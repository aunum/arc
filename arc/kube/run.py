import logging
import xmlrpc.client
import functools
from typing import Callable, Optional
import atexit
import socket
import pickle

from kubernetes.client import (
    CoreV1Api,
    V1PodSpec,
    V1ObjectMeta,
    V1Namespace,
)
from kubernetes.client.rest import ApiException
from kubernetes import config
from kubernetes.stream import portforward
import cloudpickle

from arc.image.build import DEFAULT_PORT
from arc.scm import SCM
from arc.config import Config, RemoteSyncStrategy
from arc.kube.sync import sync_repo_to_pod
from arc.kube.pod_util import (
    wait_for_pod_ready,
    wait_for_pod_running,
    pod_exists,
    create_pod_obj_from_func,
    get_pod_name_from_func,
    apply_pod,
)

logging.basicConfig(level=logging.INFO)
_REMOTE_CALL = False


def is_notebook() -> bool:
    """Checks if the current environment is a notebook

    Returns:
        bool: whether the current environment is a notebook
    """
    try:
        shell = get_ipython().__class__.__name__  # type: ignore
        if shell == "ZMQInteractiveShell":
            return True  # Jupyter notebook or qtconsole
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False


def namespace_exists(name: str, core_v1_api: Optional[CoreV1Api] = None) -> bool:
    """Checks if a namespace exists

    Args:
        name (str): name of the namespace
        core_v1_api (CoreV1Api, optional): client to use

    Raises:
        e: APIException if not a 404

    Returns:
        bool: whether the namespace exists
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()
    found = True
    try:
        core_v1_api.read_namespace(name)
    except ApiException as e:
        if e.status == 404:
            found = False
        else:
            raise e
    return found


def find_or_create_namespace(name: str, core_v1_api: Optional[CoreV1Api] = None) -> None:
    """Find or create the given namespace

    Args:
        namespace (str): name of the namespace
        core_v1_api (CoreV1Api, optional): client to use
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()
    exists = namespace_exists(name, core_v1_api)
    if exists:
        return

    core_v1_api.create_namespace(V1Namespace(metadata=V1ObjectMeta(name=name)))
    return


def create_pod_from_func(
    func: Callable,
    namespace: str,
    spec: Optional[V1PodSpec] = None,
    core_v1_api: Optional[CoreV1Api] = None,
    scm: Optional[SCM] = None,
    name: Optional[str] = None,
    sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.CONTAINER,
) -> None:
    """Create a pod from a function

    Args:
        func (Callable): function to use
        namespace (str): kubernetes namespace
        spec (Optional[V1PodSpec], optional): a custom spec. Defaults to None.
        core_v1_api (CoreV1Api, optional): client to use. Defaults to None.
        scm (SCM, optional): SCM to use. Defaults to SCM().
        name (str): name of the pod.
    """
    if scm is None:
        scm = SCM()

    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()

    if name is None:
        name = get_pod_name_from_func(func, scm)

    pod = create_pod_obj_from_func(
        func, spec=spec, core_v1_api=core_v1_api, scm=scm, name=name, sync_strategy=sync_strategy
    )
    apply_pod(name, namespace, pod, core_v1_api)
    return


def clean_all_funcs(namespace: str, core_v1_api: Optional[CoreV1Api] = None) -> None:
    """Clean all arc functions from a cluster namespace

    Args:
        namespace (str): namespace to clean
        core_v1_api (Optional[CoreV1Api], optional): client to use. Defaults to None.
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()

    ret = core_v1_api.list_namespaced_pod(namespace, label_selector="arc/type=func")
    if ret is None:
        return
    for item in ret.items:
        logging.info(f"deleting pod '{item.metadata.name}' in namespace '{item.metadata.namespace}'")
        core_v1_api.delete_namespaced_pod(item.metadata.name, item.metadata.namespace)
    return


def clean_func(func: Callable, namespace: str, core_v1_api: Optional[CoreV1Api] = None) -> None:
    """Clean arc function from cluster

    Args:
        namespace (str): namespace to clean
        core_v1_api (Optional[CoreV1Api], optional): client to use. Defaults to None.
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()

    pod_name = get_pod_name_from_func(func)
    logging.info(f"deleting pod '{pod_name}' in namespace '{namespace}'")
    core_v1_api.delete_namespaced_pod(pod_name, namespace)
    return


def pod(
    namespace: Optional[str] = None,
    spec: Optional[V1PodSpec] = None,
    clean: bool = True,
    sync_strategy: Optional[RemoteSyncStrategy] = None,
    cfg: Optional[Config] = None,
    core_v1_api: Optional[CoreV1Api] = None,
    scm: Optional[SCM] = None,
) -> Callable:
    """Run a Python function in a pod

    Args:
        namespace (str): kubernetes namespace to use
        spec (Optional[V1PodSpec]): pod spec to use
        clean (bool): whether to clean up the functions in the cluster

    Returns:
        (Callable): A wrapper to execute in a pod
    """
    if sync_strategy is None:
        if cfg is None:
            cfg = Config()
        sync_strategy = cfg.remote_sync_strategy

    def decorator(func: Callable):
        if is_notebook():
            # TODO: https://chapeau.freevariable.com/2017/12/module-frontier.html
            raise EnvironmentError("notebook support is not yet supported")

        logging.info(f"_REMOTE_CALL={_REMOTE_CALL}")
        # This prevents infinite recursion of the remote function creating more remote functions
        if _REMOTE_CALL:
            logging.info("in remote proceedure, skipping wrapper")
            return func

        # should cache the image here with kubefledged
        config.load_kube_config()

        nonlocal cfg
        if cfg is None:
            cfg = Config()

        nonlocal scm
        if scm is None:
            scm = SCM()

        nonlocal core_v1_api
        if core_v1_api is None:
            core_v1_api = CoreV1Api()

        nonlocal namespace
        namespace = str(namespace)
        if namespace:
            namespace = cfg.kube_namespace

        if clean:
            atexit.register(clean_func, func, namespace, core_v1_api=core_v1_api)

        # check if namespace exists
        find_or_create_namespace(namespace, core_v1_api)

        # check if container exists
        pod_name = get_pod_name_from_func(func, scm)
        found = pod_exists(pod_name, namespace, core_v1_api)

        if not found:
            logging.info(f"creating container for {func.__name__}")
            create_pod_from_func(func, namespace, spec=spec, core_v1_api=core_v1_api, scm=scm, name=pod_name)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logging.info(f"checking if pod is running for {pod_name}")

            # see if pod is running
            running = wait_for_pod_running(pod_name, namespace, core_v1_api)
            if not running:
                raise SystemError(f"pod {pod_name} never started running")

            logging.info(f"pod is running '{pod_name}'")

            if cfg.remote_sync_strategy == RemoteSyncStrategy.CONTAINER:
                logging.info("sync repo to pod")
                sync_repo_to_pod(pod_name, namespace, sync_strategy, func.__name__, scm, core_v1_api)
                logging.info("synced repo to pod")

            # see if pod is ready
            ready = wait_for_pod_ready(pod_name, namespace, core_v1_api)
            if not ready:
                raise SystemError(f"pod {pod_name} never became ready")

            logging.info(f"pod is ready'{pod_name}'")

            # monkey patch the python socket to connect to k8s
            socket_create_connection = socket.create_connection

            def kubernetes_create_connection(address, *args, **kwargs):
                dns_name = address[0]
                if isinstance(dns_name, bytes):
                    dns_name = dns_name.decode()
                dns_name = dns_name.split(".")
                if dns_name[-1] != "kubernetes":
                    return socket_create_connection(address, *args, **kwargs)
                if len(dns_name) not in (3, 4):
                    raise RuntimeError("Unexpected kubernetes DNS name.")
                namespace = dns_name[-2]
                name = dns_name[0]
                port = address[1]
                pf = portforward(core_v1_api.connect_get_namespaced_pod_portforward, name, namespace, ports=str(port))
                return pf.socket(port)

            socket.create_connection = kubernetes_create_connection

            # connect to the rpc server and call function
            server_addr = f"http://{pod_name}.pod.{namespace}.kubernetes:{DEFAULT_PORT}"
            with xmlrpc.client.ServerProxy(server_addr, allow_none=True) as proxy:
                logging.info(f"connected to rpc function {func.__name__}")
                args_bytes = cloudpickle.dumps(args)  # type: ignore
                kwargs_bytes = cloudpickle.dumps(kwargs)  # type: ignore

                cmd = f"result = proxy.receive(args_bytes, kwargs_bytes)"
                d = {}
                exec(cmd, locals(), d)
                r = d["result"]
                return pickle.loads(r.data)

        return wrapper

    return decorator

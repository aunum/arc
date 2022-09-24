from distutils import core
import logging
import time
import xmlrpc.client
import functools
import inspect
from typing import Callable, Optional
import atexit
import socket

from kubernetes.client import (
    CoreV1Api,
    V1Pod,
    V1PodSpec,
    V1Container,
    V1ObjectMeta,
    V1ContainerPort,
    V1Probe,
    V1Namespace,
    V1ExecAction,
)
from kubernetes.client.rest import ApiException
from kubernetes import config
from kubernetes.stream import portforward

from arc.image.build import find_or_build_img, DEFAULT_PORT
from arc.scm import SCM
from arc.kube.entrypoint import generate_entrypoint
from arc.config import Config, RemoteSyncStrategy

TYPE_LABEL = "arc/type"
FUNC_NAME_LABEL = "arc/func"
SYNC_SHA_LABEL = "arc/sync-sha"
REPO_SHA_LABEL = "arc/repo-sha"
ENV_SHA_LABEL = "arc/env-sha"
REPO_NAME_LABEL = "arc/repo"
SYNC_STRATEGY_LABEL = "sync-strategy"


def pod_running(name: str, namespace: str, core_v1_api: Optional[CoreV1Api] = None) -> bool:
    """Check if a pod is running

    Args:
        name (str): name of the pod
        namespace (str): namespace of the pod
        core_v1_api (CoreV1Api, optional): client to use

    Returns:
        bool: whether the pod is running
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()

    try:
        pod: V1Pod = core_v1_api.read_namespaced_pod(name, namespace)
    except ApiException as e:
        logging.info(f"waiting for pod to be running {e}")
        return False
    else:
        if pod.status.phase == "Failed":
            raise SystemError("pod is failed, check logs")
        elif pod.status.phase != "Running":
            logging.info(f"waiting for pod to be running; current phase: {pod.status.phase}")
            return False
        else:
            return True


def wait_for_pod_running(
    name: str,
    namespace: str,
    core_v1_api: Optional[CoreV1Api] = None,
    wait_interval: int = 1,
    max_attempts: int = 1000,
) -> bool:
    """Wait for a pod to be running

    Args:
        name (str): name of the pod
        namespace (str): namespace of the pod
        core_v1_api (CoreV1Api, optional): client to use
        wait_interval (int): period in seconds to wait before retrying
        max_attempts (int): maximum number of intervals to retry for

    Returns:
        bool: whether the pod is running
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()
    ready = False
    for _ in range(max_attempts):
        ready = pod_running(name, namespace, core_v1_api)
        if not ready:
            logging.info(f"pod not running, retrying in {wait_interval} seconds")
            time.sleep(wait_interval)
            continue
        break
    return ready


def pod_ready(name: str, namespace: str, core_v1_api: Optional[CoreV1Api] = None) -> bool:
    """Check if a pod is ready and has passed it's health checks

    Args:
        name (str): name of the pod
        namespace (str): namespace of the pod
        core_v1_api (CoreV1Api, optional): client to use

    Returns:
        bool: whether the pod is ready
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()

    try:
        pod: V1Pod = core_v1_api.read_namespaced_pod(name, namespace)
    except ApiException as e:
        logging.info(f"waiting for pod to become ready {e}")
        return False
    else:
        if pod.status.phase == "Failed":
            raise SystemError("pod is failed, check logs")
        elif pod.status.phase != "Running":
            logging.info(f"waiting for pod to become ready; current phase: {pod.status.phase}")
            return False
        else:
            for status in pod.status.container_statuses:
                if not status.ready:
                    logging.info(f"pod running but not ready")
                    return False
            return True


def wait_for_pod_ready(
    name: str,
    namespace: str,
    core_v1_api: Optional[CoreV1Api] = None,
    wait_interval: int = 1,
    max_attempts: int = 1000,
) -> bool:
    """Wait for a pod to be ready and passing it's health checks

    Args:
        name (str): name of the pod
        namespace (str): namespace of the pod
        core_v1_api (CoreV1Api, optional): client to use
        wait_interval (int): period in seconds to wait before retrying
        max_attempts (int): maximum number of intervals to retry for

    Returns:
        bool: whether the pod is ready
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()
    ready = False
    for _ in range(max_attempts):
        ready = pod_ready(name, namespace, core_v1_api)
        if not ready:
            logging.info(f"pod not ready, retrying in {wait_interval} seconds")
            time.sleep(wait_interval)
            continue
        break
    return ready


def pod_exists(name: str, namespace: str, core_v1_api: Optional[CoreV1Api] = None) -> bool:
    """Checks if a pod exists

    Args:
        name (str): name of the pod
        namespace (str): namespace of the pod
        core_v1_api (CoreV1Api, optional): client to use

    Raises:
        e: An APIException if not a 404

    Returns:
        bool: whether the pod exists
    """
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()

    found = True
    try:
        core_v1_api.read_namespaced_pod(name, namespace)
    except ApiException as e:
        if e.status == 404:
            found = False
        else:
            raise e
    return found


def get_pod_name_from_func(func: Callable, scm: Optional[SCM] = None, cfg: Optional[Config] = None) -> str:
    """Get the pod name based on the function

    Args:
        func (Callable): the function to use
        scm (SCM, optional): SCM to use. Defaults to SCM().

    Returns:
        str: the pod name
    """
    if scm is None:
        scm = SCM()

    if cfg is None:
        cfg = Config()

    func_module = inspect.getmodule(func)
    if func_module is None:
        raise SystemError(f"cannot find module for func {func.__name__}")

    mod_name = func_module.__name__
    if mod_name == "__main__":
        mod_name = "main"
    mod_clean = mod_name.replace(".", "-").replace("_", "-")
    name_clean = func.__name__.replace("_", "-")

    return f"fn-{mod_clean}-{name_clean}"


def create_pod_obj_from_func(
    func: Callable,
    spec: Optional[V1PodSpec] = None,
    core_v1_api: Optional[CoreV1Api] = None,
    scm: Optional[SCM] = None,
    name: Optional[str] = None,
    sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.CONTAINER,
) -> V1Pod:
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

    image_id = find_or_build_img(scm=scm, sync_strategy=sync_strategy)

    if name is None:
        name = get_pod_name_from_func(func, scm)

    # create command which starts remote server
    entrypoint = generate_entrypoint(func, sync_strategy=sync_strategy)
    command = ["python", "-c", entrypoint]
    logging.debug(f"running command: {command}")

    container = V1Container(
        name=func.__name__.replace("_", "-"),
        image=image_id.ref(),
        command=command,
        ports=[V1ContainerPort(container_port=8000)],
        startup_probe=V1Probe(
            success_threshold=1,
            _exec=V1ExecAction(
                command=[
                    "curl",
                    "-d",
                    "<?xml version='1.0'?><methodCall><methodName>lives</methodName></methodCall>",
                    "http://localhost:8000/RPC2",
                ]
            ),
            period_seconds=1,
            failure_threshold=10000,
        ),
    )
    if spec is None:
        spec = V1PodSpec(
            containers=[container],
            restart_policy="Never",
        )
    elif spec.containers is None:
        spec.containers = [container]
    elif spec.restart_policy is None:
        spec.restart_policy = "Never"
    pod = V1Pod(
        metadata=V1ObjectMeta(
            name=name,
            labels={
                TYPE_LABEL: "func",
                FUNC_NAME_LABEL: func.__name__,
                REPO_SHA_LABEL: scm.sha(),
                ENV_SHA_LABEL: scm.env_sha(),
                REPO_NAME_LABEL: scm.name(),
            },
        ),
        spec=spec,
    )
    return pod


def apply_pod(name: str, namespace: str, pod: V1Pod, core_v1_api: Optional[CoreV1Api] = None) -> None:
    if core_v1_api is None:
        config.load_kube_config()
        core_v1_api = CoreV1Api()
    try:
        core_v1_api.read_namespaced_pod(name, namespace)
        exists = True
    except ApiException:
        exists = False

    if not exists:
        core_v1_api.create_namespaced_pod(namespace, pod)
        return

    core_v1_api.replace_namespaced_pod(name, namespace, pod)
    return

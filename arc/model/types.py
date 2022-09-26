from abc import ABC, abstractmethod
from dataclasses import is_dataclass, make_dataclass, field
from enum import Enum
from typing import Dict, Generic, TypeVar, List, Any, Optional, Type, Union
import inspect
import time
import logging
import os
import socket
import json
import yaml
from pathlib import Path
import typing

import cloudpickle as pickle
from dataclasses_jsonschema import JsonSchemaMixin, T
from simple_parsing.helpers import Serializable
from kubernetes import client, config
from kubernetes.stream import portforward
from kubernetes.client.models import (
    V1EphemeralContainer,
    V1VolumeMount,
    V1Pod,
    V1PodSpec,
    V1PodList,
    V1Container,
    V1ContainerPort,
    V1ConfigMap,
    V1Volume,
    V1ConfigMapVolumeSource,
    V1Probe,
    V1ExecAction,
    V1EnvVar,
    V1EmptyDirVolumeSource,
    V1SecretVolumeSource,
    V1KeyToPath,
    V1PodStatus,
    V1ContainerStatus,
    V1ContainerState,
    V1ContainerStateRunning,
    V1ContainerStateTerminated,
    V1ContainerStateWaiting,
)
from kubernetes.client import CoreV1Api, V1PodSpec, V1ObjectMeta, RbacAuthorizationV1Api
from docker.utils.utils import parse_repository_tag
from docker.auth import resolve_repository_name
from urllib import request

from arc.data.types import Data
from arc.data.shapes.classes import ClassData
from arc.data.shapes.image import ImageData
from arc.kube.sync import copy_file_to_pod
from arc.model.util import get_orig_class
from arc.model.metrics import Metrics
from arc.model.opts import Opts
from arc.image.client import default_socket
from arc.image.build import REPO_ROOT, find_or_build_img, img_command
from arc.kube.pod_util import (
    REPO_SHA_LABEL,
    TYPE_LABEL,
    SYNC_SHA_LABEL,
    REPO_NAME_LABEL,
    ENV_SHA_LABEL,
    SYNC_STRATEGY_LABEL,
    wait_for_pod_ready,
)
from arc.config import Config, RemoteSyncStrategy
from arc.scm import SCM
from arc.image.registry import get_img_labels, get_repo_tags
from arc.data.encoding import ShapeEncoder
from arc.kube.env import is_k8s_proc
from arc.kube.auth_util import ensure_cluster_auth_resources, get_dockercfg_secret_name
from arc.config import Opts
from arc.image.build import img_id

X = TypeVar("X", bound="Data")
Y = TypeVar("Y", bound="Data")
O = TypeVar("O", bound="Opts")
M = TypeVar("M", bound="Model")


MODEL_LABEL = "model"
MODEL_NAME_LABEL = "name"
MODEL_VERSION_LABEL = "version"
MODEL_BASE_NAME_LABEL = "base"
MODEL_X_DATA_LABEL = "x"
MODEL_X_DATA_SCHEMA_LABEL = "x-schema"
MODEL_Y_DATA_LABEL = "y"
MODEL_Y_DATA_SCHEMA_LABEL = "y-schema"
MODEL_PARAMS_SCHEMA_LABEL = "params-schema"
MODEL_SERVER_PATH_LABEL = "server-path"
MODEL_PHASE_LABEL = "model-phase"
SERVER_PORT = "8080"
MODEL_CONFIG_FILE_NAME = "config.json"
MODEL_PKL_FILE_NAME = "model.pkl"
BUILD_MNT_DIR = "/mnt/build"


class Client(ABC):
    """A client"""

    pass


class APIUtil(JsonSchemaMixin):
    @classmethod
    def from_yaml(cls: Type[T], data: Union[str, bytes], validate: bool = True, **yaml_kwargs) -> T:
        return cls.from_dict(yaml.load(data, **yaml_kwargs), validate)

    def to_yaml(self, omit_none: bool = True, validate: bool = False, **yaml_kwargs) -> str:
        return yaml.dump(self.to_dict(omit_none, validate), **yaml_kwargs)


class Model(ABC, APIUtil):
    """A machine learning model"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the model

        Returns:
            str: The name of the model
        """
        pass

    def save(self, out_dir: str = "./model") -> None:
        """Save the model

        Args:
            out_dir (str, optional): Directory to output the model. Defaults to "./".
        """
        out_path = os.path.join(out_dir, "model.pkl")
        with open(out_path, "wb") as f:
            pickle.dump(self, f)
        return

    @classmethod
    def load(cls, dir: str = "./model") -> M:
        """Load the model

        Args:
            dir (str): Directory to the model
        """
        # https://stackoverflow.com/questions/52591862/how-can-i-save-an-object-containing-keras-models
        path = os.path.join(dir, "model.pkl")
        with open(path, "r") as f:
            return pickle.loads(f)

    @classmethod
    def opts(cls: Type["Model"]) -> Opts:
        if is_dataclass(cls):
            return cls
        sig = inspect.signature(cls.__init__)
        fin_params = []
        for param in sig.parameters:
            if param == "self":
                continue
            if sig.parameters[param].default == inspect._empty:
                fin_params.append((param, sig.parameters[param].annotation))
            else:
                fin_params.append(
                    (param, sig.parameters[param].annotation, field(default=sig.parameters[param].default))  # type: ignore
                )

        return make_dataclass(cls.__name__ + "Opts", fin_params, bases=(Serializable, JsonSchemaMixin))

    @classmethod
    def from_opts(cls: Type["Model"], opts: Opts) -> "Model":
        return cls(**opts.__dict__)


# Do we want to break that up into a trainer and an inference client?
class SupervisedModelClient(Generic[X, Y], Client):
    """A client for a supervised model"""

    pod_name: str
    pod_namespace: str
    xcls: Optional[Type[X]] = None
    ycls: Optional[Type[Y]] = None
    uri: Optional[str] = None
    server_addr: str

    def __init__(
        self,
        uri: Optional[str] = None,
        model: Optional[Type["SupervisedModel"]] = None,
        core_v1_api: Optional[CoreV1Api] = None,
        rbac_v1_api: Optional[RbacAuthorizationV1Api] = None,
        docker_socket: Optional[str] = None,
        namespace: Optional[str] = None,
        cfg: Optional[Config] = None,
        scm: Optional[SCM] = None,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
        dev_dependencies: bool = False,
        **kwargs,
    ) -> None:
        """Create a SupervisedModelClient

        Args:
            # should this just be a container for now?
            uri (str): OCI URI to the model
            docker_socket (str, optional): docker socket to use. Defaults to None.
        """

        self.uri = uri
        print("client uri: ", self.uri)

        params: Optional[Dict[str, Any]] = None
        if len(kwargs) != 0:
            params = kwargs

        if is_k8s_proc():
            logging.info("running in kubernetes")

        else:
            logging.info("not running in kubernetes")

        if core_v1_api is None:
            if is_k8s_proc():
                config.load_incluster_config()
            else:
                config.load_kube_config()

            core_v1_api = CoreV1Api()

        if rbac_v1_api is None:
            if is_k8s_proc():
                config.load_incluster_config()
            else:
                config.load_kube_config()
            rbac_v1_api = RbacAuthorizationV1Api()

        # We need to get metadata on the model by looking at the registry and pulling metadata
        if docker_socket is None:
            docker_socket = default_socket()

        if cfg is None:
            cfg = Config()

        if scm is None:
            scm = SCM()

        if namespace is None:
            namespace = cfg.kube_namespace

        if model is not None:
            self.uri = model.base_image(scm=scm, dev_dependencies=dev_dependencies, sync_strategy=sync_strategy)

        # Check schema compatibility between client/server
        img_labels = get_img_labels(self.uri)

        if img_labels is None:
            raise ValueError(f"image uri '{self.uri}' does not contain any labels, are you sure it was build by arc?")

        self.model_x_schema = img_labels[MODEL_X_DATA_SCHEMA_LABEL]
        self.model_y_schema = img_labels[MODEL_Y_DATA_SCHEMA_LABEL]
        self.model_params_schema = img_labels[MODEL_PARAMS_SCHEMA_LABEL]
        self.server_path = img_labels[MODEL_SERVER_PATH_LABEL]
        self.model_phase = img_labels[MODEL_PHASE_LABEL]

        # TODO: find a way to validate schemas during init
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

            if is_k8s_proc():
                pod_found = core_v1_api.read_namespaced_pod(name, namespace)
                ip = pod_found.status.pod_ip
                ipstr = ip.replace(".", "-")
                addr = f"{ipstr}.{namespace}.pod.cluster.local"
                return socket_create_connection((addr, port), *args, **kwargs)

            pf = portforward(
                core_v1_api.connect_get_namespaced_pod_portforward, name, namespace, ports=str(SERVER_PORT)
            )
            return pf.socket(int(port))

        socket.create_connection = kubernetes_create_connection

        # check if container exists
        logging.info("checking if model is already running in cluster")
        pod_list: V1PodList = core_v1_api.list_namespaced_pod(namespace)
        for pod in pod_list.items:
            annotations = pod.metadata.annotations
            pod_name = pod.metadata.name
            if annotations is None:
                continue
            if MODEL_LABEL in annotations:
                server_model_uri = annotations[MODEL_LABEL]
                if server_model_uri == self.uri:
                    logging.info("found model running in cluster")
                    self.server_addr = f"http://{pod_name}.pod.{namespace}.kubernetes:{SERVER_PORT}"
                    self.pod_name = pod_name
                    self.pod_namespace = namespace
                    logging.info(f"server info: {self.info()}")
                    if sync_strategy == RemoteSyncStrategy.CONTAINER:
                        logging.info("sync strategy is container")
                        if SYNC_SHA_LABEL in annotations:
                            if annotations[SYNC_SHA_LABEL] == scm.sha():
                                logging.info("sync sha label up to date")
                                return

                        logging.info("sync sha doesn't match, syncing files")
                        if model is None:
                            raise ValueError("job cannot be none when doing a container sync")
                        server_path = model.server_entrypoint()
                        logging.info(f"wrote server to path: {server_path}")
                        copy_file_to_pod(
                            scm.all_files(),
                            pod_name,
                            namespace=namespace,
                            base_path=REPO_ROOT.lstrip("/"),
                            label=True,
                            core_v1_api=core_v1_api,
                            scm=scm,
                            restart=False,
                        )
                        # TODO: need to remove this sleep
                        time.sleep(10)
                        logging.info("files copied to pod, waiting for pod to become ready")
                        # see if pod is ready
                        ready = wait_for_pod_ready(pod_name, namespace, core_v1_api)
                        if not ready:
                            raise SystemError(f"pod {pod_name} never became ready")
                        logging.info("pod is ready!")

                        # should check if info returns the right version
                        # it will just return the original verion, how do we sync the verion with the files to tell if its running?
                        # TODO!
                        logging.info(self.info())
                    logging.info("returning")
                    return

        logging.info("model not found running, deploying now...")
        repository, tag = parse_repository_tag(self.uri)
        registry, repo_name = resolve_repository_name(repository)
        project_name = repo_name.split("/")[1]

        # need to know if this should have a configmap
        pod_name = f"{str(project_name).replace('/', '-')}-{tag}"
        if len(pod_name) > 63:
            pod_name = pod_name[:62]

        if params is not None:
            cfg = V1ConfigMap(
                metadata=V1ObjectMeta(name=pod_name, namespace=namespace), data={"cfg": json.dumps(params)}
            )
            core_v1_api.create_namespaced_config_map(namespace, cfg)

        logging.info("ensuring cluster auth resources...")
        auth_resources = ensure_cluster_auth_resources(core_v1_api, rbac_v1_api, docker_socket, namespace, cfg)

        # if not deploy
        container = V1Container(
            name="server",
            command=img_command(self.server_path),
            image=self.uri,
            ports=[V1ContainerPort(container_port=int(SERVER_PORT))],
            startup_probe=V1Probe(
                success_threshold=1,
                _exec=V1ExecAction(
                    command=[
                        "curl",
                        f"http://localhost:{SERVER_PORT}/health",
                    ]
                ),
                period_seconds=1,
                failure_threshold=10000,
            ),
            env=[V1EnvVar(name="MODEL_URI", value=self.uri)],
        )
        container.volume_mounts = [
            V1VolumeMount(name="build", mount_path=BUILD_MNT_DIR),
            V1VolumeMount(name="dockercfg", mount_path="/root/.docker"),
        ]
        if params is not None:
            container.volume_mounts.append(
                V1VolumeMount(name="config", mount_path=REPO_ROOT, sub_path=MODEL_CONFIG_FILE_NAME)
            )

        spec = V1PodSpec(
            containers=[container],
            service_account_name=auth_resources.service_account_name,
        )
        spec.volumes = [
            V1Volume(name="build", empty_dir=V1EmptyDirVolumeSource()),
            V1Volume(
                name="dockercfg",
                secret=V1SecretVolumeSource(
                    secret_name=auth_resources.secret_name,
                    items=[V1KeyToPath(key=".dockerconfigjson", path="config.json")],
                ),
            ),
        ]
        if params is not None:
            spec.volumes.append(V1Volume(name="config", config_map=V1ConfigMapVolumeSource(name=pod_name)))

        pod = V1Pod(
            metadata=V1ObjectMeta(
                name=pod_name,
                namespace=namespace,
                labels={
                    TYPE_LABEL: "server",
                    MODEL_PHASE_LABEL: self.model_phase,
                    REPO_SHA_LABEL: scm.sha(),
                    ENV_SHA_LABEL: scm.env_sha(),
                    REPO_NAME_LABEL: scm.name(),
                    SYNC_STRATEGY_LABEL: str(sync_strategy),
                },
                annotations={
                    MODEL_LABEL: self.uri,
                    MODEL_X_DATA_LABEL: img_labels[MODEL_X_DATA_LABEL],
                    MODEL_Y_DATA_LABEL: img_labels[MODEL_Y_DATA_LABEL],
                    MODEL_SERVER_PATH_LABEL: img_labels[MODEL_SERVER_PATH_LABEL],
                    MODEL_X_DATA_SCHEMA_LABEL: self.model_x_schema,
                    MODEL_Y_DATA_SCHEMA_LABEL: self.model_y_schema,
                    MODEL_PARAMS_SCHEMA_LABEL: self.model_params_schema,
                },
            ),
            spec=spec,
        )
        # This should run the image on Kubernetes and store a connection to the server
        core_v1_api.create_namespaced_pod(namespace, pod)

        # see if pod is ready
        ready = wait_for_pod_ready(pod_name, namespace, core_v1_api)
        if not ready:
            raise SystemError(f"pod {pod_name} never became ready")

        logging.info(f"pod is ready'{pod_name}'")

        # TODO: handle readiness
        time.sleep(10)

        self.server_addr = f"http://{pod_name}.pod.{namespace}.kubernetes:{SERVER_PORT}"
        self.pod_name = pod_name
        self.pod_namespace = namespace

        logging.info(f"server info: {self.info()}")

        if sync_strategy == RemoteSyncStrategy.CONTAINER:
            logging.info("syncing files to model container")
            if model is None:
                raise SystemError("cannot sync files to a container without a model parameter passed in init")
            server_path = model.server_entrypoint()
            logging.info(f"wrote server to path: {server_path}")
            copy_file_to_pod(
                scm.all_files(),
                pod_name,
                namespace=namespace,
                base_path=REPO_ROOT.lstrip("/"),
                label=True,
                core_v1_api=core_v1_api,
                scm=scm,
                restart=False,
            )
            # TODO: need to remove this sleep
            time.sleep(10)
            logging.info("files copied to pod, waiting for pod to become ready")
            # see if pod is ready
            ready = wait_for_pod_ready(pod_name, namespace, core_v1_api)
            if not ready:
                raise SystemError(f"pod {pod_name} never became ready")
            logging.info("pod is ready!")

            # should check if info returns the right version
            # it will just return the original verion, how do we sync the verion with the files to tell if its running?
            # TODO!
            logging.info(self.info())
        return

    def validate(self) -> None:
        """Validate the client and server schema are compatible"""

        orig = get_orig_class(self)

    def info(self) -> Dict[str, Any]:
        """Info about the server

        Returns:
            Dict[str, Any]: Server info
        """
        req = request.Request(f"{self.server_addr}/info")
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        return json.loads(data)

    def schema(self) -> Dict[str, Any]:
        """Get OpenAPI schema for the server

        Returns:
            Dict[str, Any]: Schema of the server
        """
        req = request.Request(f"{self.server_addr}/schema")
        resp = request.urlopen(req)
        return resp.read().decode("utf-8")

    def compile(self, x: X, y: Y) -> None:
        """Compile the model

        Args:
            x (X): A sample of X
            y (Y): A sample of Y
        """
        params = json.dumps({"x": x, "y": y}, cls=ShapeEncoder).encode("utf8")
        req = request.Request(f"{self.server_addr}/compile", data=params, headers={"content-type": "application/json"})
        resp = request.urlopen(req)
        resp_data = resp.read().decode("utf-8")

        logging.info(resp_data)
        return

    # This neccessitates a Predictor or Router interface, so that fit is not exposed
    def fit(self, x: X, y: Y) -> Metrics:
        """Fit X to Y

        Args:
            x (X): Input data
            y (Y): Expected output data

        Returns:
            Metrics: Metrics
        """
        # use the connection to call standardized methods
        params = json.dumps({"x": x, "y": y}, cls=ShapeEncoder).encode("utf8")
        req = request.Request(f"{self.server_addr}/fit", data=params, headers={"content-type": "application/json"})
        resp = request.urlopen(req)
        resp_data = resp.read().decode("utf-8")

        metrics = json.loads(resp_data)
        return metrics

    def predict(self, x: X) -> Y:
        """Predict Y given X

        Args:
            x (X): Input

        Returns:
            Y: Prediction
        """
        params = json.dumps({"x": x}, cls=ShapeEncoder).encode("utf8")
        req = request.Request(f"{self.server_addr}/predict", data=params, headers={"content-type": "application/json"})
        resp = request.urlopen(req)
        resp_data = resp.read().decode("utf-8")

        if self.ycls is None:
            orig = get_orig_class(self)
            self.xcls, self.ycls = orig.__args__
        y = json.loads(resp_data, object_hook=lambda d: self.ycls(**d))  # type: ignore
        return y

    @classmethod
    def find(cls) -> List["SupervisedModelClient"]:
        """Find all the models that could be deployed (or are running) that we could find, should show with the metrics"""
        pass

    def save(
        self,
        version: Optional[str] = None,
        core_v1_api: Optional[CoreV1Api] = None,
    ) -> str:  # TODO: make this a generator
        """Save the model

        Returns:
            str: URI of the saved model
        """
        if core_v1_api is None:
            if is_k8s_proc():
                config.load_incluster_config()
            else:
                config.load_kube_config()

            core_v1_api = CoreV1Api()

        logging.info("saving model...")

        req = request.Request(f"{self.server_addr}/save", method="POST")
        resp = request.urlopen(req)
        body = resp.read().decode("utf-8")

        # should get the version of the model from the model
        repository, tag = parse_repository_tag(self.uri)
        registry, repo_name = resolve_repository_name(repository)
        docker_secret = get_dockercfg_secret_name()

        cls_name = tag.split("-")[1]

        info = self.info()
        version = info["version"]
        uri = img_id(RemoteSyncStrategy.IMAGE, tag=f"model-{cls_name}-{version}")

        path_params = {"name": self.pod_name, "namespace": self.pod_namespace}

        query_params = []  # type: ignore
        header_params = {}

        form_params = []  # type: ignore
        local_var_files = {}  # type: ignore

        header_params["Accept"] = "application/json"
        header_params["Content-Type"] = "application/strategic-merge-patch+json"

        # Authentication setting
        auth_settings = ["BearerToken"]  # noqa: E501

        _pod: V1Pod = core_v1_api.read_namespaced_pod(self.pod_name, self.pod_namespace)
        labels: Dict[str, str] = _pod.metadata.labels
        annotations: Dict[str, str] = _pod.metadata.annotations

        body = {
            "spec": {
                "ephemeralContainers": [
                    {
                        "name": f"snapshot-{int(time.time())}",
                        "args": [
                            f"--context={REPO_ROOT}",
                            f"--destination={uri}",
                            f"--dockerfile=Dockerfile.arc",
                            "--ignore-path=/product_uuid",  # For kind https://github.com/GoogleContainerTools/kaniko/issues/2164
                            f"--label={MODEL_BASE_NAME_LABEL}=SupervisedModel",
                            f"--label={MODEL_PHASE_LABEL}={info['phase']}",
                            f"--label={MODEL_NAME_LABEL}={info['name']}",
                            f"--label={MODEL_VERSION_LABEL}={info['version']}",
                            f"--label={MODEL_X_DATA_LABEL}={annotations[MODEL_X_DATA_LABEL]}",
                            f"--label={MODEL_Y_DATA_LABEL}={annotations[MODEL_Y_DATA_LABEL]}",
                            f"--label={MODEL_X_DATA_SCHEMA_LABEL}={annotations[MODEL_X_DATA_SCHEMA_LABEL]}",
                            f"--label={MODEL_Y_DATA_SCHEMA_LABEL}={annotations[MODEL_Y_DATA_SCHEMA_LABEL]}",
                            f"--label={MODEL_PARAMS_SCHEMA_LABEL}={annotations[MODEL_PARAMS_SCHEMA_LABEL]}",
                            f"--label={MODEL_SERVER_PATH_LABEL}={annotations[MODEL_SERVER_PATH_LABEL]}",
                            f"--label={ENV_SHA_LABEL}={info['env-sha']}",
                            f"--label={REPO_NAME_LABEL}={labels[REPO_NAME_LABEL]}",
                            f"--label={REPO_SHA_LABEL}={info['version']}",
                        ],
                        "image": "gcr.io/kaniko-project/executor:latest",
                        "volumeMounts": [
                            {"mountPath": "/kaniko/.docker/", "name": "dockercfg"},
                            {"mountPath": REPO_ROOT, "name": "build"},
                        ],
                    }
                ]
            }
        }

        core_v1_api.api_client.call_api(
            "/api/v1/namespaces/{namespace}/pods/{name}/ephemeralcontainers",
            "PATCH",
            path_params,
            query_params,
            header_params,
            body,
            post_params=form_params,
            files=local_var_files,
            response_type="V1Pod",  # noqa: E501
            auth_settings=auth_settings,
        )

        logging.info("snapshotting image...")

        done = False

        while not done:
            pod: V1Pod = core_v1_api.read_namespaced_pod(self.pod_name, self.pod_namespace)
            status: V1PodStatus = pod.status

            if status.ephemeral_container_statuses is None:
                time.sleep(1)
                logging.info("ephemeral container status is None")
                continue

            for container_status in status.ephemeral_container_statuses:
                st: V1ContainerStatus = container_status
                state: V1ContainerState = st.state

                if state.running is not None:
                    running: V1ContainerStateRunning = state.running
                    logging.info(f"snapshot is running: {running}")

                if state.terminated is not None:
                    terminated: V1ContainerStateTerminated = state.terminated
                    logging.info(f"snapshot is terminated: {terminated}")
                    if terminated.exit_code != 0:
                        raise SystemError(
                            f"unable to snapshot image - reason: {terminated.reason} message: {terminated.message}"
                        )
                    done = True

                if state.waiting is not None:
                    waiting: V1ContainerStateWaiting = state.waiting
                    logging.info(f"snapshot is waiting: {waiting}")

            time.sleep(1)

        return str(uri)


class ModelPhase(str, Enum):
    """Phase of the model"""

    BASE = "base"
    """Model is just a class that has never been initialized"""

    INITIALIZED = "initialized"
    """Model is initialized but hasn't been compiled or trained"""

    COMPILED = "compiled"
    """Model has been compiled but not yet trained"""

    TRAINED = "trained"
    """Model has been trained"""


class SupervisedModel(Generic[X, Y], Model):
    _type_x: Type[X]
    _type_y: Type[Y]
    _uri: Optional[str] = None

    @abstractmethod
    def compile(self, x: X, y: Y) -> None:
        """Compile the model

        Args:
            x (X): Sample input
            y (Y): Sample output
        """
        pass

    @abstractmethod
    def fit(self, x: X, y: Y) -> Metrics:
        """Fit X to Y

        Args:
            x (X): Input data
            y (Y): Expected output data

        Returns:
            Metrics: Metrics
        """
        pass

    @abstractmethod
    def predict(self, x: X) -> Y:
        """Predict Y given X

        Args:
            x (X): Input

        Returns:
            Y: Prediction
        """
        pass

    # TODO: should these be conditions?
    @abstractmethod
    def phase(self) -> ModelPhase:
        """Phase of the model

        Returns:
            ModelPhase: Phase of the model
        """
        # We should use this to track the phase of the model
        # def your_decorator(_cls):
        #     print("Hello, I'm decor!")
        #     def wrapper():
        #         return _cls()
        #     return wrapper

        # class ParentClass:
        #     def __init_subclass__(cls, **kwargs):
        #         return your_decorator(_cls=cls)

        # class A(ParentClass):
        #     pass

        # a = A()

        # or this https://stackoverflow.com/questions/6307761/how-to-decorate-all-functions-of-a-class-without-typing-it-over-and-over-for-eac

        pass

    # should have dev mode
    # def develop(cls) -> SupervisedModelClient:

    #     return SupervisedModelClient()

    @property
    def uri(self) -> str:
        if self._uri is None:
            return f"{self.__module__}.{self.__class__.__name__}"
        return self._uri

    @uri.setter
    def uri(self, val: str):
        self._uri = val

    # Note: This should probably be a HTTP-RPC implementation
    @classmethod
    def server_entrypoint(cls, num_workers: int = 1, scm: Optional[SCM] = None) -> str:
        sig = inspect.signature(cls.compile)
        x = sig.parameters["x"].annotation
        y = sig.parameters["y"].annotation

        obj_module = inspect.getmodule(cls)
        if obj_module is None:
            raise SystemError(f"could not find module for func {obj_module}")

        if scm is None:
            scm = SCM()
        version = scm.sha()

        mod_x = inspect.getmodule(x)
        if mod_x is not None:
            mod_x = mod_x.__name__

        mod_y = inspect.getmodule(y)
        if mod_y is not None:
            mod_y = mod_y.__name__

        cls_name = cls.__name__

        cls_file_path = Path(inspect.getfile(cls))
        cls_file = cls_file_path.stem
        cls_dir = os.path.dirname(os.path.realpath(str(cls_file_path)))
        server_file_name = f"{cls.__name__.lower()}_server.py"

        server_file = f"""
import json
import logging
from typing import Any, Dict
from dataclasses import dataclass
import sys
from pathlib import Path
import time
import os
import shutil

from simple_parsing import ArgumentParser
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.schemas import SchemaGenerator
import uvicorn

from arc.data.encoding import ShapeEncoder
from arc.model.metrics import Metrics
from arc.scm import SCM
from arc.image.build import REPO_ROOT
from arc.model.types import BUILD_MNT_DIR

from {cls_file} import {cls.__name__}
from {cls_file} import *
from {mod_x} import {x.__name__}
from {mod_y} import {y.__name__}

logging.basicConfig(level=logging.INFO)

parser = ArgumentParser()
parser.add_arguments({cls_name}.opts(), dest="{cls_name.lower()}")

args = parser.parse_args()

model_file = Path("./model.pkl")
cfg_file = Path("./config.json")

scm = SCM()

if model_file.is_file():
    model: {cls_name} = {cls.__name__}.load()
elif cfg_file.is_file():
    model = {cls.__name__}.load_json("./{MODEL_CONFIG_FILE_NAME}")
else:
    model = {cls.__name__}.from_opts(args.{cls_name.lower()})

uri = os.getenv("MODEL_URI")
model.uri = uri


app = Starlette(debug=True)

schemas = SchemaGenerator(
    {{"openapi": "3.0.0", "info": {{"title": "{cls_name}", "version": "{version}"}}}}
)

@app.route("/health")
def health(request):
    return JSONResponse({{"status": "alive"}})
kin
@app.route("/info")
def info(request):
    # model_dict = model.opts().to_dict()
    return JSONResponse({{"name": model.__class__.__name__, "version": scm.sha(), "env-sha": scm.env_sha(), "phase": model.phase().value}})

@app.route("/compile", methods=["POST"])
async def compile(request):
    jdict = await request.json()

    try:
        x = {x.__name__}.load_dict(jdict['x'])
    except Exception as e:
        print(e)
        raise

    try:
        y = {y.__name__}.load_dict(jdict['y'])
    except Exception as e:
        print(e)
        raise

    try:
        model.compile(x, y)
    except Exception as e:
        print(e)
        raise
    return JSONResponse({{"message": "model compiled"}})

@app.route("/save", methods=["POST"])
def save(request):
    model.save()
    logging.info("copying directory to build dir...")
    shutil.copytree(REPO_ROOT, BUILD_MNT_DIR, dirs_exist_ok=True)
    return JSONResponse({{"message": "model saved"}})


@app.route("/load", methods=["POST"])
def load(request):
    # TODO: configurable
    path = "./model.pkl"
    model = {cls_name}.load(path)
    return JSONResponse({{"message": "model loaded"}})


@app.route("/fit", methods=["POST"])
async def fit(request):
    jdict = await request.json()
    x = {x.__name__}.load_dict(jdict['x'])
    y = {y.__name__}.load_dict(jdict['y'])
    metrics = model.fit(x, y)
    return JSONResponse(metrics)

class ShapeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(content, cls=ShapeEncoder).encode('utf-8')

@app.route("/predict", methods=["POST"])
async def predict(request):
    jdict = await request.json()
    x = {x.__name__}.load_dict(jdict['x'])
    y = model.predict(x)
    # encode me
    return ShapeJSONResponse(y)

@app.route("/schema")
def openapi_schema(request):
    return schemas.OpenAPIResponse(request=request)


if __name__ == "__main__":
    pkgs: Dict[str, str] = {{}}
    for fp in scm.all_files():
        dir = os.path.dirname(fp)
        pkgs[dir] = ""

    logging.info("starting server version '{version}' on port: {SERVER_PORT}")
    uvicorn.run("__main__:app", host="0.0.0.0", port={SERVER_PORT}, log_level="debug", workers={num_workers}, reload=True, reload_dirs=pkgs.keys())
        """

        class_file = inspect.getfile(cls)
        dir_path = os.path.dirname(os.path.realpath(class_file))
        server_filepath = os.path.join(dir_path, server_file_name)
        with open(server_filepath, "w") as f:
            f.write(server_file)
        return server_filepath

    @classmethod
    def base_image(
        cls,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
    ) -> str:
        """Create a server image from the model class that can be used to create models from scratch"""

        if scm is None:
            scm = SCM()

        sig = inspect.signature(cls.compile)
        x = sig.parameters["x"].annotation
        y = sig.parameters["y"].annotation

        # write the server file somewhere we can find it
        server_filepath = Path(cls.server_entrypoint())
        repo_root = Path(str(scm.git_repo.working_dir))
        root_relative = server_filepath.relative_to(repo_root)
        container_path = Path(REPO_ROOT).joinpath(root_relative)

        # create an image using the imglib, and the server_endpoint method
        # does it makes sense to add command here if its going to be written to the root dockerfile?
        # feel like we can't not do it too, otherwise we would need to save a k8s artifact or something
        if sync_strategy == RemoteSyncStrategy.IMAGE:
            img_id = find_or_build_img(
                sync_strategy=RemoteSyncStrategy.IMAGE,
                command=img_command(str(container_path)),
                # TODO: rethink how we do tags? Maybe each model should be its own repo?
                tag_prefix=f"model-{cls.__name__.lower()}",
                labels={
                    MODEL_BASE_NAME_LABEL: "SupervisedModel",
                    MODEL_PHASE_LABEL: ModelPhase.BASE.value,
                    MODEL_NAME_LABEL: cls.__name__,
                    MODEL_VERSION_LABEL: scm.sha(),
                    MODEL_X_DATA_LABEL: x.__name__,
                    MODEL_X_DATA_SCHEMA_LABEL: json.dumps(x.json_schema()),
                    MODEL_Y_DATA_LABEL: y.__name__,
                    MODEL_Y_DATA_SCHEMA_LABEL: json.dumps(y.json_schema()),
                    MODEL_PARAMS_SCHEMA_LABEL: json.dumps(cls.opts().json_schema()),
                    MODEL_SERVER_PATH_LABEL: str(container_path),
                    ENV_SHA_LABEL: scm.env_sha(),
                    REPO_NAME_LABEL: scm.name(),
                    REPO_SHA_LABEL: scm.sha(),
                },
                dev_dependencies=dev_dependencies,
            )
        elif sync_strategy == RemoteSyncStrategy.CONTAINER:
            img_id = find_or_build_img(
                sync_strategy=RemoteSyncStrategy.IMAGE,  # TODO: fix this at the source, we want to copy all files now
                command=img_command(str(container_path)),
                # TODO: rethink how we do tags? Maybe each model should be its own repo?
                tag=f"modelenv-{cls.__name__.lower()}-{scm.env_sha()}",
                labels={
                    MODEL_BASE_NAME_LABEL: "SupervisedModel",
                    MODEL_PHASE_LABEL: ModelPhase.BASE.value,
                    MODEL_NAME_LABEL: cls.__name__,
                    MODEL_VERSION_LABEL: scm.sha(),
                    MODEL_X_DATA_LABEL: x.__name__,
                    MODEL_X_DATA_SCHEMA_LABEL: json.dumps(x.json_schema()),
                    MODEL_Y_DATA_LABEL: y.__name__,
                    MODEL_Y_DATA_SCHEMA_LABEL: json.dumps(y.json_schema()),
                    MODEL_PARAMS_SCHEMA_LABEL: json.dumps(cls.opts().json_schema()),
                    MODEL_SERVER_PATH_LABEL: str(container_path),
                    ENV_SHA_LABEL: scm.env_sha(),
                    REPO_NAME_LABEL: scm.name(),
                    REPO_SHA_LABEL: scm.sha(),
                },
                dev_dependencies=dev_dependencies,
            )
        if clean:
            os.remove(server_filepath)

        return str(img_id)

    def image(self, scm: Optional[SCM] = None, clean: bool = True) -> str:
        """Create a server image with the saved model"""

        if scm is None:
            scm = SCM()

        sig = inspect.signature(self.compile)
        x = sig.parameters["x"].annotation
        y = sig.parameters["y"].annotation

        self.save()

        # write the server file somewhere we can find it
        server_filepath = Path(self.server_entrypoint())
        repo_root = Path(str(scm.git_repo.working_dir))
        root_relative = server_filepath.relative_to(repo_root)
        container_path = Path(REPO_ROOT).joinpath(root_relative)

        img_id = find_or_build_img(
            sync_strategy=RemoteSyncStrategy.IMAGE,
            command=img_command(str(container_path)),
            tag=f"model-{self.__class__.__name__.lower()}-{scm.sha()}",
            labels={
                MODEL_BASE_NAME_LABEL: "SupervisedModel",
                MODEL_PHASE_LABEL: self.phase().value,
                MODEL_NAME_LABEL: self.__class__.__name__,
                MODEL_VERSION_LABEL: scm.sha(),
                MODEL_X_DATA_LABEL: x.__name__,
                MODEL_X_DATA_SCHEMA_LABEL: json.dumps(x.json_schema()),
                MODEL_Y_DATA_LABEL: y.__name__,
                MODEL_Y_DATA_SCHEMA_LABEL: json.dumps(y.json_schema()),
                MODEL_PARAMS_SCHEMA_LABEL: json.dumps(self.json_schema()),
                MODEL_SERVER_PATH_LABEL: str(container_path),
                ENV_SHA_LABEL: scm.env_sha(),
                REPO_NAME_LABEL: scm.name(),
                REPO_SHA_LABEL: scm.sha(),
            },
        )

        if clean:
            os.remove(f"./{MODEL_PKL_FILE_NAME}")
            os.remove(server_filepath)

        return str(img_id)

    def deploy(
        cls,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
        **kwargs,
    ) -> SupervisedModelClient[X, Y]:
        """Create a deployment of the class, which will allow for the generation of instances remotely"""

        if "__orig_class__" in cls.__dict__:
            raise ValueError("not yet supported")

        if "__orig_bases__" in cls.__dict__:
            orig_bases = cls.__orig_bases__
            if len(orig_bases) == 0:
                raise ValueError("No X/Y was provided to base class")

            orig_class = orig_bases[0]
            args = typing.get_args(orig_class)
            x_cls: Type[X] = args[0]
            y_cls: Type[Y] = args[1]
        else:
            raise ValueError("orig_base not found and is needed")

        img_id = cls.base_image(scm, clean, dev_dependencies)
        return SupervisedModelClient[x_cls, y_cls](
            uri=img_id, sync_strategy=sync_strategy, dev_dependencies=dev_dependencies, **kwargs
        )

    @classmethod
    def develop(
        cls,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = True,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.CONTAINER,
        **kwargs,
    ) -> SupervisedModelClient[X, Y]:
        """Develop against the model remotely"""

        if "__orig_class__" in cls.__dict__:
            raise ValueError("not yet supported")

        if "__orig_bases__" in cls.__dict__:
            orig_bases = cls.__orig_bases__
            if len(orig_bases) == 0:
                raise ValueError("No X/Y was provided to base class")

            orig_class = orig_bases[0]
            args = typing.get_args(orig_class)
            x_cls: Type[X] = args[0]
            y_cls: Type[Y] = args[1]
        else:
            raise ValueError("orig_base not found and is needed")

        return SupervisedModelClient[x_cls, y_cls](
            model=cls, sync_strategy=sync_strategy, dev_dependencies=dev_dependencies, scm=scm, **kwargs
        )

    @classmethod
    def versions(
        cls: Type["SupervisedModel"], repositories: Optional[List[str]] = None, cfg: Optional[Config] = None
    ) -> List[str]:
        """Find all versions of this job

        Args:
            cls (Type[SupervisedJob]): the SupervisedJob class
            repositories (List[str], optional): extra repositories to check

        Returns:
            List[str]: A list of versions
        """

        if repositories is None:
            if cfg is None:
                cfg = Config()
            repositories = [f"{cfg.registry_url}/{cfg.image_repository}"]

        if repositories is None:
            # TODO: use current repository
            raise ValueError("must provide repositories to search")

        ret: List[str] = []
        for repo_uri in repositories:
            tags = get_repo_tags(repo_uri)

            for tag in tags:
                if f"model-{cls.__name__.lower()}" in tag:
                    ret.append(f"{repo_uri}:{tag}")
        return ret

    # TODO: generate a model template e.g. SupervisedModel[Image, Classes].gen()
    # should create a file normally or a cell in jupyter


class UnsupervisedModel(Generic[X], Model):
    @abstractmethod
    def compile(self, x: X) -> None:
        """Compile the model

        Args:
            x (X): Sample input
        """
        pass

    @abstractmethod
    def fit(self, x: X) -> Metrics:
        """Fit X

        Args:
            x (X): Input data
            y (Y): Expected output data
        """
        pass

    @abstractmethod
    def predict(self, x: X) -> Y:
        """Predict Y given X

        Args:
            x (X): Input

        Returns:
            Y: Prediction
        """
        pass


MultiClassImageClassifier = SupervisedModel[ImageData, ClassData]

from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import TextIOWrapper
from typing import Dict, Generic, Tuple, TypeVar, List, Any, Optional, Type, Union, get_args
import inspect
import time
import logging
import os
import socket
import json
from pathlib import Path
import typing
import uuid

from kubernetes import config
from kubernetes.stream import portforward
from kubernetes.client.models import (
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
)
from kubernetes.client import CoreV1Api, V1ObjectMeta, RbacAuthorizationV1Api
from docker.utils.utils import parse_repository_tag
from docker.auth import resolve_repository_name
from urllib import request

from arc.data.types import Data
from arc.kube.sync import copy_file_to_pod
from arc.model.types import ModelPhase, SupervisedModel, SupervisedModelClient
from arc.model.util import get_orig_class
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
from arc.kube.auth_util import ensure_cluster_auth_resources
from arc.client import get_client_id

X = TypeVar("X", bound="Data")
Y = TypeVar("Y", bound="Data")
O = TypeVar("O", bound="Opts")  # noqa: E741


PREDICTOR_LABEL = "predictor"
PREDICTOR_NAME_LABEL = "name"
PREDICTOR_VERSION_LABEL = "version"
PREDICTOR_BASE_NAME_LABEL = "base"
PREDICTOR_X_DATA_LABEL = "x"
PREDICTOR_X_DATA_SCHEMA_LABEL = "x-schema"
PREDICTOR_Y_DATA_LABEL = "y"
PREDICTOR_Y_DATA_SCHEMA_LABEL = "y-schema"
PREDICTOR_PARAMS_SCHEMA_LABEL = "params-schema"
PREDICTOR_SERVER_PATH_LABEL = "server-path"
OWNER_LABEL = "owner"
SERVER_PORT = "8080"
PREDICTOR_CONFIG_FILE_NAME = "config.json"
PREDICTOR_PKL_FILE_NAME = "model.pkl"
BUILD_MNT_DIR = "/mnt/build"


class PredictorClient(Generic[X, Y]):
    """A client for a predictor"""

    pod_name: str
    pod_namespace: str
    xcls: Optional[Type[X]] = None
    ycls: Optional[Type[Y]] = None
    uri: Optional[str] = None
    server_addr: str
    core_v1_api: CoreV1Api
    predictor_x_schema: str
    predictor_y_schema: str
    predictor_params_schema: str

    def __init__(
        self,
        uri: Optional[str] = None,
        predictor: Optional[Type["Predictor"]] = None,
        core_v1_api: Optional[CoreV1Api] = None,
        rbac_v1_api: Optional[RbacAuthorizationV1Api] = None,
        docker_socket: Optional[str] = None,
        namespace: Optional[str] = None,
        cfg: Optional[Config] = None,
        scm: Optional[SCM] = None,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
        dev_dependencies: bool = False,
        clean: bool = True,
        **kwargs,
    ) -> None:
        """A Predictor client

        Args:
            uri (Optional[str], optional): URI of the model. Defaults to None.
            predictor (Optional[Type[Predictor]], optional): Model to use. Defaults to None.
            core_v1_api (Optional[CoreV1Api], optional): CoreV1API to use. Defaults to None.
            rbac_v1_api (Optional[RbacAuthorizationV1Api], optional): RbacV1Api to use. Defaults to None.
            docker_socket (Optional[str], optional): Docker socket to use. Defaults to None.
            namespace (Optional[str], optional): Namespace to use. Defaults to None.
            cfg (Optional[Config], optional): Config to use. Defaults to None.
            scm (Optional[SCM], optional): SCM to use. Defaults to None.
            sync_strategy (RemoteSyncStrategy, optional): Sync strategy to use. Defaults to RemoteSyncStrategy.IMAGE.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            clean (bool, optional): Whether to clean the generated files. Defaults to True
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

        self.core_v1_api = core_v1_api

        # We need to get metadata on the model by looking at the registry and pulling metadata
        if docker_socket is None:
            docker_socket = default_socket()

        if cfg is None:
            cfg = Config()

        if scm is None:
            scm = SCM()

        if namespace is None:
            namespace = cfg.kube_namespace

        if predictor is not None:
            self.uri = predictor.base_image(
                scm=scm, dev_dependencies=dev_dependencies, clean=clean, sync_strategy=sync_strategy
            )

        # Check schema compatibility between client/server https://github.com/aunum/arc/issues/12
        img_labels = get_img_labels(self.uri)

        if img_labels is None:
            raise ValueError(f"image uri '{self.uri}' does not contain any labels, are you sure it was build by arc?")

        self.predictor_x_schema = img_labels[PREDICTOR_X_DATA_SCHEMA_LABEL]
        self.predictor_y_schema = img_labels[PREDICTOR_Y_DATA_SCHEMA_LABEL]
        self.predictor_params_schema = img_labels[PREDICTOR_PARAMS_SCHEMA_LABEL]
        self.server_path = img_labels[PREDICTOR_SERVER_PATH_LABEL]

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
            if PREDICTOR_LABEL in annotations and OWNER_LABEL in annotations:
                server_model_uri = annotations[PREDICTOR_LABEL]
                model_owner = annotations[OWNER_LABEL]
                if server_model_uri == self.uri:
                    if model_owner != get_client_id():
                        logging.warning("found model running in cluster but owner is not current user")
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
                        if predictor is None:
                            raise ValueError("job cannot be none when doing a container sync")
                        server_path = predictor.server_entrypoint()
                        logging.info(f"wrote server to path: {server_path}")
                        copy_file_to_pod(
                            scm.all_files(absolute_paths=True),
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
                        # it will just return the original verion, how do we sync the verion with
                        # the files to tell if its running?
                        # TODO! https://github.com/aunum/arc/issues/11
                        logging.info(self.info())
                    logging.info("returning")
                    return

        logging.info("model not found running, deploying now...")
        repository, tag = parse_repository_tag(self.uri)
        registry, repo_name = resolve_repository_name(repository)
        project_name = repo_name.split("/")[1]

        pod_name = f"{str(project_name).replace('/', '-')}-{tag}"

        if len(pod_name) > 57:
            pod_name = pod_name[:56]

        uid = str(uuid.uuid4())
        pod_name = pod_name + "-" + uid[:5]

        logging.info("ensuring cluster auth resources...")
        auth_resources = ensure_cluster_auth_resources(core_v1_api, rbac_v1_api, docker_socket, namespace, cfg)

        if params is not None:
            cfg = V1ConfigMap(
                metadata=V1ObjectMeta(name=pod_name, namespace=namespace), data={"cfg": json.dumps(params)}
            )
            core_v1_api.create_namespaced_config_map(namespace, cfg)

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
            env=[V1EnvVar(name="PREDICTOR_URI", value=self.uri)],
        )
        container.volume_mounts = [
            V1VolumeMount(name="build", mount_path=BUILD_MNT_DIR),
            V1VolumeMount(name="dockercfg", mount_path="/root/.docker"),
        ]
        if params is not None:
            container.volume_mounts.append(
                V1VolumeMount(name="config", mount_path=REPO_ROOT, sub_path=PREDICTOR_CONFIG_FILE_NAME)
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
                    REPO_SHA_LABEL: scm.sha(),
                    ENV_SHA_LABEL: scm.env_sha(),
                    REPO_NAME_LABEL: scm.name(),
                    SYNC_STRATEGY_LABEL: str(sync_strategy),
                },
                annotations={
                    PREDICTOR_LABEL: self.uri,
                    OWNER_LABEL: get_client_id(),
                    PREDICTOR_X_DATA_LABEL: img_labels[PREDICTOR_X_DATA_LABEL],
                    PREDICTOR_Y_DATA_LABEL: img_labels[PREDICTOR_Y_DATA_LABEL],
                    PREDICTOR_SERVER_PATH_LABEL: img_labels[PREDICTOR_SERVER_PATH_LABEL],
                    PREDICTOR_X_DATA_SCHEMA_LABEL: self.predictor_x_schema,
                    PREDICTOR_Y_DATA_SCHEMA_LABEL: self.predictor_y_schema,
                    PREDICTOR_PARAMS_SCHEMA_LABEL: self.predictor_params_schema,
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

        # TODO: handle readiness https://github.com/aunum/arc/issues/11
        time.sleep(10)

        self.server_addr = f"http://{pod_name}.pod.{namespace}.kubernetes:{SERVER_PORT}"
        self.pod_name = pod_name
        self.pod_namespace = namespace

        logging.info(f"server info: {self.info()}")

        if sync_strategy == RemoteSyncStrategy.CONTAINER:
            logging.info("syncing files to model container")
            if predictor is None:
                raise SystemError("cannot sync files to a container without a model parameter passed in init")
            server_path = predictor.server_entrypoint()
            logging.info(f"wrote server to path: {server_path}")
            copy_file_to_pod(
                scm.all_files(absolute_paths=True),
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
            # TODO! https://github.com/aunum/arc/issues/11
            logging.info(self.info())
        return

    def validate(self) -> None:
        """Validate the client and server schema are compatible"""

        raise NotImplementedError()

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

    def io(self) -> Tuple[Optional[X], Optional[Y]]:
        """Get IO for model; if compiled

        Returns:
            Tuple[X, Y]: X and Y for the model
        """
        req = request.Request(f"{self.server_addr}/io")
        resp = request.urlopen(req)
        resp_data = resp.read().decode("utf-8")

        if self.ycls is None:
            orig = get_orig_class(self)
            self.xcls, self.ycls = orig.__args__

        jdict = json.loads(resp_data)
        if jdict["x"] is None or jdict["y"] is None:
            return (None, None)

        x = self.xcls.load_dict(jdict["x"])  # type: ignore
        y = self.ycls.load_dict(jdict["y"])
        return (x, y)

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

    def delete(self) -> None:
        """Delete the model"""

        self.core_v1_api.delete_namespaced_pod(self.pod_name, self.pod_namespace)

    @classmethod
    def find(cls) -> List["PredictorClient"]:
        """Find all the models that could be deployed (or are running) that we could find,
        should show with the metrics"""
        raise NotImplementedError()


class Predictor(Generic[X, Y], ABC):
    """Prediction interface for one or many models"""

    @abstractmethod
    def predict(self, x: X) -> Y:
        """Predict Y given X

        Args:
            x (X): X to predict

        Returns:
            Y: predicted Y
        """
        pass

    @classmethod
    def name(cls) -> str:
        """Short name for the predictor

        Returns:
            str: Short name for the predictor
        """
        return cls.__name__

    @classmethod
    def short_name(cls) -> str:
        """Short name for the predictor

        Returns:
            str: Short name for the predictor
        """
        return cls.__name__.lower()

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
        # cls_dir = os.path.dirname(os.path.realpath(str(cls_file_path)))
        server_file_name = f"{cls.short_name().lower()}_server.py"

        server_file = f"""
import json
import logging
from typing import Any, Dict
from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import time

from simple_parsing import ArgumentParser
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.schemas import SchemaGenerator
import uvicorn

from arc.data.encoding import ShapeEncoder
from arc.scm import SCM
from arc.image.build import REPO_ROOT, build_containerfile
from arc.image.file import write_containerfile
from arc.model.types import BUILD_MNT_DIR

from {cls_file} import {cls.__name__}
from {cls_file} import *
from {mod_x} import {x.__name__}
from {mod_y} import {y.__name__}

logging.basicConfig(level=logging.INFO)

parser = ArgumentParser()
parser.add_arguments({cls_name}.opts(), dest="{cls_name.lower()}")

args = parser.parse_args()

cfg_file = Path("./config.json")

scm = SCM()

last_used_ts = time.time()

if cfg_file.is_file():
    predictor = {cls.__name__}.load_json("./{PREDICTOR_CONFIG_FILE_NAME}")
else:
    predictor = {cls.__name__}.from_opts(args.{cls_name.lower()})

uri = os.getenv("PREDICTOR_URI")
predictor.uri = uri


app = Starlette(debug=True)

schemas = SchemaGenerator(
    {{"openapi": "3.0.0", "info": {{"title": "{cls_name}", "version": "{version}"}}}}
)


def update_ts():
    global last_used_ts
    last_used_ts = time.time()


@app.route("/last_used")
def last_used(request):
    return JSONResponse({{"elapsed": time.time() - last_used_ts}})


@app.route("/health")
def health(request):
    return JSONResponse({{"status": "alive"}})


@app.route("/info")
def info(request):
    # model_dict = model.opts().to_dict()
    return JSONResponse({{"name": predictor.name(), "version": scm.sha(), "env-sha": scm.env_sha(), "uri": uri}})


@app.route("/io")
def io(request):
    update_ts()
    x, y = predictor.io()
    if x is None or y is None:
        return JSONResponse({{"x": None, "y": None}})
    resp = {{"x": x.repr_json(), "y": y.repr_json()}}
    return JSONResponse(resp)


class ShapeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(content, cls=ShapeEncoder).encode('utf-8')


@app.route("/predict", methods=["POST"])
async def predict(request):
    update_ts()
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
        """  # noqa: E501

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

        if sync_strategy == RemoteSyncStrategy.IMAGE:
            img_id = find_or_build_img(
                sync_strategy=RemoteSyncStrategy.IMAGE,
                command=img_command(str(container_path)),
                tag_prefix=f"predictor-{cls.short_name().lower()}",
                labels={
                    PREDICTOR_BASE_NAME_LABEL: "Predictor",
                    PREDICTOR_NAME_LABEL: cls.__name__,
                    PREDICTOR_VERSION_LABEL: scm.sha(),
                    PREDICTOR_X_DATA_LABEL: x.__name__,
                    PREDICTOR_X_DATA_SCHEMA_LABEL: json.dumps(x.json_schema()),
                    PREDICTOR_Y_DATA_LABEL: y.__name__,
                    PREDICTOR_Y_DATA_SCHEMA_LABEL: json.dumps(y.json_schema()),
                    PREDICTOR_PARAMS_SCHEMA_LABEL: json.dumps(cls.opts().json_schema()),
                    PREDICTOR_SERVER_PATH_LABEL: str(container_path),
                    ENV_SHA_LABEL: scm.env_sha(),
                    REPO_NAME_LABEL: scm.name(),
                    REPO_SHA_LABEL: scm.sha(),
                },
                dev_dependencies=dev_dependencies,
                clean=clean,
            )
        elif sync_strategy == RemoteSyncStrategy.CONTAINER:
            img_id = find_or_build_img(
                sync_strategy=RemoteSyncStrategy.IMAGE,  # TODO: fix this at the source, we want to copy all files now
                command=img_command(str(container_path)),
                tag=f"predictor-{cls.short_name().lower()}-{scm.env_sha()}",
                labels={
                    PREDICTOR_BASE_NAME_LABEL: "Predictor",
                    PREDICTOR_NAME_LABEL: cls.__name__,
                    PREDICTOR_VERSION_LABEL: scm.sha(),
                    PREDICTOR_X_DATA_LABEL: x.__name__,
                    PREDICTOR_X_DATA_SCHEMA_LABEL: json.dumps(x.json_schema()),
                    PREDICTOR_Y_DATA_LABEL: y.__name__,
                    PREDICTOR_Y_DATA_SCHEMA_LABEL: json.dumps(y.json_schema()),
                    PREDICTOR_PARAMS_SCHEMA_LABEL: json.dumps(cls.opts().json_schema()),
                    PREDICTOR_SERVER_PATH_LABEL: str(container_path),
                    ENV_SHA_LABEL: scm.env_sha(),
                    REPO_NAME_LABEL: scm.name(),
                    REPO_SHA_LABEL: scm.sha(),
                },
                dev_dependencies=dev_dependencies,
                clean=clean,
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
            tag=f"predictor-{self.short_name().lower()}-{scm.sha()}",
            labels={
                PREDICTOR_BASE_NAME_LABEL: "Predictor",
                PREDICTOR_NAME_LABEL: self.__class__.__name__,
                PREDICTOR_VERSION_LABEL: scm.sha(),
                PREDICTOR_X_DATA_LABEL: x.__name__,
                PREDICTOR_X_DATA_SCHEMA_LABEL: json.dumps(x.json_schema()),
                PREDICTOR_Y_DATA_LABEL: y.__name__,
                PREDICTOR_Y_DATA_SCHEMA_LABEL: json.dumps(y.json_schema()),
                PREDICTOR_PARAMS_SCHEMA_LABEL: json.dumps(self.json_schema()),
                PREDICTOR_SERVER_PATH_LABEL: str(container_path),
                ENV_SHA_LABEL: scm.env_sha(),
                REPO_NAME_LABEL: scm.name(),
                REPO_SHA_LABEL: scm.sha(),
            },
            clean=clean,
        )

        if clean:
            os.remove(server_filepath)

        return str(img_id)

    def deploy(
        cls,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
        **kwargs,
    ) -> PredictorClient[X, Y]:
        """Create a deployment of the class, which will allow for the generation of instances remotely"""

        if "__orig_class__" in cls.__dict__:
            raise ValueError("not yet supported")

        if "__orig_bases__" in cls.__dict__:
            orig_bases = cls.__orig_bases__  # type: ignore
            if len(orig_bases) == 0:
                raise ValueError("No X/Y was provided to base class")

            orig_class = orig_bases[0]
            args = get_args(orig_class)
            x_cls: Type[X] = args[0]
            y_cls: Type[Y] = args[1]
        else:
            raise ValueError("orig_base not found and is needed")

        img_id = cls.base_image(scm, clean, dev_dependencies)
        return PredictorClient[x_cls, y_cls](  # type: ignore
            uri=img_id, sync_strategy=sync_strategy, clean=clean, dev_dependencies=dev_dependencies, **kwargs
        )

    @classmethod
    def develop(
        cls,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = True,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.CONTAINER,
        **kwargs,
    ) -> PredictorClient[X, Y]:
        """Develop against the model remotely"""

        if "__orig_class__" in cls.__dict__:
            raise ValueError("not yet supported")

        if "__orig_bases__" in cls.__dict__:
            orig_bases = cls.__orig_bases__  # type: ignore
            if len(orig_bases) == 0:
                raise ValueError("No X/Y was provided to base class")

            orig_class = orig_bases[0]
            args = typing.get_args(orig_class)
            x_cls: Type[X] = args[0]
            y_cls: Type[Y] = args[1]
        else:
            raise ValueError("orig_base not found and is needed")

        return PredictorClient[x_cls, y_cls](  # type: ignore
            model=cls, sync_strategy=sync_strategy, clean=clean, dev_dependencies=dev_dependencies, scm=scm, **kwargs
        )

    @classmethod
    def versions(
        cls: Type["Predictor"], repositories: Optional[List[str]] = None, cfg: Optional[Config] = None
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
            repositories = [cfg.image_repo]

        if repositories is None:
            # TODO: use current repository
            raise ValueError("must provide repositories to search")

        ret: List[str] = []
        for repo_uri in repositories:
            tags = get_repo_tags(repo_uri)

            for tag in tags:
                if f"predictor-{cls.__name__.lower()}" in tag:
                    ret.append(f"{repo_uri}:{tag}")
        return ret


class Recorder(Generic[X, Y]):
    """Record model predictions and feedback"""

    @abstractmethod
    def record(self, x: X, y_pred: Y) -> None:
        """Record model predictions

        Args:
            x (X): X input
            y_pred (Y): Y prediction
        """
        pass

    @abstractmethod
    def feedback(self, x: X, y_true: Y) -> None:
        """Record model predictions

        Args:
            x (X): X input
            y_true (Y): Y true
        """
        pass


class FileRecorder(Recorder[X, Y]):
    """Record results to a file"""

    dir: str
    _preds_handler: TextIOWrapper
    _feedback_handler: TextIOWrapper

    def __init__(self, dir: str = "./recorder") -> None:
        self.dir = dir
        current_time = str(time.time())
        self._preds_handler = open(os.path.join(dir, "predictions", f"{current_time}.json"))
        self._feedback_handler = open(os.path.join(dir, "feedback", f"{current_time}.json"))

    def record(self, x: X, y_pred: Y) -> None:
        """Record model predictions

        Args:
            x (X): X input
            y_pred (Y): Y prediction
        """
        self._preds_handler.write(json.dumps({"x": x.repr_json(), "y": y_pred.repr_json(), "time": time.time()}))

    def feedback(self, x: X, y_true: Y) -> None:
        """Record model predictions

        Args:
            x (X): X input
            y_true (Y): Y true
        """
        self._feedback_handler.write(
            json.dumps({"x": x.repr_json(), "y_true": y_true.repr_json(), "time": time.time()})
        )


@dataclass
class ModelRoutePortion(Generic[X, Y]):
    """A proportion that a model should be routed to"""

    model: Union[
        SupervisedModel[X, Y],
        SupervisedModelClient[X, Y],
    ]
    portion: int
    shadow: bool


class ProportionRouter(Predictor[X, Y]):
    """Route to models based on proportions"""

    routes: List[ModelRoutePortion]

    _count: Dict[str, int]
    _count_total: int
    _proportion_total: int
    _proportions: Dict[str, int]
    _recorder: Recorder[X, Y]

    def __init__(
        self,
        routes: List[ModelRoutePortion[X, Y]],
        recorder: Recorder[X, Y],
    ) -> None:

        self.update(routes)
        self._recorder = recorder

    def update(self, routes: List[ModelRoutePortion]) -> None:
        """Update the routes

        Args:
            routes (List[ModelRoutePortion]): Routes to use
        """

        # TODO how do we use this remote?
        self.routes = routes

        for route in routes:
            self._proportion_total += route.portion

        for route in routes:
            self._proportions[route.model.uri] = route.portion / self._proportion_total

        self._count = {}

    def predict(self, x: X) -> Y:
        """Predict Y given X

        Args:
            x (X): X to predict

        Returns:
            Y: predicted Y
        """
        self._count_total = 0
        for _, count in self._count.items():
            self._count_total += count

        max_delta = 0
        chosen_uri = ""
        current_proportions: Dict[str, int] = {}
        for uri, count in self._count.items():
            current_proportion = count / self._count_total
            current_proportions[uri] = current_proportion
            designated_proportion = self._proportions[uri]
            delta = designated_proportion - current_proportion
            if delta > max_delta:
                max_delta = delta
                chosen_uri = uri

        logging.info(f"using chosen uri '{chosen_uri}' with a delta of {max_delta}")
        y: Y = None
        for route in self.routes:
            if route.model.uri == chosen_uri:
                y = route.model.predict(x)
                self._recorder.record(x, y)
                continue

            if route.shadow:
                y_shadow = route.model.predict(x)
                logging.info(f"shadow response from model: {y_shadow}")

                self._recorder.record(x, y_shadow)

        return y

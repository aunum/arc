from abc import abstractmethod
import shutil
from typing import List, Dict, Any, Type, Optional
from urllib import parse, request
import json
import socket
from simple_parsing import ArgumentParser

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, JSONResponse
from starlette.routing import Route
from starlette.schemas import SchemaGenerator
import uvicorn

from arc.scm import SCM

from abc import ABC, abstractmethod
from dataclasses import dataclass, is_dataclass, make_dataclass, field
from enum import Enum
from typing import Dict, Generic, Tuple, TypeVar, List, Any, Optional, Type, Union
import inspect
import time
import logging
import os
import socket
import json
import yaml
from pathlib import Path
import typing
import uuid

import cloudpickle as pickle
from dataclasses_jsonschema import JsonSchemaMixin, T
from simple_parsing.helpers import Serializable
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
    V1PodStatus,
    V1ContainerStatus,
    V1ContainerState,
    V1ContainerStateRunning,
    V1ContainerStateTerminated,
    V1ContainerStateWaiting,
    V1EnvVarSource,
    V1ObjectFieldSelector,
)
from kubernetes.client import CoreV1Api, V1ObjectMeta, RbacAuthorizationV1Api
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
from arc.kube.auth_util import ensure_cluster_auth_resources
from arc.image.build import img_id
from arc.client import get_client_id
from arc.kube.uri import parse_k8s_uri, make_k8s_uri


SERVER_PORT = "8080"
NAME_LABEL = "name"
VERSION_LABEL = "version"
BASES_LABEL = "base"
PARAMS_SCHEMA_LABEL = "params-schema"
SERVER_PATH_LABEL = "server-path"
OWNER_LABEL = "owner"
SERVER_PORT = "8080"
CONFIG_FILE_NAME = "config.json"
BUILD_MNT_DIR = "/mnt/build"
ARTIFACT_TYPE_LABEL = "artifact-type"


class APIUtil(JsonSchemaMixin):
    @classmethod
    def from_yaml(cls: Type[T], data: Union[str, bytes], validate: bool = True, **yaml_kwargs) -> T:
        return cls.from_dict(yaml.load(data, **yaml_kwargs), validate)

    def to_yaml(self, omit_none: bool = True, validate: bool = False, **yaml_kwargs) -> str:
        return yaml.dump(self.to_dict(omit_none, validate), **yaml_kwargs)


@dataclass
class RunningServer:
    uri: str
    k8s_uri: str


class Client:
    def provision(
        self,
        uri: Optional[str] = None,
        server: Optional[Type["Server"]] = None,
        reuse: bool = True,
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

        if uri is not None and uri.startswith("k8s://"):
            self.pod_namespace, self.pod_name = parse_k8s_uri(uri)
            self.server_addr = f"http://{self.pod_name}.pod.{self.pod_namespace}.kubernetes:{SERVER_PORT}"
            logging.info(f"connecting directly to pod {self.pod_name} in namespace {self.pod_namespace}")
            info = self.info()
            logging.info(f"server info: {info}")
            self.uri = info["uri"]
            return

        if server is not None:
            self.uri = server.base_image(
                scm=scm, dev_dependencies=dev_dependencies, clean=clean, sync_strategy=sync_strategy
            )

        # Check schema compatibility between client/server https://github.com/aunum/arc/issues/12
        img_labels = get_img_labels(self.uri)

        if img_labels is None:
            raise ValueError(f"image uri '{self.uri}' does not contain any labels, are you sure it was build by arc?")

        self.model_x_schema = img_labels[MODEL_X_DATA_SCHEMA_LABEL]
        self.model_y_schema = img_labels[MODEL_Y_DATA_SCHEMA_LABEL]
        self.model_params_schema = img_labels[MODEL_PARAMS_SCHEMA_LABEL]
        self.server_path = img_labels[SERVER_PATH_LABEL]
        self.model_phase = img_labels[MODEL_PHASE_LABEL]

        # check if container exists
        if reuse:
            logging.info("checking if model is already running in cluster")
            pod_list: V1PodList = core_v1_api.list_namespaced_pod(namespace)
            for pod in pod_list.items:
                annotations = pod.metadata.annotations
                pod_name = pod.metadata.name
                if annotations is None:
                    continue
                if MODEL_LABEL in annotations and OWNER_LABEL in annotations:
                    server_model_uri = annotations[MODEL_LABEL]
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
                            if model is None:
                                raise ValueError("job cannot be none when doing a container sync")
                            server_path = model.server_entrypoint()
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

        logging.info("creating model in cluster")
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
            env=[
                V1EnvVar(
                    name="POD_NAME",
                    value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path="metadata.name")),
                ),
                V1EnvVar(
                    name="POD_NAMESPACE",
                    value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path="metadata.namespace")),
                ),
                V1EnvVar(name="MODEL_URI", value=self.uri),
            ],
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
                    OWNER_LABEL: get_client_id(),
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

        # TODO: handle readiness https://github.com/aunum/arc/issues/11
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

    def info(self) -> Dict[str, Any]:
        """Info about the server

        Returns:
            Dict[str, Any]: Server info
        """
        req = request.Request(f"{self.server_addr}/info")
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        return json.loads(data)

    def health(self) -> Dict[str, Any]:
        """Health of the server

        Returns:
            Dict[str, Any]: Server health
        """
        req = request.Request(f"{self.server_addr}/health")
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

    def load(self, dir: str = "./artifacts") -> None:
        """Load the object

        Args:
            dir (str, optional): Directory to load from. Defaults to "./artifacts".
        """

        params = json.dumps({"dir": dir}).encode("utf8")
        req = request.Request(f"{self.server_addr}/load", data=params, headers={"content-type": "application/json"})
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        logging.info(jdict)
        return

    def delete(self) -> None:
        """Delete the model"""

        self.core_v1_api.delete_namespaced_pod(self.pod_name, self.pod_namespace)

    @classmethod
    def find(cls) -> List["Client"]:
        """Find all the models that could be deployed (or are running) that we could find,
        should show with the metrics"""
        raise NotImplementedError()

    def k8s_uri(self) -> str:
        """K8s URI for the model

        Returns:
            str: K8s URI for the model
        """
        if self.pod_name == "" or self.pod_namespace == "":
            raise ValueError("no pod name or namespace for client")

        return make_k8s_uri(self.pod_name, self.pod_namespace)

    def copy(self, core_v1_api: Optional[CoreV1Api] = None) -> RunningServer:
        """Copy the model

        Args:
            core_v1_api (Optional[CoreV1Api], optional): CoreV1Api to sue. Defaults to None.

        Returns:
            RunningModel: A running server
        """
        params = json.dumps({}, cls=ShapeEncoder).encode("utf8")
        req = request.Request(f"{self.server_addr}/copy", data=params, headers={"content-type": "application/json"})
        resp = request.urlopen(req)
        resp_data = resp.read().decode("utf-8")

        jdict = json.loads(resp_data)
        return RunningServer(uri=jdict["uri"], k8s_uri=jdict["k8s_uri"])

    # def save(
    #     self,
    #     version: Optional[str] = None,
    #     core_v1_api: Optional[CoreV1Api] = None,
    # ) -> str:  # TODO: make this a generator
    #     """Save the model

    #     Args:
    #         version (Optional[str], optional): Version to use. Defaults to repo version.
    #         core_v1_api (Optional[CoreV1Api], optional): CoreV1API to use. Defaults to None.

    #     Returns:
    #         str: URI of the saved model
    #     """
    #     if core_v1_api is None:
    #         if is_k8s_proc():
    #             config.load_incluster_config()
    #         else:
    #             config.load_kube_config()

    #         core_v1_api = CoreV1Api()

    #     logging.info("saving model...")

    #     req = request.Request(f"{self.server_addr}/save", method="POST")
    #     resp = request.urlopen(req)
    #     body = resp.read().decode("utf-8")

    #     _, tag = parse_repository_tag(self.uri)
    #     # registry, repo_name = resolve_repository_name(repository)
    #     # docker_secret = get_dockercfg_secret_name()

    #     cls_name = tag.split("-")[1]

    #     info = self.info()
    #     version = info["version"]
    #     uri = img_id(RemoteSyncStrategy.IMAGE, tag=f"model-{cls_name}-{version}")

    #     path_params = {"name": self.pod_name, "namespace": self.pod_namespace}

    #     query_params = []  # type: ignore
    #     header_params = {}

    #     form_params = []  # type: ignore
    #     local_var_files = {}  # type: ignore

    #     header_params["Accept"] = "application/json"
    #     header_params["Content-Type"] = "application/strategic-merge-patch+json"

    #     # Authentication setting
    #     auth_settings = ["BearerToken"]  # noqa: E501

    #     _pod: V1Pod = core_v1_api.read_namespaced_pod(self.pod_name, self.pod_namespace)
    #     labels: Dict[str, str] = _pod.metadata.labels
    #     annotations: Dict[str, str] = _pod.metadata.annotations

    #     body = {
    #         "spec": {
    #             "ephemeralContainers": [
    #                 {
    #                     "name": f"snapshot-{int(time.time())}",
    #                     "args": [
    #                         f"--context={REPO_ROOT}",
    #                         f"--destination={uri}",
    #                         "--dockerfile=Dockerfile.arc",
    #                         "--ignore-path=/product_uuid",  # https://github.com/GoogleContainerTools/kaniko/issues/2164
    #                         f"--label={BASE_NAME_LABEL}=SupervisedModel",
    #                         f"--label={MODEL_PHASE_LABEL}={info['phase']}",
    #                         f"--label={MODEL_NAME_LABEL}={info['name']}",
    #                         f"--label={MODEL_VERSION_LABEL}={info['version']}",
    #                         f"--label={MODEL_X_DATA_LABEL}={annotations[MODEL_X_DATA_LABEL]}",
    #                         f"--label={MODEL_Y_DATA_LABEL}={annotations[MODEL_Y_DATA_LABEL]}",
    #                         f"--label={MODEL_X_DATA_SCHEMA_LABEL}={annotations[MODEL_X_DATA_SCHEMA_LABEL]}",
    #                         f"--label={MODEL_Y_DATA_SCHEMA_LABEL}={annotations[MODEL_Y_DATA_SCHEMA_LABEL]}",
    #                         f"--label={MODEL_PARAMS_SCHEMA_LABEL}={annotations[MODEL_PARAMS_SCHEMA_LABEL]}",
    #                         f"--label={MODEL_SERVER_PATH_LABEL}={annotations[MODEL_SERVER_PATH_LABEL]}",
    #                         f"--label={ENV_SHA_LABEL}={info['env-sha']}",
    #                         f"--label={REPO_NAME_LABEL}={labels[REPO_NAME_LABEL]}",
    #                         f"--label={REPO_SHA_LABEL}={info['version']}",
    #                     ],
    #                     "image": "gcr.io/kaniko-project/executor:latest",
    #                     "volumeMounts": [
    #                         {"mountPath": "/kaniko/.docker/", "name": "dockercfg"},
    #                         {"mountPath": REPO_ROOT, "name": "build"},
    #                     ],
    #                 }
    #             ]
    #         }
    #     }

    #     core_v1_api.api_client.call_api(
    #         "/api/v1/namespaces/{namespace}/pods/{name}/ephemeralcontainers",
    #         "PATCH",
    #         path_params,
    #         query_params,
    #         header_params,
    #         body,
    #         post_params=form_params,
    #         files=local_var_files,
    #         response_type="V1Pod",  # noqa: E501
    #         auth_settings=auth_settings,
    #     )

    #     logging.info("snapshotting image...")

    #     done = False

    #     while not done:
    #         pod: V1Pod = core_v1_api.read_namespaced_pod(self.pod_name, self.pod_namespace)
    #         status: V1PodStatus = pod.status

    #         if status.ephemeral_container_statuses is None:
    #             time.sleep(1)
    #             logging.info("ephemeral container status is None")
    #             continue

    #         for container_status in status.ephemeral_container_statuses:
    #             st: V1ContainerStatus = container_status
    #             state: V1ContainerState = st.state

    #             if state.running is not None:
    #                 running: V1ContainerStateRunning = state.running
    #                 logging.info(f"snapshot is running: {running}")

    #             if state.terminated is not None:
    #                 terminated: V1ContainerStateTerminated = state.terminated
    #                 logging.info(f"snapshot is terminated: {terminated}")
    #                 if terminated.exit_code != 0:
    #                     raise SystemError(
    #                         f"unable to snapshot image - reason: {terminated.reason} message: {terminated.message}"
    #                     )
    #                 done = True

    #             if state.waiting is not None:
    #                 waiting: V1ContainerStateWaiting = state.waiting
    #                 logging.info(f"snapshot is waiting: {waiting}")

    #         time.sleep(1)

    #     return str(uri)


class Server(ABC, APIUtil):
    """A server that can be built and ran remotely"""

    last_used_ts: float
    scm: SCM
    schemas: SchemaGenerator

    @classmethod
    def create_from_env(cls) -> "Server":
        parser = ArgumentParser()
        parser.add_arguments(cls.opts(), dest="server")

        args = parser.parse_args()

        artifact_file = Path(f"./artifacts/{cls.short_name()}.pkl")
        cfg_file = Path("./config.json")

        if artifact_file.is_file():
            logging.info("loading srv artifact found locally")
            srv: "Server" = cls.load()
        elif cfg_file.is_file():
            logging.info("loading srv from config file")
            srv = cls.load_json(f"./{CONFIG_FILE_NAME}")  # type: ignore
        else:
            logging.info("loading srv from args")
            srv = cls.from_opts(args.server)

        uri = os.getenv("MODEL_URI")
        if uri is None:
            logging.warning("$MODEL_URI var not found, defaulting to class uri")
        else:
            srv.uri = uri

        srv.last_used_ts = time.time()
        srv.scm = SCM()

        return srv

    def info_req(self, request):
        return JSONResponse(
            {"name": self.__class__.__name__, "version": self.scm().sha(), "env-sha": self.scm().env_sha()}
        )

    def health_req(self, request):
        return JSONResponse({"health": "ok"})

    @classmethod
    def routes(cls) -> List[Route]:
        return [
            Route("/info", endpoint=cls.info_req),
            Route("/health", endpoint=cls.health_req),
            Route("/schema", endpoint=cls._schema_req),
        ]

    @classmethod
    def client_cls(cls) -> Type[Client]:
        return Client

    @classmethod
    def server_entrypoint(cls, scm: Optional[SCM] = None) -> str:

        obj_module = inspect.getmodule(cls)
        if obj_module is None:
            raise SystemError(f"could not find module for func {obj_module}")

        if scm is None:
            scm = SCM()

        cls_file_path = Path(inspect.getfile(cls))
        cls_file = cls_file_path.stem
        server_file_name = f"{cls.short_name().lower()}_server.py"

        server_file = f"""
import logging

from {cls_file} import {cls.__name__}
from {cls_file} import *

logging.basicConfig(level=logging.INFO)

{cls.__name__}.create_from_env().serve()
        """  # noqa: E501

        class_file = inspect.getfile(cls)
        dir_path = os.path.dirname(os.path.realpath(class_file))
        server_filepath = os.path.join(dir_path, server_file_name)
        with open(server_filepath, "w") as f:
            f.write(server_file)
        return server_filepath

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @classmethod
    def short_name(cls) -> str:
        return cls.__name__.lower()

    def save(self, out_dir: str = "./artifacts") -> None:
        """Save the object

        Args:
            out_dir (str, optional): Directory to output the artiacts. Defaults to "./artifacts".
        """
        out_path = os.path.join(out_dir, f"{self.short_name()}.pkl")
        with open(out_path, "wb") as f:
            pickle.dump(self, f)
        return

    @classmethod
    def load(cls, dir: str = "./artifacts") -> "Server":
        """Load the object

        Args:
            dir (str): Directory to the artifacts
        """
        # https://stackoverflow.com/questions/52591862/how-can-i-save-an-object-containing-keras-models
        path = os.path.join(dir, f"{cls.short_name()}.pkl")
        with open(path, "rb") as f:
            return pickle.load(f)

    @classmethod
    def clean_artifacts(cls, dir: str = "./artifacts") -> None:
        shutil.rmtree(dir)

    @classmethod
    def opts(cls: Type["Server"]) -> Opts:
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
                    (
                        param,
                        sig.parameters[param].annotation,
                        field(default=sig.parameters[param].default),
                    )  # type: ignore
                )

        return make_dataclass(cls.__name__ + "Opts", fin_params, bases=(Serializable, JsonSchemaMixin))

    @abstractmethod
    @classmethod
    def artifact_type(cls) -> str:
        pass

    @property
    def uri(self) -> str:
        if self._uri is None:
            return f"{self.__module__}.{self.__class__.__name__}"
        return self._uri

    @uri.setter
    def uri(self, val: str):
        self._uri = val

    def _update_ts(self):
        self.last_used_ts = time.time()

    def deploy(
        cls,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
        **kwargs,
    ) -> Client:
        """Create a deployment of the class, which will allow for the generation of instances remotely"""
        imgid = cls.base_image(scm, clean, dev_dependencies)
        return cls.client_cls()(  # type: ignore
            uri=imgid, sync_strategy=sync_strategy, clean=clean, scm=scm, dev_dependencies=dev_dependencies, **kwargs
        )

    @classmethod
    def develop(
        cls,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        reuse: bool = True,
        **kwargs,
    ) -> Client:
        """Create a deployment of the class, which will allow for the generation of instances remotely"""
        return cls.client_cls()(  # type: ignore
            server=cls,
            sync_strategy=RemoteSyncStrategy.CONTAINER,
            clean=clean,
            reuse=reuse,
            dev_dependencies=dev_dependencies,
            scm=scm,
            **kwargs,
        )

    @classmethod
    def base_image(
        cls,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
    ) -> str:
        """Create a server image from the model class that can be used to create models from scratch"""

        return cls.build_image(
            cls.artifact_type(), scm=scm, clean=clean, dev_dependencies=dev_dependencies, sync_strategy=sync_strategy
        )

    def image(self, scm: Optional[SCM] = None, dev_dependencies: bool = False, clean: bool = True) -> str:
        """Create a server image with the saved model"""

        if scm is None:
            scm = SCM()

        self.save()

        uri = self.build_image(
            self.artifact_type(),
            scm=scm,
            clean=clean,
            dev_dependencies=dev_dependencies,
            sync_strategy=RemoteSyncStrategy.IMAGE,
        )
        if clean:
            self.clean_artifacts()

        return uri

    @classmethod
    def build_image(
        cls,
        artifact_type: str,
        labels: Optional[Dict[str, str]] = None,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
    ) -> str:
        """Build a generic image for a server"""

        if scm is None:
            scm = SCM()
        # write the server file somewhere we can find it
        server_filepath = Path(cls.server_entrypoint())
        repo_root = Path(str(scm.git_repo.working_dir))
        root_relative = server_filepath.relative_to(repo_root)
        container_path = Path(REPO_ROOT).joinpath(root_relative)

        bases = inspect.getmro(cls)
        base_names = []
        for base in bases:
            base_names.append(base.__name__)

        base_labels = {
            BASES_LABEL: json.dumps(base_names),
            NAME_LABEL: cls.__name__,
            VERSION_LABEL: scm.sha(),
            PARAMS_SCHEMA_LABEL: json.dumps(cls.opts().json_schema()),
            SERVER_PATH_LABEL: str(container_path),
            ENV_SHA_LABEL: scm.env_sha(),
            REPO_NAME_LABEL: scm.name(),
            REPO_SHA_LABEL: scm.sha(),
        }
        if labels is not None:
            base_labels.update(labels)

        if sync_strategy == RemoteSyncStrategy.IMAGE:
            imgid = find_or_build_img(
                sync_strategy=RemoteSyncStrategy.IMAGE,
                command=img_command(str(container_path)),
                tag_prefix=f"{artifact_type.lower()}-{cls.short_name().lower()}",
                labels=labels,
                dev_dependencies=dev_dependencies,
                clean=clean,
            )
        elif sync_strategy == RemoteSyncStrategy.CONTAINER:
            imgid = find_or_build_img(
                sync_strategy=RemoteSyncStrategy.IMAGE,  # TODO: fix this at the source, we want to copy all files now
                command=img_command(str(container_path)),
                tag=f"{artifact_type.lower()}env-{cls.short_name().lower()}-{scm.env_sha()}",
                labels=labels,
                dev_dependencies=dev_dependencies,
                clean=clean,
            )
        if clean:
            os.remove(server_filepath)

        return str(imgid)

    @classmethod
    def from_opts(cls: Type["Server"], opts: Opts) -> "Server":
        return cls(**opts.__dict__)

    def serve(self, port: int = 8080, log_level: str = "info", reload: bool = True) -> None:
        """Serve the class

        Args:
            port (int, optional): Port to serve one. Defaults to 8080.
            log_level (str, optional): Log level. Defaults to "info".
            reload (bool, optional): Whether to hot reload. Defaults to True.
        """
        routes = self.routes()

        app = Starlette(routes=routes)
        self.schemas = SchemaGenerator(
            {"openapi": "3.0.0", "info": {"title": self.__class__.__name__, "version": self.scm.sha()}}
        )

        pkgs: Dict[str, str] = {}
        for fp in self.scm.all_files():
            dir = os.path.dirname(fp)
            pkgs[dir] = ""

        logging.info("starting server version '{version}' on port: {SERVER_PORT}")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level=log_level,
            workers=1,
            reload=reload,
            reload_dirs=pkgs.keys(),
        )

    def _schema_req(self, request):
        return self.schemas.OpenAPIResponse(request=request)

    @classmethod
    def versions(
        cls: Type["Server"], repositories: Optional[List[str]] = None, cfg: Optional[Config] = None
    ) -> List[str]:
        """Find all versions of this type

        Args:
            cls (Type[Server]): the Server class
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
                if f"{cls.artifact_type()}-{cls.__name__.lower()}" in tag:
                    ret.append(f"{repo_uri}:{tag}")
        return ret

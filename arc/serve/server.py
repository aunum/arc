from __future__ import annotations
import shutil
from urllib import request
import json
import socket
from abc import ABC, ABCMeta, abstractmethod, abstractproperty
from simple_parsing import ArgumentParser
from dataclasses import dataclass
from typing import Dict, Iterable, List, Any, Optional, Type, TypeVar, Union, get_type_hints
import typing
import inspect
import time
import logging
import os
import yaml
from pathlib import Path
import uuid
from functools import wraps
from types import FunctionType
from inspect import signature

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.schemas import SchemaGenerator
import uvicorn
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
from typing_inspect import is_generic_type

from arc.kube.sync import copy_file_to_pod
from arc.image.client import default_socket
from arc.image.build import REPO_ROOT, find_or_build_img, img_command
from arc.kube.pod_util import (
    REPO_SHA_LABEL,
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
from arc.opts import OptsBuilder
from arc.kind import Kind

SERVER_PORT = "8080"
NAME_LABEL = "name"
VERSION_LABEL = "version"
BASES_LABEL = "bases"
PARAMS_SCHEMA_LABEL = "params-schema"
SERVER_PATH_LABEL = "server-path"
URI_LABEL = "uri"
OWNER_LABEL = "owner"
SERVER_PORT = "8080"
CONFIG_FILE_NAME = "config.json"
BUILD_MNT_DIR = "/mnt/build"
ARTIFACT_TYPE_LABEL = "artifact-type"
CONFIG_DIR = "/config"


class APIUtil(JsonSchemaMixin):
    @classmethod
    def from_yaml(cls: Type[T], data: Union[str, bytes], validate: bool = True, **yaml_kwargs) -> T:
        return cls.from_dict(yaml.load(data, **yaml_kwargs), validate)

    def to_yaml(self, omit_none: bool = True, validate: bool = False, **yaml_kwargs) -> str:
        return yaml.dump(self.to_dict(omit_none, validate), **yaml_kwargs)


@dataclass
class Process:
    """A Process represents a running process"""

    uri: str
    """URI the process is built from"""

    k8s_uri: str
    """K8s URI where the process is running"""


class Client:
    """A client for a server running remotely"""

    uri: str
    artifact_labels: Dict[str, Any]
    core_v1_api: CoreV1Api
    rbac_v1_api: RbacAuthorizationV1Api
    scm: SCM
    cfg: Config
    docker_socket: str

    def __init__(
        self,
        uri: Optional[str] = None,
        server: Optional[Union[Type["Server"], "Server"]] = None,
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
        self.core_v1_api = core_v1_api

        if rbac_v1_api is None:
            if is_k8s_proc():
                config.load_incluster_config()
            else:
                config.load_kube_config()
            rbac_v1_api = RbacAuthorizationV1Api()
        self.rbac_v1_api = rbac_v1_api

        # We need to get metadata on the server by looking at the registry and pulling metadata
        if docker_socket is None:
            docker_socket = default_socket()
        self.docker_socket = docker_socket

        if cfg is None:
            cfg = Config()
        self.cfg = cfg

        if scm is None:
            scm = SCM()
        self.scm = scm

        if namespace is None:
            namespace = cfg.kube_namespace

        self._patch_socket(core_v1_api)

        if uri is not None and uri.startswith("k8s://"):
            self.pod_namespace, self.pod_name = parse_k8s_uri(uri)
            self.server_addr = f"http://{self.pod_name}.pod.{self.pod_namespace}.kubernetes:{SERVER_PORT}"
            logging.info(f"connecting directly to pod {self.pod_name} in namespace {self.pod_namespace}")
            info = self.info()
            logging.info(f"server info: {info}")
            self.uri = info["uri"]
            self.artifact_labels = get_img_labels(self.uri)
            return

        if server is not None:
            self.uri = server.base_image(
                scm=scm, dev_dependencies=dev_dependencies, clean=clean, sync_strategy=sync_strategy
            )
            if isinstance(server, Server):
                if "_kwargs" in server.__dict__:
                    params = server._kwargs  # type: ignore
        else:
            if uri is None:
                raise ValueError("Client URI cannot be none. Either 'uri' or 'server' must be provided")
            self.uri = uri

        print("client uri: ", self.uri)

        # Check schema compatibility between client/server https://github.com/aunum/arc/issues/12
        self.artifact_labels = get_img_labels(self.uri)

        if self.artifact_labels is None:
            raise ValueError(f"image uri '{self.uri}' does not contain any labels, are you sure it was build by arc?")

        if reuse:
            # check if container exists
            logging.info("checking if model is already running in cluster")
            found_pod = self._find_reusable_pod(namespace)
            if found_pod is not None:
                logging.info("found reusable server running in cluster")
                pod_name = found_pod.metadata.name
                self.server_addr = f"http://{pod_name}.pod.{namespace}.kubernetes:{SERVER_PORT}"
                self.pod_name = pod_name
                self.pod_namespace = namespace
                annotations = found_pod.metadata.annotations
                logging.info(f"server info: {self.info()}")
                if sync_strategy == RemoteSyncStrategy.CONTAINER:
                    logging.info("sync strategy is container")
                    if SYNC_SHA_LABEL in annotations:
                        if annotations[SYNC_SHA_LABEL] == scm.sha():
                            logging.info("sync sha label up to date")
                            return

                    logging.info("sync sha doesn't match, syncing files")
                    self._sync_to_pod(server, found_pod, namespace=namespace)
                return

            logging.info("server not found running, deploying now...")

        logging.info("creating server in cluster")
        pod = self._create_k8s_resources(
            sync_strategy=sync_strategy,
            params=params,
            namespace=namespace,
        )
        pod_name = pod.metadata.name

        # TODO: handle readiness https://github.com/aunum/arc/issues/11
        time.sleep(10)

        self.server_addr = f"http://{pod_name}.pod.{namespace}.kubernetes:{SERVER_PORT}"
        self.pod_name = pod_name
        self.pod_namespace = namespace

        logging.info(f"server info: {self.info()}")

        if sync_strategy == RemoteSyncStrategy.CONTAINER:
            logging.info("syncing files to server container")
            self._sync_to_pod(server, pod, namespace)
        return

    def _patch_socket(self, core_v1_api: CoreV1Api) -> None:
        """Patch the socket to port forward to k8s pods

        Args:
            core_v1_api (CoreV1Api): CoreV1API to use
        """
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

    def _find_reusable_pod(self, namespace: str) -> Optional[V1Pod]:
        """Find a reusable pod to sync code to

        Args:
            namespace (str): Namespace to look

        Returns:
            Optional[V1Pod]: A pod if found or None.
        """
        logging.info("checking if server is already running in cluster")
        pod_list: V1PodList = self.core_v1_api.list_namespaced_pod(namespace)
        found_pod: Optional[V1Pod] = None
        for pod in pod_list.items:
            annotations = pod.metadata.annotations
            if annotations is None:
                continue
            if URI_LABEL in annotations and OWNER_LABEL in annotations:
                server_uri = annotations[URI_LABEL]
                server_owner = annotations[OWNER_LABEL]
                if server_uri == self.uri:
                    if server_owner != get_client_id():
                        logging.warning("found server running in cluster but owner is not current user")
                    found_pod = pod
        return found_pod

    def _sync_to_pod(
        self,
        server: Optional[Union[Type[Server], Server]],
        pod: V1Pod,
        namespace: str,
    ) -> None:
        """Sync local code to pod

        Args:
            server (Optional[Type[Server]]): Server type to use
            pod (V1Pod): Pod to sync to
            namespace (str): Namespace to use
        """
        if server is None:
            raise ValueError("server cannot be None when doing a container sync")

        server_path = server.server_entrypoint()
        logging.info(f"wrote server to path: {server_path}")
        pod_name = pod.metadata.name
        copy_file_to_pod(
            self.scm.all_files(absolute_paths=True),
            pod_name,
            namespace=namespace,
            base_path=REPO_ROOT.lstrip("/"),
            label=True,
            core_v1_api=self.core_v1_api,
            scm=self.scm,
            restart=False,
        )
        # TODO: need to remove this sleep
        time.sleep(10)
        logging.info("files copied to pod, waiting for pod to become ready")
        # see if pod is ready
        ready = wait_for_pod_ready(pod_name, namespace, self.core_v1_api)
        if not ready:
            raise SystemError(f"pod {pod_name} never became ready")
        logging.info("pod is ready!")

        # should check if info returns the right version
        # it will just return the original verion, how do we sync the verion with
        # the files to tell if its running?
        # TODO! https://github.com/aunum/arc/issues/11
        logging.info(self.info())
        return

    def _create_k8s_resources(
        self,
        sync_strategy: RemoteSyncStrategy,
        labels: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
    ) -> V1Pod:
        """Create the resources needed in Kubernetes

        Args:
            sync_strategy (RemoteSyncStrategy): Sync strategy to use
            labels (Optional[Dict[str, Any]], optional): Labels to add. Defaults to None.
            params (Optional[Dict[str, Any]], optional): Params for the model to use. Defaults to None.
            namespace (Optional[str], optional): Namespace to use. Defaults to None.

        Returns:
            V1Pod: The created pod
        """

        repository, tag = parse_repository_tag(self.uri)
        registry, repo_name = resolve_repository_name(repository)
        project_name = repo_name.split("/")[1]

        pod_name = f"{str(project_name).replace('/', '-')}-{tag}"

        if len(pod_name) > 57:
            pod_name = pod_name[:56]

        uid = str(uuid.uuid4())
        pod_name = pod_name + "-" + uid[:5]

        logging.info("ensuring cluster auth resources...")
        auth_resources = ensure_cluster_auth_resources(
            self.core_v1_api, self.rbac_v1_api, self.docker_socket, namespace, self.cfg
        )

        if params is not None:
            cfg = V1ConfigMap(
                metadata=V1ObjectMeta(name=pod_name, namespace=namespace), data={CONFIG_FILE_NAME: json.dumps(params)}
            )
            self.core_v1_api.create_namespaced_config_map(namespace, cfg)

        server_path = self.artifact_labels[SERVER_PATH_LABEL]

        # if not deploy
        container = V1Container(
            name="server",
            command=img_command(server_path),
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
                V1EnvVar(name="ARTIFACT_URI", value=self.uri),
            ],
        )
        container.volume_mounts = [
            V1VolumeMount(name="build", mount_path=BUILD_MNT_DIR),
            V1VolumeMount(name="dockercfg", mount_path="/root/.docker"),
        ]
        if params is not None:
            container.volume_mounts.append(V1VolumeMount(name="config", mount_path=CONFIG_DIR))

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

        annotations = {
            URI_LABEL: self.uri,
            OWNER_LABEL: get_client_id(),
        }
        annotations.update(self.artifact_labels)
        po = V1Pod(
            metadata=V1ObjectMeta(
                name=pod_name,
                namespace=namespace,
                labels={
                    REPO_SHA_LABEL: self.scm.sha(),
                    ENV_SHA_LABEL: self.scm.env_sha(),
                    REPO_NAME_LABEL: self.scm.name(),
                    SYNC_STRATEGY_LABEL: str(sync_strategy),
                },
                annotations=annotations,
            ),
            spec=spec,
        )
        self.core_v1_api.create_namespaced_pod(namespace, po)

        # see if pod is ready
        ready = wait_for_pod_ready(pod_name, namespace, self.core_v1_api)
        if not ready:
            raise SystemError(f"pod {pod_name} never became ready")

        logging.info(f"pod is ready'{pod_name}'")

        return po

    def info(self) -> Dict[str, Any]:
        """Info about the server

        Returns:
            Dict[str, Any]: Server info
        """
        req = request.Request(f"{self.server_addr}/info")
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        return json.loads(data)

    def labels(self) -> Dict[str, Any]:
        """Labels for the server

        Returns:
            Dict[str, Any]: Server info
        """
        req = request.Request(f"{self.server_addr}/labels")
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
        data = resp.read().decode("utf-8")
        return json.loads(data)

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
        """Delete the server"""
        self.core_v1_api.delete_namespaced_pod(self.pod_name, self.pod_namespace)

    @classmethod
    def find(cls) -> List["Client"]:
        """Find all the servers that could be deployed (or are running)"""
        raise NotImplementedError()

    def k8s_uri(self) -> str:
        """K8s URI for the server

        Returns:
            str: K8s URI for the server
        """
        if self.pod_name == "" or self.pod_namespace == "":
            raise ValueError("no pod name or namespace for client")

        return make_k8s_uri(self.pod_name, self.pod_namespace)

    def copy(self, core_v1_api: Optional[CoreV1Api] = None) -> Process:
        """Copy the server

        Args:
            core_v1_api (Optional[CoreV1Api], optional): CoreV1Api to sue. Defaults to None.

        Returns:
            RunningServer: A running server
        """
        params = json.dumps({}, cls=ShapeEncoder).encode("utf8")
        req = request.Request(f"{self.server_addr}/copy", data=params, headers={"content-type": "application/json"})
        resp = request.urlopen(req)
        resp_data = resp.read().decode("utf-8")

        jdict = json.loads(resp_data)
        return Process(uri=jdict["uri"], k8s_uri=jdict["k8s_uri"])

    def save(
        self,
        version: Optional[str] = None,
        core_v1_api: Optional[CoreV1Api] = None,
    ) -> str:  # TODO: make this a generator
        """Save the server

        Args:
            version (Optional[str], optional): Version to use. Defaults to repo version.
            core_v1_api (Optional[CoreV1Api], optional): CoreV1API to use. Defaults to None.

        Returns:
            str: URI of the saved server
        """
        if core_v1_api is None:
            if is_k8s_proc():
                config.load_incluster_config()
            else:
                config.load_kube_config()

            core_v1_api = CoreV1Api()

        logging.info("saving server...")

        req = request.Request(f"{self.server_addr}/save", method="POST")
        resp = request.urlopen(req)
        body = resp.read().decode("utf-8")

        _, tag = parse_repository_tag(self.uri)
        # registry, repo_name = resolve_repository_name(repository)
        # docker_secret = get_dockercfg_secret_name()

        cls_name = tag.split("-")[1]

        info = self.info()
        version = info["version"]
        uri = img_id(RemoteSyncStrategy.IMAGE, tag=f"{cls_name}-{version}")

        labels = self.labels()

        path_params = {"name": self.pod_name, "namespace": self.pod_namespace}

        query_params = []  # type: ignore
        header_params = {}

        form_params = []  # type: ignore
        local_var_files = {}  # type: ignore

        header_params["Accept"] = "application/json"
        header_params["Content-Type"] = "application/strategic-merge-patch+json"

        # Authentication setting
        auth_settings = ["BearerToken"]  # noqa: E501

        # _pod: V1Pod = core_v1_api.read_namespaced_pod(self.pod_name, self.pod_namespace)

        label_args: List[str] = []
        for k, v in labels.items():
            label_args.append(f"--label={k}={v}")

        args = [
            f"--context={REPO_ROOT}",
            f"--destination={uri}",
            "--dockerfile=Dockerfile.arc",
            "--ignore-path=/product_uuid",  # https://github.com/GoogleContainerTools/kaniko/issues/2164
        ]
        args.extend(label_args)
        body = {
            "spec": {
                "ephemeralContainers": [
                    {
                        "name": f"snapshot-{int(time.time())}",
                        "args": args,
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


def init_wrapper(method):
    """Init wrapper stores the args provided on object creation so that they
    may be used remotely"""

    @wraps(method)
    def wrapped(*args, **kwargs):
        self_var = args[0]
        _kwargs = kwargs.copy()
        names = method.__code__.co_varnames
        _kwargs.update(zip(names[1:], args[1:]))
        if "_kwargs" not in self_var.__dict__:
            self_var.__dict__["_kwargs"] = _kwargs
        return method(*args, **kwargs)

    return wrapped


def local(method):
    """Local wrapper"""
    method.local = True
    return method


class ServerMetaClass(type):
    """Server metaclass is the metaclass for the Server type"""

    def __new__(meta, classname, bases, classDict):
        newClassDict = {}
        routes: List[str] = []

        for attributeName, attribute in classDict.items():
            if isinstance(attribute, FunctionType):
                if hasattr(attribute, "local"):
                    print("!!! ignoring: ", attributeName)
                    continue

                if attributeName.startswith("__"):
                    continue

                if attributeName == "__init__":
                    attribute = init_wrapper(attribute)
                elif not attributeName.startswith("_"):
                    print("attribute: ", attribute)
                    print("sig: ", signature(attribute))
                    print("sig params: ", signature(attribute).parameters)
                    load_lines = []
                    sig = signature(attribute)
                    for k in sig.parameters:
                        print("k", k)
                        if k == "self":
                            continue
                        param = sig.parameters[k]
                        print("param annot: ", param.annotation)
                        _op = getattr(param.annotation, "from_dict", None)
                        print("_op: ", _op)
                        if callable(_op):
                            print("!!!! callable")
                            load_lines.append(f"jdict['{k}'] = {param.annotation.__name__}.from_dict(jdict['{k}'])")

                    hints = get_type_hints(attribute)
                    ret = hints["return"]

                    ret_op = getattr(ret, "to_dict", None)
                    ser_line = ""
                    print("ret_op: ", ret_op)
                    if callable(ret_op):
                        ser_line = "ret = ret.to_dict()"

                    joined_load_lines = "\n".join(load_lines)
                    if isinstance(ret, Iterable):
                        req_code = f"""
# Use websockets...
@app.websocket_route('/stream')
async def stream(websocket):
    update_ts()
    await websocket.accept()

    # TODO: ugly hack to not deal with concurrency
    if "client-uuid" not in websocket.headers:
        raise ValueError("'client-uuid' must be present in headers")
    client_uuid = websocket.headers["client-uuid"]
    global global_client_uuid
    if global_client_uuid == "":
        global_client_uuid = client_uuid
    if global_client_uuid != client_uuid:
        raise ValueError("arc jobs currently do not support multiple clients; create another job for your client")

    # Process incoming messages
    params = websocket.query_params

    batch_size = params.get("batch_size", DEFAULT_BATCH_SIZE)
    batch_type = params.get("batch_type", BatchType.TRAIN.value)

    for x, y in job.stream(int(batch_size), BatchType(batch_type)):
        total_start = time.time()
        # rec = await websocket.receive_json()
        print("prepping data")
        x_repr = x.repr_json()
        y_repr = y.repr_json()
        print("sending")
        d = {{"x": x_repr, "y": y_repr, "end": False}}
        await websocket.send_json(d)
        print("sent")
        total_end = time.time()
        print("total loop time: ", total_end - total_start)

    # reset the uid to unlock
    global_client_uuid = ""
    print("sending end")
    await websocket.send_json({{"end": True}})
    print("all done sending data, closing socket")
    await websocket.close()
                        """
                    else:
                        req_code = f"""
async def _{attributeName}_req(self, request): 
    jdict = await request.json()
    {joined_load_lines}
    ret = {attributeName}(**jdict)
    {ser_line}
    return JSONResponse(ret)
"""
                    print("req code: ", req_code)
                    exec(req_code)
                    newClassDict[f"_{attributeName}_req"] = eval(f"_{attributeName}_req")
                    routes.append(f"Route('/{attributeName}', endpoint=self._{attributeName}_req)")
            newClassDict[attributeName] = attribute

        routes_joined = ", ".join(routes)
        route_code = f"""
def _routes(self) -> List[Route]:
    return [{routes_joined}]
"""
        print("route code: ", route_code)
        exec(route_code)
        newClassDict["_routes"] = _routes  # noqa: F821
        return type.__new__(meta, classname, bases, newClassDict)


class CombinedMeta(ServerMetaClass, ABCMeta):
    pass


S = TypeVar("S", bound="Server")


# TODO: can we get rid or APIUtil??
# should this be an actor?
class Server(ABC, APIUtil, metaclass=CombinedMeta):
    """A server that can be built and ran remotely"""

    last_used_ts: float
    scm: SCM
    schemas: SchemaGenerator

    @local
    @classmethod
    def from_env(cls: Type[S]) -> S:
        """Create the server from the environment, it will look for a saved artifact,
        a config.json, or command line arguments

        Returns:
            Server: A server
        """
        log_level = os.getenv("LOG_LEVEL")
        if log_level is None:
            logging.basicConfig(level=logging.INFO)
        else:
            logging.basicConfig(level=log_level)

        parser = ArgumentParser()
        opts = cls.opts()
        if opts is not None:
            parser.add_arguments(opts, dest="server")

        logging.info("logging test0")

        artifact_file = Path(f"./artifacts/{cls.short_name()}.pkl")
        cfg_file = Path(CONFIG_DIR, CONFIG_FILE_NAME)

        if artifact_file.is_file():
            logging.info("loading srv artifact found locally")
            srv: S = cls.load()
        elif cfg_file.is_file():
            if opts is None:
                logging.info("no local artifact, config, or args found. Creating vanilla class without parameters")
                srv = cls()
            else:
                logging.info("loading srv from config file")
                jopts = opts.load_json(cfg_file)
                srv = cls.from_opts(jopts)  # type: ignore
        elif opts is not None:
            logging.info("loading srv from args")
            args = parser.parse_args()
            srv = cls.from_opts(args.server)
        else:
            if opts is None:
                logging.info("no local artifact, config, or args found. Creating vanilla class without parameters")
                srv = cls()
            else:
                logging.info("loading srv from args")
                args = parser.parse_args()
                srv = cls.from_opts(args.server)

        uri = os.getenv("ARTIFACT_URI")
        if uri is None:
            logging.warning("$ARTIFACT_URI var not found, defaulting to class uri")
        else:
            srv.uri = uri

        srv.last_used_ts = time.time()
        srv.scm = SCM()

        return srv

    @classmethod
    def name(cls) -> str:
        """Name of the server

        Returns:
            str: Name of the server
        """
        return cls.__name__

    @classmethod
    def short_name(cls) -> str:
        """Short name for the server

        Returns:
            str: A short name
        """
        return cls.__name__.lower()

    @classmethod
    def base_names(cls) -> List[str]:
        """Bases for the server

        Raises:
            SystemError: Server bases

        Returns:
            List[str]: Bases of the server
        """
        bases = inspect.getmro(cls)
        base_names: List[str] = []
        for base in bases:
            if isinstance(base, Server):
                base_names.append(base.__name__)
        return base_names

    def _info_req(self, request):
        return JSONResponse(
            {
                "name": self.__class__.__name__,
                "version": self.scm.sha(),
                "env-sha": self.scm.env_sha(),
                "uri": self.uri,
            }
        )

    def _health_req(self, request):
        return JSONResponse({"health": "ok"})

    def _labels_req(self, request):
        return JSONResponse(self.labels())

    @classmethod
    def labels(cls, scm: Optional[SCM] = None) -> Dict[str, Any]:
        """Labels for the server

        Args:
            scm (Optional[SCM], optional): SCM to use. Defaults to None.

        Returns:
            Dict[str, Any]: Labels for the server
        """
        if scm is None:
            scm = SCM()
        base_names = cls.base_names()

        base_labels = {
            BASES_LABEL: json.dumps(base_names),
            NAME_LABEL: cls.__name__,
            VERSION_LABEL: scm.sha(),
            PARAMS_SCHEMA_LABEL: json.dumps(cls.opts_schema()),
            ENV_SHA_LABEL: scm.env_sha(),
            REPO_NAME_LABEL: scm.name(),
            REPO_SHA_LABEL: scm.sha(),
        }
        return base_labels

    def _routes(self) -> List[Route]:
        """Routes to add to the server

        Returns:
            List[Route]: List of routes to add to the server
        """
        routes = [
            Route("/info", endpoint=self._info_req, methods=["GET"]),
            Route("/health", endpoint=self._health_req, methods=["GET"]),
            Route("/schema", endpoint=self._schema_req, methods=["GET"]),
            Route("/labels", endpoint=self._labels_req, methods=["GET"]),
        ]

        return routes

    @classmethod
    def client_cls(cls) -> Type[Client]:
        """Class of the client for the server

        Returns:
            Type[Client]: A client class for the server
        """
        return Client

    @local
    @classmethod
    def server_entrypoint(cls, scm: Optional[SCM] = None, num_workers: int = 1) -> str:
        """Generate entrypoint for the server

        Args:
            scm (Optional[SCM], optional): SCM to use. Defaults to None.

        Returns:
            str: Path to the entrypoint file
        """
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
import os

import uvicorn

from {cls_file} import {cls.__name__}
from {cls_file} import *  # noqa: F403, F401

log_level = os.getenv("LOG_LEVEL")
if log_level is None:
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=log_level)

logging.info("creating object")
srv = {cls.__name__}.from_env()

logging.info("creating app")
app = srv.server_app()

if __name__ == "__main__":
    pkgs = srv._reload_dirs()
    logging.info(f"starting server version '{{srv.scm.sha()}}' on port: {SERVER_PORT}")
    uvicorn.run(
        "__main__:app",
        host="0.0.0.0",
        port={SERVER_PORT},
        log_level="info",
        workers={num_workers},
        reload=True,
        reload_dirs=pkgs.keys(),
    )
"""

        class_file = inspect.getfile(cls)
        dir_path = os.path.dirname(os.path.realpath(class_file))
        server_filepath = os.path.join(dir_path, server_file_name)
        with open(server_filepath, "w") as f:
            f.write(server_file)
        return server_filepath

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
    def load(cls: Type[S], dir: str = "./artifacts") -> S:
        """Load the object

        Args:
            dir (str): Directory to the artifacts
        """
        path = os.path.join(dir, f"{cls.short_name()}.pkl")
        with open(path, "rb") as f:
            return pickle.load(f)

    @classmethod
    def clean_artifacts(cls, dir: str = "./artifacts") -> None:
        """Clean any created artifacts

        Args:
            dir (str, optional): Directory where artifacts exist. Defaults to "./artifacts".
        """
        shutil.rmtree(dir)

    @classmethod
    def opts_schema(cls) -> Dict[str, Any]:
        """Schema for the server options

        Returns:
            Dict[str, Any]: JsonSchema for the server options
        """
        opts = OptsBuilder[JsonSchemaMixin].build(cls)
        if opts is None:
            return {}
        return opts.json_schema()

    @classmethod
    def opts(cls) -> Optional[Type[Serializable]]:
        """Options for the server

        Returns:
            Optional[Type[Serializable]]: Options for the server
        """
        return OptsBuilder[Serializable].build(cls)

    @property
    def uri(self) -> str:
        """URI for the resource

        Returns:
            str: A URI for the resource
        """
        if self._uri is None:
            return f"{self.__module__}.{self.__class__.__name__}"
        return self._uri

    @uri.setter
    def uri(self, val: str):
        self._uri = val

    def _update_ts(self):
        self.last_used_ts = time.time()

    @local
    def deploy(
        self,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
        **kwargs,
    ) -> Client:
        """Create a deployment of the class, which will allow for the generation of instances remotely

        Args:
            scm (Optional[SCM], optional): SCM to use. Defaults to None.
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            sync_strategy (RemoteSyncStrategy, optional): Sync strategy to use. Defaults to RemoteSyncStrategy.IMAGE.

        Returns:
            Client: A client for the server
        """

        imgid = self.base_image(scm, clean, dev_dependencies)
        return self.client_cls()(  # type: ignore
            uri=imgid, sync_strategy=sync_strategy, clean=clean, scm=scm, dev_dependencies=dev_dependencies, **kwargs
        )

    @local
    @classmethod
    def develop(
        self,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        reuse: bool = True,
        **kwargs,
    ) -> Client:
        """Create a deployment of the class, and sync local code to it

        Args:
            scm (Optional[SCM], optional): SCM to use. Defaults to None.
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            reuse (bool, optional): Whether to reuse existing running servers. Defaults to True.

        Returns:
            Client: A client for the server
        """
        return self.client_cls()(  # type: ignore
            server=self,
            sync_strategy=RemoteSyncStrategy.CONTAINER,
            clean=clean,
            reuse=reuse,
            dev_dependencies=dev_dependencies,
            scm=scm,
            **kwargs,
        )

    @local
    @classmethod
    def base_image(
        cls,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
    ) -> str:
        """Create an image from the server class that can be used to create servers from scratch

        Args:
            scm (Optional[SCM], optional): SCM to use. Defaults to None.
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            sync_strategy (RemoteSyncStrategy, optional): Sync strategy to use. Defaults to RemoteSyncStrategy.IMAGE.

        Returns:
            str: URI for the image
        """

        return cls.build_image(scm=scm, clean=clean, dev_dependencies=dev_dependencies, sync_strategy=sync_strategy)

    @local
    def image(self, scm: Optional[SCM] = None, dev_dependencies: bool = False, clean: bool = True) -> str:
        """Create a server image with the saved artifact

        Args:
            scm (Optional[SCM], optional): SCM to use. Defaults to None.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            clean (bool, optional): Whether to clean the generated files. Defaults to True.

        Returns:
            str: URI for the image
        """

        if scm is None:
            scm = SCM()

        self.save()

        uri = self.build_image(
            scm=scm,
            clean=clean,
            dev_dependencies=dev_dependencies,
            sync_strategy=RemoteSyncStrategy.IMAGE,
        )
        if clean:
            self.clean_artifacts()

        return uri

    @local
    @classmethod
    def build_image(
        cls,
        labels: Optional[Dict[str, str]] = None,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
    ) -> str:
        """Build a generic image for a server

        Args:
            labels (Optional[Dict[str, str]], optional): Labels to add. Defaults to None.
            scm (Optional[SCM], optional): SCM to use. Defaults to None.
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            sync_strategy (RemoteSyncStrategy, optional): Sync strategy to use. Defaults to RemoteSyncStrategy.IMAGE.

        Returns:
            str: URI of the image
        """

        if scm is None:
            scm = SCM()
        # write the server file somewhere we can find it
        server_filepath = Path(cls.server_entrypoint())
        repo_root = Path(str(scm.git_repo.working_dir))
        root_relative = server_filepath.relative_to(repo_root)
        container_path = Path(REPO_ROOT).joinpath(root_relative)

        base_labels = cls.labels()
        if labels is not None:
            base_labels.update(labels)

        base_labels[SERVER_PATH_LABEL] = str(container_path)

        if sync_strategy == RemoteSyncStrategy.IMAGE:
            imgid = find_or_build_img(
                sync_strategy=RemoteSyncStrategy.IMAGE,
                command=img_command(str(container_path)),
                tag_prefix=f"{cls.short_name().lower()}",
                labels=base_labels,
                dev_dependencies=dev_dependencies,
                clean=clean,
            )
        elif sync_strategy == RemoteSyncStrategy.CONTAINER:
            imgid = find_or_build_img(
                sync_strategy=RemoteSyncStrategy.IMAGE,  # TODO: fix this at the source, we want to copy all files now
                command=img_command(str(container_path)),
                tag=f"{cls.short_name().lower()}-env-{scm.env_sha()}",
                labels=base_labels,
                dev_dependencies=dev_dependencies,
                clean=clean,
            )
        if clean:
            os.remove(server_filepath)

        return str(imgid)

    @classmethod
    def from_opts(cls: Type[S], opts: Type[Serializable]) -> S:
        """Load server from Opts

        Args:
            cls (Type[&quot;Server&quot;]): Server
            opts (Opts): Opts to load from

        Returns:
            Server: A server
        """
        return cls(**opts.__dict__)

    @local
    def server_app(self) -> Starlette:
        """Starlette server app

        Returns:
            Starlette: A server app
        """
        routes = self._routes()

        app = Starlette(routes=routes)
        self.schemas = SchemaGenerator(
            {"openapi": "3.0.0", "info": {"title": self.__class__.__name__, "version": self.scm.sha()}}
        )
        return app

    def _reload_dirs(self) -> Dict[str, str]:
        pkgs: Dict[str, str] = {}
        for fp in self.scm.all_files():
            dir = os.path.dirname(fp)
            pkgs[dir] = ""

        return pkgs

    @local
    def serve(self, port: int = 8080, log_level: str = "info", reload: bool = True) -> None:
        """Serve the class

        Args:
            port (int, optional): Port to serve one. Defaults to 8080.
            log_level (str, optional): Log level. Defaults to "info".
            reload (bool, optional): Whether to hot reload. Defaults to True.
        """
        app = self.server_app()

        pkgs = self._reload_dirs()

        logging.info(f"starting server version '{self.scm.sha()}' on port: {SERVER_PORT}")
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
            cfg (Config, optional): Config to use

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
                if f"{cls.__name__.lower()}" in tag:
                    ret.append(f"{repo_uri}:{tag}")
        return ret

    @local
    @classmethod
    def gen_client(cls) -> str:
        """Generate a client for the server

        Returns:
            str: The client Python code
        """
        fns = inspect.getmembers(cls, predicate=inspect.isfunction)
        print("fns: ", fns)
        params: List[str] = []
        methods: List[str] = []
        imports: List[str] = []
        for name, fn in fns:
            if name.startswith("_"):
                continue

            print("name: ", name)
            print("fn: ", fn)
            sig = inspect.signature(fn)
            print("sig str: ", str(sig))

            # print("sig: ", sig)
            # print("params: ", sig.parameters)

            for k in sig.parameters:
                if k == "self":
                    continue
                param = sig.parameters[k]
                # print("param annot: ", param.annotation)
                _op = getattr(param.annotation, "to_dict", None)
                if callable(_op):
                    params.append(f"'{k}': {k}.to_dict()")
                    continue

                params.append(f"'{k}': {k}")

            import_statements: Dict[str, Any] = {}
            hints = get_type_hints(fn)

            def proc_hint(h: Type):
                print("===================")
                print("processing hint....")
                print("===================")
                mod = h.__module__
                print("h mod: ", mod)

                if mod == "builtins":
                    return

                if is_generic_type(h):
                    print("is generic")
                    args = typing.get_args(h)
                    for arg in args:
                        print("processing arg: ", arg)
                        proc_hint(arg)

                    origin = typing.get_origin(h)
                    if origin == list:
                        origin = List
                    if origin == dict:
                        origin = Dict
                    h = origin  # type: ignore

                # TODO: handle Union

                import_statements[f"from {mod} import {h.__name__}"] = None

            for hint in hints:
                print("hint: ", hint)
                h = hints[hint]
                proc_hint(h)

            ret = hints["return"]
            ret_op = getattr(ret, "from_dict", None)
            ser_line = "ret = jdict['response']"
            print("ret_op: ", ret_op)
            if callable(ret_op):
                ser_line = "ret = ret.from_dict(jdict)"

            params_joined = ",".join(params)

            client_fn = f"""
    def {name}{sig}:
        params = json.dumps({{{params_joined}}}).encode("utf8")
        req = request.Request(f"{{self.server_addr}}/{name}", data=params, headers={{"content-type": "application/json"}})
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        {ser_line}
        return ret
            """
            methods.append(client_fn)

        imports_joined = "\n".join(import_statements.keys())
        methods_joined = "\n".join(methods)
        client_file = f"""
from urllib import request
import json
import logging

from arc.serve.server import Client
{imports_joined}

class {cls.__name__}Client(Client):
{methods_joined}
        """

        return client_file

    @classmethod
    def _client_file_name(cls) -> str:
        return f"{cls.__name__.lower()}_client"

    @local
    @classmethod
    def write_client_file(cls) -> None:
        """Generate and write the client file next to the current one"""
        with open(f"{cls._client_file_name}.py", "w", encoding="utf-8") as f:
            f.write(cls.gen_client())

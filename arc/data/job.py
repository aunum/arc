from abc import ABC, abstractmethod
from dataclasses import dataclass, field, make_dataclass, is_dataclass
from typing import List, Iterator, Tuple, Dict, Type, Union, Any, Optional
import logging
import inspect
import typing
from typing import TypeVar, Generic
from pathlib import Path
import os
import json
import socket
import time
import uuid
from urllib import parse, request

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
    V1SecretVolumeSource,
    V1Probe,
    V1ExecAction,
    V1EnvVar,
    V1KeyToPath,
    V1EnvVarSource,
    V1ObjectFieldSelector,
)
from kubernetes.client import (
    CoreV1Api,
    V1ObjectMeta,
    RbacAuthorizationV1Api,
)
from docker.utils.utils import parse_repository_tag
from docker.auth import resolve_repository_name
from websocket import create_connection
from dataclasses_jsonschema import JsonSchemaMixin

from arc.data.types import XData, YData
from arc.kube.sync import copy_file_to_pod
from arc.model.types import SupervisedModel, SupervisedModelClient
from arc.data.types import Score, EvalReport, BatchType
from arc.scm import SCM
from arc.image.client import default_socket
from arc.image.build import REPO_ROOT, find_or_build_img, img_command
from arc.config import Config, RemoteSyncStrategy
from arc.kube.pod_util import (
    TYPE_LABEL,
    SYNC_SHA_LABEL,
    REPO_NAME_LABEL,
    FUNC_NAME_LABEL,
    ENV_SHA_LABEL,
    REPO_SHA_LABEL,
    SYNC_STRATEGY_LABEL,
    wait_for_pod_ready,
)
from arc.image.registry import get_img_labels, get_repo_tags
from arc.kube.env import is_k8s_proc
from arc.kube.auth_util import ensure_cluster_auth_resources
from arc.config import Opts


DEFAULT_BATCH_SIZE = 32
DEFAULT_EPOCH_SIZE = 100
JOB_LABEL = "job"
JOB_NAME_LABEL = "name"
JOB_VERSION_LABEL = "version"
JOB_BASE_NAME_LABEL = "base"
JOB_X_DATA_LABEL = "x"
JOB_X_DATA_SCHEMA_LABEL = "x-schema"
JOB_Y_DATA_LABEL = "y"
JOB_Y_DATA_SCHEMA_LABEL = "y-schema"
JOB_PARAMS_SCHEMA_LABEL = "params-schema"
JOB_SERVER_PATH_LABEL = "server-path"
SERVER_PORT = "8080"
JOB_CONFIG_FILE_NAME = "config.json"

X = TypeVar("X", bound="XData")
Y = TypeVar("Y", bound="YData")


@dataclass
class XY(Generic[X, Y]):
    x: X
    y: Y

    @classmethod
    @abstractmethod
    def load_dict(cls: Type["XY"], dict: Dict[str, Any]) -> "XY":
        return cls(x=cls.x.__class__.load_dict(dict["x"]), y=cls.y.__class__.load_dict(dict["y"]))


class SupervisedJobClient(Generic[X, Y]):
    """A client for a supervised model"""

    pod_name: str
    pod_namespace: str
    x_cls: Optional[Type[X]] = None
    y_cls: Optional[Type[Y]] = None
    uri: Optional[str] = None
    uid: Optional[str] = None

    def __init__(
        self,
        uri: Optional[str] = None,
        job: Optional[Type["SupervisedJob"]] = None,
        core_v1_api: Optional[CoreV1Api] = None,
        rbac_v1_api: Optional[RbacAuthorizationV1Api] = None,
        docker_socket: Optional[str] = None,
        namespace: Optional[str] = None,
        cfg: Optional[Config] = None,
        scm: Optional[SCM] = None,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
        dev_dependencies: Optional[bool] = None,
        clean: bool = True,
        **kwargs,
    ) -> None:
        """A SupervisedJobClient

        Args:
            uri (Optional[str], optional): URI to create job from. Defaults to None.
            job (Optional[Type[&quot;SupervisedJob&quot;]], optional): Job to use. Defaults to None.
            core_v1_api (Optional[CoreV1Api], optional): CoreV1Api to use. Defaults to None.
            rbac_v1_api (Optional[RbacAuthorizationV1Api], optional): RbacV1Api to use. Defaults to None.
            docker_socket (Optional[str], optional): Docker socket to use. Defaults to None.
            namespace (Optional[str], optional): Namespace to use. Defaults to None.
            cfg (Optional[Config], optional): Config to use. Defaults to None.
            scm (Optional[SCM], optional): SCM to use. Defaults to None.
            sync_strategy (RemoteSyncStrategy, optional): SyncStrategy to employ. Defaults to RemoteSyncStrategy.IMAGE.
            dev_dependencies (Optional[bool], optional): Whether to install dev dependencies. Defaults to None.
            clean (bool, optional): Whether to clean the generated files. Defaults to True.
        """

        self.uri = uri

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

        if docker_socket is None:
            docker_socket = default_socket()

        if cfg is None:
            cfg = Config()

        if scm is None:
            scm = SCM()

        if namespace is None:
            namespace = cfg.kube_namespace

        if job is not None:
            self.uri = job.base_image(
                scm=scm, sync_strategy=sync_strategy, clean=clean, dev_dependencies=dev_dependencies
            )

        # Check schema compatibility between client/server
        img_labels = get_img_labels(self.uri)

        if img_labels is None:
            raise ValueError(f"image uri '{self.uri}' does not contain any labels, are you sure it was build by arc?")

        self.model_x_schema = img_labels[JOB_X_DATA_SCHEMA_LABEL]
        self.model_y_schema = img_labels[JOB_Y_DATA_SCHEMA_LABEL]
        self.model_params_schema = img_labels[JOB_PARAMS_SCHEMA_LABEL]
        self.server_path = img_labels[JOB_SERVER_PATH_LABEL]

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

            logging.debug(f"port forwarding name: {name} and namespace: {namespace} port: {port}")
            pf = portforward(core_v1_api.connect_get_namespaced_pod_portforward, name, namespace, ports=str(port))
            return pf.socket(int(port))

        socket.create_connection = kubernetes_create_connection

        # check if container exists
        logging.info("checking if job is already running in cluster")
        pod_list: V1PodList = core_v1_api.list_namespaced_pod(namespace)
        for pod in pod_list.items:
            annotations = pod.metadata.annotations
            pod_name = pod.metadata.name
            if annotations is None:
                continue
            if JOB_LABEL in annotations:
                server_job_uri = annotations[JOB_LABEL]
                if server_job_uri == self.uri:
                    logging.info("found job running in cluster")
                    self.server_addr = f"http://{pod_name}.pod.{namespace}.kubernetes:{SERVER_PORT}"
                    self.pod_name = pod_name
                    self.pod_namespace = namespace
                    if sync_strategy == RemoteSyncStrategy.CONTAINER:
                        logging.info("sync strategy is container")
                        if SYNC_SHA_LABEL in annotations:
                            if annotations[SYNC_SHA_LABEL] == scm.sha():
                                logging.info("sync sha label up to date")
                                return

                        logging.info("sync sha doesn't match, syncing files")
                        if job is None:
                            raise ValueError("job cannot be none when doing a container sync")
                        server_path = job.server_entrypoint()
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

                # TODO: store connection to server

        logging.info("model not found running, deploying now...")
        repository, tag = parse_repository_tag(self.uri)
        _, repo_name = resolve_repository_name(repository)
        project_name = repo_name.split("/")[1]

        # need to know if this should have a configmap
        pod_name = f"{str(project_name).replace('/', '-')}-{tag}"
        if len(pod_name) > 63:
            pod_name = pod_name[:62]

        if params is not None:
            cfgmap = V1ConfigMap(
                metadata=V1ObjectMeta(name=pod_name, namespace=namespace), data={"cfg": json.dumps(params)}
            )
            core_v1_api.create_namespaced_config_map(namespace, cfgmap)

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
            env=[
                V1EnvVar(name="JOB_URI", value=self.uri),
                V1EnvVar(
                    name="POD_NAME",
                    value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path="metadata.name")),
                ),
            ],
        )

        volume_mounts = [V1VolumeMount(name="dockercfg", mount_path="/root/.docker")]

        if params is not None:
            volume_mounts.append(V1VolumeMount(name="config", mount_path=REPO_ROOT, sub_path=JOB_CONFIG_FILE_NAME))

        container.volume_mounts = volume_mounts

        spec = V1PodSpec(
            containers=[container],
            service_account_name=auth_resources.service_account_name,
        )

        volumes = [
            V1Volume(
                name="dockercfg",
                secret=V1SecretVolumeSource(
                    secret_name=auth_resources.secret_name,
                    items=[V1KeyToPath(key=".dockerconfigjson", path="config.json")],
                ),
            )
        ]

        if params is not None:
            volumes.append(V1Volume(name="config", config_map=V1ConfigMapVolumeSource(name=pod_name)))

        spec.volumes = volumes

        pod = V1Pod(
            metadata=V1ObjectMeta(
                name=pod_name,
                namespace=namespace,
                labels={
                    TYPE_LABEL: "server",
                    FUNC_NAME_LABEL: self.__class__.__name__,
                    REPO_SHA_LABEL: scm.sha(),
                    ENV_SHA_LABEL: scm.env_sha(),
                    REPO_NAME_LABEL: scm.name(),
                    SYNC_STRATEGY_LABEL: str(sync_strategy),
                },
                annotations={
                    JOB_LABEL: self.uri,
                    JOB_X_DATA_SCHEMA_LABEL: self.model_x_schema,
                    JOB_Y_DATA_SCHEMA_LABEL: self.model_y_schema,
                    JOB_PARAMS_SCHEMA_LABEL: self.model_params_schema,
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
            logging.info("syncing files to job container")
            server_path = job.server_entrypoint()
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

    def stream(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        batch_type: BatchType = BatchType.TRAIN,
    ) -> Iterator[Tuple[X, Y]]:
        """Stream data

        Args:
            batch_size (int, optional): Size of the batch. Defaults to DEFAULT_BATCH_SIZE.
            batch_type (BatchType, optional): Type of the batch. Defaults to BatchType.TRAIN.

        Yields:
            Iterator[Tuple[X, Y]]: An iterator of X and Y
        """
        server_addr = f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes:{SERVER_PORT}"

        # you need to create your own socket here
        sock = socket.create_connection((f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes", SERVER_PORT))
        if self.uid is None:
            self.uid = uuid.uuid4()
        ws = create_connection(
            f"ws://{server_addr}/stream?batch_size={batch_size}&batch_type={batch_type}",
            header=[f"client-uuid: {self.uid}"],
            socket=sock,
        )
        try:
            while True:
                _, data = ws.recv_data()
                if self.x_cls is None or self.y_cls is None:
                    print("self dict: ", self.__dict__)
                    args = typing.get_args(self.__orig_class__)
                    self.x_cls: Type[X] = args[0]
                    self.y_cls: Type[Y] = args[1]

                jdict = json.loads(data)
                end = jdict["end"]
                if end:
                    break
                x = self.x_cls.load_dict(jdict["x"])
                y = self.y_cls.load_dict(jdict["y"])
                yield (x, y)

        except Exception as e:
            print("stream exception: ", e)
            raise e

    def sample(self, batch_size: int = DEFAULT_BATCH_SIZE) -> Tuple[X, Y]:
        """Sample data

        Args:
            batch_size (int, optional): Size of the batch. Defaults to 32.

        Returns:
            Tuple[X, Y]: A tuple of X and Y
        """

        params = parse.urlencode({"batch_size": batch_size})
        req = request.Request(f"{self.server_addr}/sample?{params}")
        resp = request.urlopen(req)
        resp_data = resp.read().decode("utf-8")

        if self.x_cls is None:
            args = typing.get_args(self.__orig_class__)
            self.x_cls: Type[X] = args[0]
            self.y_cls: Type[Y] = args[1]

        jdict = json.loads(resp_data)
        x = self.x_cls.load_dict(jdict["x"])
        y = self.y_cls.load_dict(jdict["y"])
        return (x, y)

    def evaluate(
        self,
        model: Union[SupervisedModel[X, Y], SupervisedModelClient[X, Y]],
        batch_size: int = DEFAULT_BATCH_SIZE,
        store: bool = True,
    ) -> EvalReport:
        """Evaluate a model

        Args:
            model (SupervisedModel | SupervisedModelClient): Model to evaluate
            batch_size (int): Batch size. Defaults to 32
            store (bool): Store the report as an artifact. Defaults to True

        Returns:
            Report: A report of the evaluation
        """
        if self.y_cls is None:
            args = typing.get_args(self.__orig_class__)
            self.x_cls: Type[X] = args[0]
            self.y_cls: Type[Y] = args[1]

        if type(model) == SupervisedModel:
            uri = model.image()
        else:
            uri = model.uri

        if uri is None:
            raise ValueError("model uri cannot be none")

        params = json.dumps({"model_uri": uri, "batch_size": batch_size, "store": store}).encode("utf8")
        req = request.Request(f"{self.server_addr}/evaluate", data=params, headers={"content-type": "application/json"})
        resp = request.urlopen(req)
        resp_data = resp.read().decode("utf-8")
        js = json.loads(resp_data)

        rd = js["report"]

        report = self.y_cls.score_cls().report_cls()(**rd)

        return report

    def _set_internal_types():
        pass

    def leaderboard(self) -> List[EvalReport]:
        """Leaderboard shows the top perorming models

        Returns:
            List[EvalReport]: List of eval reports
        """
        if self.y_cls is None:
            args = typing.get_args(self.__orig_class__)
            self.x_cls: Type[X] = args[0]
            self.y_cls: Type[Y] = args[1]

        req = request.Request(f"{self.server_addr}/leaderboard")
        resp = request.urlopen(req)
        resp_data = resp.read().decode("utf-8")

        r = json.loads(resp_data)
        leader_dict = r["leaderboard"]
        report_cls = self.y_cls.score_cls().report_cls()

        reports = []
        for leader in leader_dict:
            reports.append(report_cls.load_dict(leader))

        return reports


class Job(ABC):
    """A machine learning job"""

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of the job"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the job"""
        pass

    @abstractmethod
    def leaderboard(self) -> List[EvalReport]:
        """Leaderboard shows the top perorming models"""
        pass

    @classmethod
    def opts(cls: Type["Job"]) -> Opts:
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

    @classmethod
    def from_opts(cls: Type["Job"], opts: Opts) -> "Job":
        return cls(**opts.__dict__)


class SupervisedJob(Generic[X, Y], Job):
    """A supervised learning job"""

    x_cls: Optional[Type[X]] = None
    y_cls: Optional[Type[Y]] = None
    _uri: Optional[str] = None

    @abstractmethod
    def stream(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        batch_type: BatchType = BatchType.TRAIN,
    ) -> Iterator[Tuple[X, Y]]:
        """Stream data

        Args:
            batch_size (int, optional): Size of the batch. Defaults to DEFAULT_BATCH_SIZE.
            batch_type (BatchType, optional): Type of the batch. Defaults to BatchType.TRAIN.

        Yields:
            Iterator[Tuple[X, Y]]: An iterator of X and Y
        """
        pass

    @abstractmethod
    def sample(self, batch_size: int = DEFAULT_BATCH_SIZE) -> Tuple[X, Y]:
        """Sample data

        Args:
            batch_size (int, optional): Size of the batch. Defaults to DEFAULT_BATCH_SIZE.

        Returns:
            Tuple[X, Y]: A tuple of X and Y
        """
        pass

    @property
    def uri(self) -> str:
        if self._uri is None:
            return f"{self.__module__}.{self.__class__.__name__}"
        return self._uri

    @uri.setter
    def uri(self, val: str):
        self._uri = val

    def evaluate(
        self,
        model: Union[SupervisedModel[X, Y], SupervisedModelClient[X, Y]],
        batch_size: int = DEFAULT_BATCH_SIZE,
        store: bool = True,
    ) -> EvalReport:
        """Evaluate a model

        Args:
            model (SupervisedModel | SupervisedModelClient): Model to evaluate
            batch_size (int): Batch size. Defaults to 32
            store (bool): Store the report as an artifact. Defaults to True

        Returns:
            Report: A report of the evaluation
        """
        score: Score = None
        if self.y_cls is None:
            orig_bases = self.__orig_bases__
            if len(orig_bases) == 0:
                raise ValueError("No X/Y was provided to base class")

            orig_class = orig_bases[0]
            args = typing.get_args(orig_class)
            self.x_cls: Type[X] = args[0]
            self.y_cls: Type[Y] = args[1]

        for x, y in self.stream(batch_size=batch_size, batch_type=BatchType.TEST):
            y_pred = model.predict(x)
            score = self.y_cls.score_cls()(y, y_pred) + score
            print(str(score))

        logging.info("checking if model should be saved")
        model_uri = type(model).__name__
        if type(model) == SupervisedModel:
            if store:
                logging.info("saving model...")
                model_uri = model.image()
        else:
            # TODO: proper parser for modelenv
            if "modelenv" in model.uri:
                logging.info("model client is in develop mode, storing model as an image...")
                model_uri = model.save()
            else:
                logging.info("model already a complete image")
                model_uri = model.uri

        if self.uri is None:
            self.uri = type(self).__name__
            if store:
                self.uri = self.base_image()

        # Save report
        logging.info(f"creating report for model: {model_uri} and job: {self.uri}")
        report = score.report(model_uri, self.uri)
        print("report: ", report)
        if store:
            report.store()

        return report

    def leaderboard(self) -> List[EvalReport]:
        """Leaderboard shows the top perorming models

        Returns:
            List[EvalReport]: List of eval reports
        """
        orig_bases = self.__orig_bases__
        if len(orig_bases) == 0:
            raise ValueError("No X/Y was provided to base class")

        orig_class = orig_bases[0]
        args = typing.get_args(orig_class)
        y_cls: Type[Y] = args[1]

        hints = typing.get_type_hints(y_cls.score_cls().report)
        report_cls: EvalReport = hints["return"]
        if self.uri is None:
            raise ValueError("Job has never been stored, use image() to store job")
        return report_cls.find(artifact_uri=self.uri)

    @classmethod
    def _set_args(cls) -> None:
        orig_bases = cls.__orig_bases__
        if len(orig_bases) == 0:
            raise ValueError("No X/Y was provided to base class")

        orig_class = orig_bases[0]
        args = typing.get_args(orig_class)
        cls.x_cls: Type[X] = args[0]
        cls.y_cls: Type[Y] = args[1]

        return None

    @classmethod
    def server_entrypoint(cls, num_workers: int = 1, scm: Optional[SCM] = None) -> str:
        orig_bases = cls.__orig_bases__
        if len(orig_bases) == 0:
            raise ValueError("No X/Y was provided to base class")

        orig_class = orig_bases[0]
        args = typing.get_args(orig_class)
        x_cls: Type[X] = args[0]
        y_cls: Type[Y] = args[1]

        obj_module = inspect.getmodule(cls)
        if obj_module is None:
            raise SystemError(f"could not find module for func {obj_module}")

        if scm is None:
            scm = SCM()
        version = scm.sha()

        mod_x = inspect.getmodule(x_cls)
        if mod_x is not None:
            mod_x = mod_x.__name__

        mod_y = inspect.getmodule(y_cls)
        if mod_y is not None:
            mod_y = mod_y.__name__

        cls_name = cls.__name__

        cls_file_path = Path(inspect.getfile(cls))
        cls_file = cls_file_path.stem
        # cls_dir = os.path.dirname(os.path.realpath(str(cls_file_path)))
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

from simple_parsing import ArgumentParser
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.schemas import SchemaGenerator
import uvicorn

from arc.data.encoding import ShapeEncoder
from arc.model.metrics import Metrics
from arc.model.types import SupervisedModel, SupervisedModelClient
from arc.scm import SCM

from {cls_file} import {cls.__name__}
from {cls_file} import *
from {mod_x} import {x_cls.__name__}
from {mod_y} import {y_cls.__name__}

logging.basicConfig(level=logging.INFO)

parser = ArgumentParser()
parser.add_arguments({cls_name}.opts(), dest="{cls_name.lower()}")

args = parser.parse_args()

cfg_file = Path("./{JOB_CONFIG_FILE_NAME}")

scm = SCM()

if cfg_file.is_file():
    opts = {cls.__name__}.opts().load_json("./{JOB_CONFIG_FILE_NAME}")
    job = {cls.__name__}.from_opts(opts)
else:
    job = {cls.__name__}.from_opts(args.{cls_name.lower()})


uri = os.getenv("JOB_URI")
print("setting job uri: ", uri)
job.uri = uri

global_client_uuid = ""

async def on_start():
    global global_client_uuid
    global_client_uuid = ""

app = Starlette(debug=True, on_startup=[on_start])

schemas = SchemaGenerator(
    {{"openapi": "3.0.0", "info": {{"title": "{cls_name}", "version": "{version}"}}}}
)

@app.route("/health")
def health(request):
    return JSONResponse({{"status": "alive"}})

@app.route("/info")
def info(request):
    return JSONResponse({{"version": scm.sha()}})


@app.route("/description")
def description(request):
    return JSONResponse({{"description": job.description}})


@app.route("/name")
def name(request):
    return JSONResponse({{"name": job.name}})


@app.route("/uri")
def uri(request):
    return JSONResponse({{"uri": uri}})


@app.route("/leaderboard")
async def leaderboard(request):
    leaders = job.leaderboard()
    ret = []
    for leader in leaders:
        ret.append(leader.repr_json())
    return JSONResponse({{"leaderboard": ret}})


class ShapeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(content, cls=ShapeEncoder).encode('utf-8')


# Use websockets...
@app.websocket_route('/stream')
async def stream(websocket):
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


@app.route("/sample", methods=["GET"])
async def sample(request):
    params = request.query_params
    batch_size = params.get("batch_size", DEFAULT_BATCH_SIZE)

    x, y = job.sample(int(batch_size))
    resp = {{"x": x.repr_json(), "y": y.repr_json()}}
    return JSONResponse(resp)


@app.route("/evaluate", methods=["POST"])
async def evaluate(request):
    jdict = await request.json()
    try:
        model_uri = jdict['model_uri']
        print("model_uri: ", model_uri)

        opts = jdict.get("opts", None)
        batch_size = jdict.get("batch_size", 32)
        store = jdict.get("store", True)

        if opts is None:
            model = SupervisedModelClient[{x_cls.__name__}, {y_cls.__name__}](model_uri)
        else:
            model = SupervisedModelClient[{x_cls.__name__}, {y_cls.__name__}](model_uri, **opts)

    except Exception as e:
        print(e)
        raise

    report = job.evaluate(model, batch_size, store)

    return JSONResponse({{"report": report.repr_json()}})


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
        """Create a server image with the saved model"""

        if scm is None:
            scm = SCM()

        orig_bases = cls.__orig_bases__
        if len(orig_bases) == 0:
            raise ValueError("No X/Y was provided to base class")

        orig_class = orig_bases[0]
        args = typing.get_args(orig_class)
        x_cls: Type[X] = args[0]
        y_cls: Type[Y] = args[1]

        # write the server file somewhere we can find it
        server_filepath = Path(cls.server_entrypoint())
        repo_root = Path(str(scm.git_repo.working_dir))
        root_relative = server_filepath.relative_to(repo_root)
        container_path = Path(REPO_ROOT).joinpath(root_relative)

        if sync_strategy == RemoteSyncStrategy.IMAGE:
            img_id = find_or_build_img(
                sync_strategy=RemoteSyncStrategy.IMAGE,
                command=img_command(str(container_path)),
                tag_prefix=f"job-{cls.__name__.lower()}-",
                labels={
                    JOB_BASE_NAME_LABEL: "SupervisedJob",
                    JOB_NAME_LABEL: cls.__name__,
                    JOB_VERSION_LABEL: scm.sha(),
                    JOB_X_DATA_LABEL: x_cls.__name__,
                    JOB_X_DATA_SCHEMA_LABEL: json.dumps(x_cls.json_schema()),
                    JOB_Y_DATA_LABEL: y_cls.__name__,
                    JOB_Y_DATA_SCHEMA_LABEL: json.dumps(y_cls.json_schema()),
                    JOB_PARAMS_SCHEMA_LABEL: json.dumps(cls.opts().json_schema()),
                    JOB_SERVER_PATH_LABEL: str(container_path),
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
                tag=f"jobenv-{cls.__name__.lower()}-{scm.env_sha()}",
                labels={
                    JOB_BASE_NAME_LABEL: "SupervisedJob",
                    JOB_NAME_LABEL: cls.__name__,
                    JOB_VERSION_LABEL: scm.sha(),
                    JOB_X_DATA_LABEL: x_cls.__name__,
                    JOB_X_DATA_SCHEMA_LABEL: json.dumps(x_cls.json_schema()),
                    JOB_Y_DATA_LABEL: y_cls.__name__,
                    JOB_Y_DATA_SCHEMA_LABEL: json.dumps(y_cls.json_schema()),
                    JOB_PARAMS_SCHEMA_LABEL: json.dumps(cls.opts().json_schema()),
                    JOB_SERVER_PATH_LABEL: str(container_path),
                    ENV_SHA_LABEL: scm.env_sha(),
                    REPO_NAME_LABEL: scm.name(),
                    REPO_SHA_LABEL: scm.sha(),
                },
                dev_dependencies=dev_dependencies,
            )

        if clean:
            os.remove(server_filepath)

        return str(img_id)

    @classmethod
    def deploy(
        cls,
        scm: Optional[SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.IMAGE,
        **kwargs,
    ) -> SupervisedJobClient[X, Y]:
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

        img_id = cls.base_image(scm, clean=clean, dev_dependencies=dev_dependencies, sync_strategy=sync_strategy)

        client = SupervisedJobClient[x_cls, y_cls](
            uri=img_id, sync_strategy=sync_strategy, dev_dependencies=dev_dependencies, **kwargs
        )
        return client

    @classmethod
    def develop(
        cls,
        scm: Optional[SCM] = None,
        dev_dependencies: bool = True,
        clean: bool = True,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.CONTAINER,
        **kwargs,
    ) -> SupervisedJobClient[X, Y]:
        """Develop against the class remotely"""

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

        client = SupervisedJobClient[x_cls, y_cls](
            job=cls, sync_strategy=sync_strategy, clean=clean, dev_dependencies=dev_dependencies, scm=scm, **kwargs
        )
        return client

    @classmethod
    def versions(
        cls: Type["SupervisedJob"], repositories: Optional[List[str]] = None, cfg: Optional[Config] = None
    ) -> List[str]:
        """Find all versions of this job

        Args:
            cls (Type[SupervisedJob]): The SupervisedJob class
            repositories (List[str], optional): Extra repositories to check
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
                if f"job-{cls.__name__.lower()}" in tag:
                    ret.append(f"{repo_uri}:{tag}")
        return ret


class UnsupervisedJob(Generic[X], Job):
    """An unsupervised learning job"""

    # TODO: this should be a mixin that comes from the shapestream
    @abstractmethod
    def stream(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        batch_type: BatchType = BatchType.TRAIN,
    ) -> Iterator[X]:
        """Stream data

        Args:
            batch_size (int, optional): Size of the batch. Defaults to DEFAULT_BATCH_SIZE.
            batch_type (BatchType, optional): Type of the batch. Defaults to BatchType.TRAIN.

        Yields:
            Iterator[X]: An iterator of X
        """
        pass

    @abstractmethod
    def sample(self, batch_size: int = DEFAULT_BATCH_SIZE) -> X:
        """Sample data

        Args:
            batch_size (int, optional): Size of the batch. Defaults to DEFAULT_BATCH_SIZE.

        Returns:
            X: An X
        """
        pass

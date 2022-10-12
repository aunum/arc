from typing import Dict, Generic, TypeVar, List, Any, Optional, Type, Union, get_args
import inspect
import time
import logging
import os
import socket
import json
from pathlib import Path

from kubernetes import config
from kubernetes.stream import portforward
from kubernetes.client.models import (
    V1VolumeMount,
    V1Pod,
    V1PodSpec,
    V1PodList,
    V1Container,
    V1ContainerPort,
    V1Volume,
    V1Probe,
    V1ExecAction,
    V1SecretVolumeSource,
    V1KeyToPath,
    V1EnvVarSource,
    V1EnvVar,
    V1ObjectFieldSelector,
)
from kubernetes.client import CoreV1Api, V1ObjectMeta, RbacAuthorizationV1Api
from urllib import request
from docker.utils.utils import parse_repository_tag
from docker.auth import resolve_repository_name
import uuid


from arc.data.types import Data, EvalReport
from arc.kube.sync import copy_file_to_pod
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
from arc.kube.env import is_k8s_proc
from arc.kube.auth_util import ensure_cluster_auth_resources
from arc.data.job import SupervisedJob, SupervisedJobClient
from arc.model.types import (
    SupervisedModel,
    SupervisedModelClient,
    ModelPhase,
    MODEL_X_DATA_LABEL,
    MODEL_X_DATA_SCHEMA_LABEL,
    MODEL_Y_DATA_LABEL,
    MODEL_Y_DATA_SCHEMA_LABEL,
)
from arc.generic import RuntimeGeneric

X = TypeVar("X", bound="Data")
Y = TypeVar("Y", bound="Data")

SERVER_PORT = "8080"
ARC_VERSION_LABEL = "arc-version"
TRAINER_SERVER_PATH_LABEL = "server-path"
TRAINER_LABEL = "trainer"
TRAINER_NAME_LABEL = "name"
TRAINER_VERSION_LABEL = "version"
TRAINER_BASE_NAME_LABEL = "base"
SERVER_PORT = "8080"


class TrainerClient(Generic[X, Y]):
    """A client for training models"""

    pod_name: str
    pod_namespace: str
    core_v1_api: CoreV1Api
    xcls: Optional[Type[X]] = None
    ycls: Optional[Type[Y]] = None
    uri: Optional[str] = None
    server_addr: str
    model_x_type: str
    model_y_type: str

    def __init__(
        self,
        uri: Optional[str] = None,
        trainer: Optional["Trainer"] = None,
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
        """Client for a Trainer

        Args:
            uri (Optional[str], optional): URI to create Trainer from. Defaults to None.
            trainer (Optional[&quot;Trainer&quot;], optional): Trainer to create a client from. Defaults to None.
            core_v1_api (Optional[CoreV1Api], optional): K8s CoreV1API to use. Defaults to None.
            rbac_v1_api (Optional[RbacAuthorizationV1Api], optional): K8s RBACV1API to use. Defaults to None.
            docker_socket (Optional[str], optional): Docker socket to use. Defaults to None.
            namespace (Optional[str], optional): Namespace to use. Defaults to None.
            cfg (Optional[Config], optional): Config to use. Defaults to None.
            scm (Optional[SCM], optional): SCM to use. Defaults to None.
            sync_strategy (RemoteSyncStrategy, optional): Sync strategy to use. Defaults to RemoteSyncStrategy.IMAGE.
            dev_dependencies (bool, optional): Whether to install dev dependencies in image. Defaults to False.
        """
        self.uri = uri

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

        # We need to get metadata on the model by looking at the registry and pulling metadata
        if docker_socket is None:
            docker_socket = default_socket()

        if cfg is None:
            cfg = Config()

        if scm is None:
            scm = SCM()

        if namespace is None:
            namespace = cfg.kube_namespace

        if trainer is not None:
            self.uri = trainer.base_image(scm=scm, dev_dependencies=dev_dependencies, sync_strategy=sync_strategy)

        # Check schema compatibility between client/server
        img_labels = get_img_labels(self.uri)

        if img_labels is None:
            raise ValueError(f"image uri '{self.uri}' does not contain any labels, are you sure it was build by arc?")

        self.server_path = img_labels[TRAINER_SERVER_PATH_LABEL]
        self.model_x_schema = img_labels[MODEL_X_DATA_SCHEMA_LABEL]
        self.model_y_schema = img_labels[MODEL_Y_DATA_SCHEMA_LABEL]
        self.model_x_type = img_labels[MODEL_X_DATA_LABEL]
        self.model_y_type = img_labels[MODEL_Y_DATA_LABEL]

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
            if TRAINER_LABEL in annotations:
                server_model_uri = annotations[TRAINER_LABEL]
                if server_model_uri == self.uri:
                    logging.info("found trainer running in cluster")
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
                        if trainer is None:
                            raise ValueError("trainer cannot be none when doing a container sync")
                        server_path = trainer.server_entrypoint()
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
                        # it will just return the original verion, how do we sync the verion with the
                        # files to tell if its running?
                        # TODO! https://github.com/aunum/arc/issues/11
                        logging.info(self.info())
                    return

        logging.info("model not found running, deploying now...")
        repository, tag = parse_repository_tag(self.uri)
        _, repo_name = resolve_repository_name(repository)
        project_name = repo_name.split("/")[1]

        # need to know if this should have a configmap
        pod_name = f"{str(project_name).replace('/', '-')}-{tag}"
        if len(pod_name) > 57:
            pod_name = pod_name[:56]

        uid = str(uuid.uuid4())
        pod_name = pod_name + "-" + uid[:5]

        logging.info("ensuring cluster auth resources...")
        auth_resources = ensure_cluster_auth_resources(core_v1_api, rbac_v1_api, docker_socket, namespace, cfg)

        # if not deploy
        container = V1Container(
            name="server",
            command=img_command(self.server_path),
            image=self.uri,
            ports=[V1ContainerPort(container_port=int(SERVER_PORT))],
            env=[
                V1EnvVar(
                    name="POD_NAME",
                    value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path="metadata.name")),
                )
            ],
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
        )
        container.volume_mounts = [
            V1VolumeMount(name="dockercfg", mount_path="/root/.docker"),
        ]

        spec = V1PodSpec(
            containers=[container],
            service_account_name=auth_resources.service_account_name,
        )
        spec.volumes = [
            V1Volume(
                name="dockercfg",
                secret=V1SecretVolumeSource(
                    secret_name=auth_resources.secret_name,
                    items=[V1KeyToPath(key=".dockerconfigjson", path="config.json")],
                ),
            ),
        ]

        pod = V1Pod(
            metadata=V1ObjectMeta(
                name=pod_name,
                namespace=namespace,
                labels={
                    TYPE_LABEL: "trainer",
                    REPO_SHA_LABEL: scm.sha(),
                    ENV_SHA_LABEL: scm.env_sha(),
                    REPO_NAME_LABEL: scm.name(),
                    SYNC_STRATEGY_LABEL: str(sync_strategy),
                },
                annotations={
                    TRAINER_LABEL: self.uri,
                    MODEL_X_DATA_SCHEMA_LABEL: self.model_x_schema,
                    MODEL_Y_DATA_SCHEMA_LABEL: self.model_y_schema,
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
            if trainer is None:
                raise SystemError("cannot sync files to a container without a model parameter passed in init")
            server_path = trainer.server_entrypoint()
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

    def train(
        self,
        job: Union[SupervisedJob[X, Y], SupervisedJobClient[X, Y], str],
        model: Optional[
            Union[
                SupervisedModel[X, Y],
                SupervisedModelClient[X, Y],
                List[Union[SupervisedModel[X, Y], SupervisedModelClient[X, Y]]],
                str,
                List[str],
            ]
        ] = None,
        max_parallel: int = 10,
        max_search: int = 20,
        evaluate: bool = True,
        dev_dependencies: bool = False,
    ) -> Dict[str, EvalReport]:
        """Train the models for the job

        Args:
            job (SupervisedJob[X, Y] | SupervisedJobClient[X, Y] | str): Job to train for
            model (Optional[ SupervisedModel[X, Y]  |  SupervisedModelClient[X, Y]  |  List[SupervisedModel[X, Y]  |  SupervisedModelClient[X, Y]]  |  str  |  List[str] ], optional): Models to train. Defaults to None.
            max_parallel (int, optional): Maximum parallel models to train. Defaults to 10.
            max_search (int, optional): Maximum search space when no models are provided. Defaults to 20.
            evaluate (bool, optional): Whether to evalute the models. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies for local models. Defaults to False

        Returns:
            Dict[str, EvalReport]: A dictionary of model URI to report
        """  # noqa: E501

        models: List[str] = []
        if isinstance(model, SupervisedModel):
            models = [model.deploy(dev_dependencies=dev_dependencies).uri]
        elif isinstance(model, SupervisedModelClient):
            models = [model.uri]
        elif isinstance(model, str):
            # create client
            logging.info(f"creating model for {model}")
            models = [model]
        elif SupervisedModel in model.__bases__:
            models = [model.deploy(dev_dependencies=dev_dependencies).uri]
        elif isinstance(model, list):
            for m in model:
                if isinstance(m, str):
                    models.append(m)
                elif isinstance(m, SupervisedModelClient):
                    models.append(m.uri)
                elif isinstance(m, SupervisedModel):
                    logging.info(f"creating deployment for model {m.uri}")
                    models.append(m.deploy(dev_dependencies=dev_dependencies).uri)
                else:
                    raise SystemError(f"unknown type: {type(m)}")
        else:
            raise SystemError(f"unsupported type for 'model': {type(model)}")

        job_uri = ""
        if isinstance(job, str):
            job_uri = job
            if "jobenv" in job and not job.startswith("k8s://"):
                raise ValueError("cannot use a jobenv that is not a k8s uri, too ambiguous. Try passing job.k8s_uri()")
        elif isinstance(job, SupervisedJob):
            logging.info(f"creating deployment for job: {job.uri}")
            job_uri = job.deploy(dev_dependencies=dev_dependencies).uri
        elif isinstance(job, SupervisedJobClient):
            job_uri = job.uri
            if "jobenv" in job_uri:
                logging.info("copying jobenv")
                running_job = job.copy()
                job_uri = running_job.k8s_uri()
        elif SupervisedJob in job.__bases__:
            logging.info(f"creating deployment for job: {job.uri}")
            job_uri = job.deploy(dev_dependencies=dev_dependencies).uri
        else:
            raise SystemError(f"unsupported type for 'job': {type(job)}")

        # use the connection to call standardized methods
        params = json.dumps(
            {
                "job": job_uri,
                "model": models,
                "max_parallel": max_parallel,
                "max_search": max_search,
                "evaluate": evaluate,
            }
        ).encode("utf8")
        print("params: ", params)
        req = request.Request(f"{self.server_addr}/train", data=params, headers={"content-type": "application/json"})
        resp = request.urlopen(req)
        resp_data = resp.read().decode("utf-8")

        reports = json.loads(resp_data)
        return reports


class Trainer(RuntimeGeneric, Generic[X, Y]):
    """Trainer of models"""

    def train(
        self,
        job: Union[SupervisedJob[X, Y], SupervisedJobClient[X, Y], str],
        model: Optional[
            Union[
                SupervisedModel[X, Y],
                SupervisedModelClient[X, Y],
                List[SupervisedModel[X, Y]],
                List[SupervisedModelClient[X, Y]],
                str,
                List[str],
            ]
        ] = None,
        max_parallel: int = 10,
        max_search: int = 20,
        evaluate: bool = True,
        destroy: bool = True,
    ) -> Dict[str, EvalReport]:
        """Train models for a job

        Args:
            job (SupervisedJob[X, Y] | SupervisedJobClient[X, Y] | str): Job to train for
            model (Optional[SupervisedModel[X, Y]  |  List[SupervisedModel[X, Y]] | SupervisedModelClient[X, Y] | List[SupervisedModelClient[X, Y]] | str | List[str]], optional): Models to train, if None, it will search for models. Defaults to None.
            max_parallel (int, optional): Maximum parallel models to train. Defaults to 10.
            max_search (int, optional): Maximum number of models to search for if none are provided. Defaults to 20.
            evaluate (bool, optional): Wether to evaluate. Defaults to True.
            destroy (bool, optional): Whether to destory the running models after evaluation, they will still be saved as artifacts. Defaults to True.
        """  # noqa: E501

        args = get_args(self.__orig_class__)
        x_cls: Type[X] = args[0]
        y_cls: Type[Y] = args[1]

        models: List[Union[SupervisedModel[x_cls, y_cls], SupervisedModelClient[x_cls, y_cls]]] = []
        if isinstance(model, SupervisedModel) or isinstance(model, SupervisedModelClient):
            models = [model]
        elif isinstance(model, str):
            # create client
            logging.info(f"creating model for {model}")
            models = [SupervisedModelClient[x_cls, y_cls](uri=model)]
        elif isinstance(model, list):
            for m in model:
                if isinstance(m, str):
                    logging.info(f"creating deployment for model {m}")
                    models.append(SupervisedModelClient[x_cls, y_cls](uri=m))
                elif isinstance(m, SupervisedModelClient):
                    models.append(m.uri)
                elif isinstance(m, SupervisedModel):
                    logging.info(f"creating model for {m.uri}")
                    models.append(SupervisedModelClient[x_cls, y_cls](model=m))
                else:
                    raise SystemError(f"unknown type: {type(m)}")
        else:
            raise SystemError(f"unknown type: {type(m)}")

        if model is None:
            # find models
            raise NotImplementedError("automl not yet implemented")

        if isinstance(job, str):
            print("creating job!!!")
            print(job)
            if "jobenv" in job and not job.startswith("k8s://"):
                raise ValueError("cannot use a jobenv that is not a k8s uri, too ambiguous. Try passing job.k8s_uri()")
            logging.info(f"creating deployment for job '{job}'")
            job = SupervisedJobClient[x_cls, y_cls](uri=job)
        else:
            print("not creating job!!!")
            print(job)

        # compile the models
        sample_x, sample_y = job.sample(1)
        logging.info(f"sample y: {sample_y}")

        compat_models = []
        for modl in models:
            info = modl.info()
            phase = modl.phase()
            logging.info(f"training model: {info}")

            if phase == ModelPhase.COMPILED.value or phase == ModelPhase.TRAINED.value:
                x, y = modl.io()
                if x is None:
                    raise SystemError("model is compiled but returns no IO")
                if not sample_x.compatible(x) or not sample_y.compatible(y):
                    logging.warning(f"model '{modl.name()}' is not compatible with the job, skipping")
                    continue
                compat_models.append(modl)
            logging.info(f"compiling model: {modl}")
            modl.compile(sample_x, sample_y)

        models = compat_models

        logging.info(f"training {len(models)} models")
        for x, y in job.stream():
            logging.debug(f"sending x: {x}")
            logging.debug(f"sending y: {y}")

            for modl in models:
                metrics = modl.fit(x, y)
                logging.info(f"model: {modl.uri} metrics: {metrics}")

        ret = {}
        if evaluate:
            for modl in models:
                logging.info(f"evaluating model: {modl}")
                report = job.evaluate(modl)
                logging.info(f"model {modl.uri} report: {report}")
                ret[modl.uri] = report

        if destroy:
            for modl in models:
                logging.info(f"deleting model {modl.uri}")
                modl.delete()

        return ret

    @classmethod
    def server_entrypoint(cls, num_workers: int = 1, scm: Optional[SCM] = None) -> str:

        # Lots of fun hacks from https://github.com/python/typing/issues/629 yay python!
        x_cls: Type[X] = cls.__args__[0]
        y_cls: Type[Y] = cls.__args__[1]

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

        cls_file_path = Path(inspect.getfile(cls._generic.__origin__))
        cls_file = cls_file_path.stem
        # cls_dir = os.path.dirname(os.path.realpath(str(cls_file_path)))
        server_file_name = f"{cls._generic.__origin__.__name__.lower()}_server.py"
        server_file = f"""
import logging
from typing import Any, Dict
from dataclasses import dataclass
import os
import time

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.schemas import SchemaGenerator
import uvicorn

from arc.scm import SCM
from arc.model.trainer import Trainer

from {cls_file} import {cls.__name__}
from {cls_file} import *
from {mod_x} import {x_cls.__name__}
from {mod_y} import {y_cls.__name__}

logging.basicConfig(level=logging.INFO)

scm = SCM()

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
    return JSONResponse({{"version": scm.sha(), "env-sha": scm.env_sha()}})


@app.route('/train', methods=["POST"])
async def train(request):
    update_ts()
    jdict = await request.json()
    trainer = Trainer[{x_cls.__name__}, {y_cls.__name__}]()
    res = trainer.train(**jdict)

    ret = {{}}
    for model_uri, report in res.items():
        ret[model_uri] = report.repr_json()

    return JSONResponse(ret)


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

        class_file = inspect.getfile(cls._generic.__origin__)
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
        """Create a server image with the saved model

        Args:
            scm (Optional[SCM], optional): Optional SCM to use. Defaults to None.
            clean (bool, optional): Whether to clean the generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            sync_strategy (RemoteSyncStrategy, optional): Sync strategy to use. Defaults to RemoteSyncStrategy.IMAGE.

        Returns:
            str: URI of the image
        """

        if scm is None:
            scm = SCM()

        x_cls: Type[X] = cls.__args__[0]
        y_cls: Type[Y] = cls.__args__[1]

        # write the server file somewhere we can find it
        server_filepath = Path(cls.server_entrypoint())
        repo_root = Path(str(scm.git_repo.working_dir))
        root_relative = server_filepath.relative_to(repo_root)
        container_path = Path(REPO_ROOT).joinpath(root_relative)

        name = f"{x_cls.short_name()}-{y_cls.short_name()}"

        if sync_strategy == RemoteSyncStrategy.IMAGE:
            img_id = find_or_build_img(
                sync_strategy=RemoteSyncStrategy.IMAGE,
                command=img_command(str(container_path)),
                tag_prefix=f"trainer-{name}-",
                labels={
                    TRAINER_BASE_NAME_LABEL: "Trainer",
                    TRAINER_NAME_LABEL: cls.__name__,
                    TRAINER_VERSION_LABEL: scm.sha(),
                    MODEL_X_DATA_LABEL: x_cls.__name__,
                    MODEL_X_DATA_SCHEMA_LABEL: json.dumps(x_cls.json_schema()),
                    MODEL_Y_DATA_LABEL: y_cls.__name__,
                    MODEL_Y_DATA_SCHEMA_LABEL: json.dumps(y_cls.json_schema()),
                    TRAINER_SERVER_PATH_LABEL: str(container_path),
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
                tag=f"trainerenv-{name}-{scm.env_sha()}",
                labels={
                    TRAINER_BASE_NAME_LABEL: "Trainer",
                    TRAINER_NAME_LABEL: cls.__name__,
                    TRAINER_VERSION_LABEL: scm.sha(),
                    MODEL_X_DATA_LABEL: x_cls.__name__,
                    MODEL_X_DATA_SCHEMA_LABEL: json.dumps(x_cls.json_schema()),
                    MODEL_Y_DATA_LABEL: y_cls.__name__,
                    MODEL_Y_DATA_SCHEMA_LABEL: json.dumps(y_cls.json_schema()),
                    TRAINER_SERVER_PATH_LABEL: str(container_path),
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
    ) -> TrainerClient[X, Y]:
        """Create a deployment of the class, which will allow for the generation of instances remotely

        Args:
            scm (Optional[SCM], optional): Optional SCM to use. Defaults to None.
            clean (bool, optional): Whether to clean the generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install the dev dependencies. Defaults to False.
            sync_strategy (RemoteSyncStrategy, optional): Sync strategies to use. Defaults to RemoteSyncStrategy.IMAGE.

        Returns:
            TrainerClient[X, Y]: A trainer client
        """
        if scm is None:
            scm = SCM()

        x_cls: Type[X] = cls.__args__[0]
        y_cls: Type[Y] = cls.__args__[1]

        print("deploy x_cls: ", x_cls)
        print("deploy y_cls: ", y_cls)

        img_id = cls.base_image(scm, clean, dev_dependencies, sync_strategy=sync_strategy)

        client = TrainerClient[x_cls, y_cls](
            uri=img_id, sync_strategy=sync_strategy, dev_dependencies=dev_dependencies, **kwargs
        )
        return client

    @classmethod
    def develop(
        cls,
        scm: Optional[SCM] = None,
        dev_dependencies: bool = True,
        sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.CONTAINER,
        **kwargs,
    ) -> TrainerClient[X, Y]:
        """Develop against the class remotely

        Args:
            scm (Optional[SCM], optional): Optional SCM to use. Defaults to None.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to True.
            sync_strategy (RemoteSyncStrategy, optional): Which sync strategy to use. Defaults to RemoteSyncStrategy.CONTAINER.

        Returns:
            TrainerClient[X, Y]: A trainer client
        """  # noqa: E501

        if scm is None:
            scm = SCM()

        x_cls: Type[X] = cls.__args__[0]
        y_cls: Type[Y] = cls.__args__[1]

        print("dev x_cls: ", x_cls)
        print("dev y_cls: ", y_cls)

        client = TrainerClient[x_cls, y_cls](
            trainer=cls, sync_strategy=sync_strategy, dev_dependencies=dev_dependencies, scm=scm, **kwargs
        )
        return client

    @classmethod
    def versions(
        cls: Type["Trainer"], repositories: Optional[List[str]] = None, cfg: Optional[Config] = None
    ) -> List[str]:
        """Find all versions of this trainer

        Args:
            cls (Type[Trainer]): the Trainer class
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
                if f"trainer-{cls.__name__.lower()}" in tag:
                    ret.append(f"{repo_uri}:{tag}")
        return ret

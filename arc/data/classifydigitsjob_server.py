
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
from kubernetes import config
from kubernetes.client.models import (
    V1Pod,
)
from kubernetes.client import CoreV1Api, V1ObjectMeta

from arc.data.encoding import ShapeEncoder
from arc.model.metrics import Metrics
from arc.model.types import SupervisedModel, SupervisedModelClient
from arc.data.job import SupervisedJob, SupervisedJobClient
from arc.scm import SCM
from arc.kube.env import is_k8s_proc
from arc.image.build import REPO_ROOT, build_containerfile
from arc.image.file import write_containerfile
from arc.model.types import BUILD_MNT_DIR
from arc.kube.copy import copy_pod
from arc.kube.pod_util import (
    wait_for_pod_ready,
)
from arc.kube.uri import make_k8s_uri
from arc.kube.sync import copy_file_to_pod

from job_test import ClassifyDigitsJob
from job_test import *
from arc.data.shapes.image import ImageData
from arc.data.shapes.classes import ClassData

logging.basicConfig(level=logging.INFO)

parser = ArgumentParser()
parser.add_arguments(ClassifyDigitsJob.opts(), dest="classifydigitsjob")

args = parser.parse_args()

last_used_ts = time.time()

cfg_file = Path("./config.json")

scm = SCM()

if cfg_file.is_file():
    opts = ClassifyDigitsJob.opts().load_json("./config.json")
    job = ClassifyDigitsJob.from_opts(opts)
else:
    job = ClassifyDigitsJob.from_opts(args.classifydigitsjob)


uri = os.getenv("JOB_URI")
print("setting job uri: ", uri)
job.uri = uri

global_client_uuid = ""

async def on_start():
    global global_client_uuid
    global_client_uuid = ""

app = Starlette(debug=True, on_startup=[on_start])

schemas = SchemaGenerator(
    {"openapi": "3.0.0", "info": {"title": "ClassifyDigitsJob", "version": "5316caa-f0182aa"}}
)


def update_ts():
    global last_used_ts
    last_used_ts = time.time()


@app.route("/last_used")
def last_used(request):
    return JSONResponse({"elapsed": time.time() - last_used_ts})


@app.route("/health")
def health(request):
    return JSONResponse({"status": "alive"})


@app.route("/info")
def info(request):
    return JSONResponse({"name": "ClassifyDigitsJob", "version": scm.sha(), "uri": uri})


@app.route("/description")
def description(request):
    return JSONResponse({"description": job.description})


@app.route("/name")
def name(request):
    return JSONResponse({"name": job.name})


@app.route("/uri")
def uri(request):
    return JSONResponse({"uri": uri})


@app.route("/leaderboard")
async def leaderboard(request):
    update_ts()
    leaders = job.leaderboard()
    ret = []
    for leader in leaders:
        ret.append(leader.repr_json())
    return JSONResponse({"leaderboard": ret})


class ShapeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(content, cls=ShapeEncoder).encode('utf-8')


@app.route("/copy", methods=["POST"])
def copy(request):
    update_ts()
    logging.info("copying job")

    pod_name = os.getenv("POD_NAME")
    pod_namespace = os.getenv("POD_NAMESPACE")

    if is_k8s_proc():
        config.load_incluster_config()
    else:
        config.load_kube_config()

    core_v1_api = CoreV1Api()

    new_pod = copy_pod(pod_name, pod_namespace, core_v1_api)
    pod_name = new_pod.metadata.name

    logging.info("creating pod")
    # This should run the image on Kubernetes and store a connection to the server
    core_v1_api.create_namespaced_pod(pod_namespace, new_pod)

    # see if pod is ready
    ready = wait_for_pod_ready(pod_name, pod_namespace, core_v1_api)
    if not ready:
        raise SystemError(f"pod {pod_name} never became ready")

    logging.info(f"pod {pod_name} is ready")

    # TODO: handle readiness https://github.com/aunum/arc/issues/11
    time.sleep(10)

    logging.info("syncing files to model container")
    copy_file_to_pod(
        scm.all_files(absolute_paths=True),
        pod_name,
        namespace=pod_namespace,
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
    ready = wait_for_pod_ready(pod_name, pod_namespace, core_v1_api)
    if not ready:
        raise SystemError("pod never became ready")
    logging.info(f"pod {pod_name} is ready!")

    # We need to load the model in the new server!
    k8s_uri = make_k8s_uri(new_pod.metadata.name, new_pod.metadata.namespace)
    new_model = SupervisedJobClient(uri=k8s_uri)

    return JSONResponse({"uri": uri, "k8s_uri": k8s_uri})


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
        d = {"x": x_repr, "y": y_repr, "end": False}
        await websocket.send_json(d)
        print("sent")
        total_end = time.time()
        print("total loop time: ", total_end - total_start)

    # reset the uid to unlock
    global_client_uuid = ""
    print("sending end")
    await websocket.send_json({"end": True})
    print("all done sending data, closing socket")
    await websocket.close()


@app.route("/sample", methods=["GET"])
async def sample(request):
    update_ts()
    params = request.query_params
    batch_size = params.get("batch_size", DEFAULT_BATCH_SIZE)

    x, y = job.sample(int(batch_size))
    resp = {"x": x.repr_json(), "y": y.repr_json()}
    return JSONResponse(resp)


@app.route("/evaluate", methods=["POST"])
async def evaluate(request):
    update_ts()
    jdict = await request.json()
    try:
        model_uri = jdict['model_uri']
        print("model_uri: ", model_uri)

        opts = jdict.get("opts", None)
        batch_size = jdict.get("batch_size", 32)
        store = jdict.get("store", True)
        reuse = jdict.get("reuse", False)

        if not reuse and "modelenv" in model_uri:
            logging.info("getting client for model env")
            model = SupervisedModelClient[ImageData, ClassData](uri=model_uri, reuse=True)
            logging.info("copying model")
            new_model_info = model.copy()
            model = SupervisedModelClient[ImageData, ClassData](uri=new_model_info.k8s_uri)

        else:
            if opts is None:
                model = SupervisedModelClient[ImageData, ClassData](uri=model_uri, reuse=reuse)
            else:
                model = SupervisedModelClient[ImageData, ClassData](uri=model_uri, reuse=reuse, **opts)

    except Exception as e:
        print(e)
        raise

    report = job.evaluate(model, batch_size, store)

    return JSONResponse({"report": report.repr_json()})


@app.route("/schema")
def openapi_schema(request):
    return schemas.OpenAPIResponse(request=request)

if __name__ == "__main__":
    pkgs: Dict[str, str] = {}
    for fp in scm.all_files():
        dir = os.path.dirname(fp)
        pkgs[dir] = ""

    logging.info("starting server version '5316caa-f0182aa' on port: 8080")
    uvicorn.run("__main__:app", host="0.0.0.0", port=8080, log_level="info", workers=1, reload=True, reload_dirs=pkgs.keys())
        
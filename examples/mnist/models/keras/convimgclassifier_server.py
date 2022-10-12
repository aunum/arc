
import json
import logging
from typing import Any, Dict
from pathlib import Path
import time
import os
import shutil

from simple_parsing import ArgumentParser
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.schemas import SchemaGenerator
import uvicorn
from kubernetes import config
from kubernetes.client.models import (
    V1Pod,
)
from kubernetes.client import CoreV1Api, V1ObjectMeta

from arc.kube.env import is_k8s_proc
from arc.data.encoding import ShapeEncoder
from arc.scm import SCM
from arc.image.build import REPO_ROOT, build_containerfile
from arc.image.file import write_containerfile
from arc.model.types import BUILD_MNT_DIR
from arc.kube.copy import copy_pod
from arc.kube.pod_util import (
    wait_for_pod_ready,
)
from arc.kube.uri import make_k8s_uri
from arc.kube.sync import copy_file_to_pod
from arc.model.types import SupervisedModelClient

from classifier import ConvMultiClassImageClassifier
from classifier import *
from arc.data.shapes.image import ImageData
from arc.data.shapes.classes import ClassData

logging.basicConfig(level=logging.INFO)

parser = ArgumentParser()
parser.add_arguments(ConvMultiClassImageClassifier.opts(), dest="convmulticlassimageclassifier")

args = parser.parse_args()

model_file = Path("./model/model.pkl")
cfg_file = Path("./config.json")

scm = SCM()

last_used_ts = time.time()

if model_file.is_file():
    logging.info("loading model found locally")
    model: ConvMultiClassImageClassifier = ConvMultiClassImageClassifier.load()
elif cfg_file.is_file():
    logging.info("loading model from config file")
    model = ConvMultiClassImageClassifier.load_json("./config.json")
else:
    logging.info("loading model from args")
    model = ConvMultiClassImageClassifier.from_opts(args.convmulticlassimageclassifier)

uri = os.getenv("MODEL_URI")
model.uri = uri


# async def on_start():
#     global model
#     if model_file.is_file():
#         logging.info("loading model found locally")
#         model: ConvMultiClassImageClassifier = ConvMultiClassImageClassifier.load()


# app = Starlette(debug=True, on_startup=[on_start])
app = Starlette(debug=True)


schemas = SchemaGenerator(
    {"openapi": "3.0.0", "info": {"title": "ConvMultiClassImageClassifier", "version": "5316caa-99cc386"}}
)

def update_ts():
    global last_used_ts
    last_used_ts = time.time()


@app.route("/health")
def health(request):
    return JSONResponse({"status": "alive"})


@app.route("/phase")
def phase(request):
    return JSONResponse({"phase": model.phase().value})


@app.route("/copy", methods=["POST"])
def copy(request):
    update_ts()
    logging.info("saving model")

    model.save()
    logging.info("copying model")

    logging.info("building containerfile")
    c = build_containerfile()

    logging.info("writing containerfile")
    write_containerfile(c)

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
    new_model = SupervisedModelClient(uri=k8s_uri)

    logging.info("loading the model")
    new_model.load()

    return JSONResponse({"uri": uri, "k8s_uri": k8s_uri})


@app.route("/last_used")
def last_used(request):
    return JSONResponse({"elapsed": time.time() - last_used_ts})


@app.route("/info")
def info(request):
    # model_dict = model.opts().to_dict()
    return JSONResponse({"name": model.__class__.__name__, "version": scm.sha(), "env-sha": scm.env_sha(), "phase": model.phase().value, "uri": uri})


@app.route("/compile", methods=["POST"])
async def compile(request):
    update_ts()
    jdict = await request.json()

    try:
        x = ImageData.load_dict(jdict['x'])
    except Exception as e:
        print(e)
        raise

    try:
        y = ClassData.load_dict(jdict['y'])
    except Exception as e:
        print(e)
        raise

    try:
        model.compile(x, y)
    except Exception as e:
        print(e)
        raise
    return JSONResponse({"message": "model compiled"})


@app.route("/io")
def io(request):
    update_ts()
    x, y = model.io()
    if x is None or y is None:
        return JSONResponse({"x": None, "y": None})
    resp = {"x": x.repr_json(), "y": y.repr_json()}
    return JSONResponse(resp)


@app.route("/save", methods=["POST"])
def save(request):
    update_ts()
    logging.info("saving model")
    model.save()
    logging.info("building containerfile")
    c = build_containerfile()
    logging.info("writing containerfile")
    write_containerfile(c)
    logging.info("copying directory to build dir...")
    shutil.copytree(REPO_ROOT, BUILD_MNT_DIR, dirs_exist_ok=True)
    return JSONResponse({"message": "model saved"})


@app.route("/load", methods=["POST"])
async def load(request):
    update_ts()
    jdict = await request.json()
    global model
    model = ConvMultiClassImageClassifier.load(jdict["dir"])
    return JSONResponse({"message": "model loaded"})


@app.route("/fit", methods=["POST"])
async def fit(request):
    update_ts()
    jdict = await request.json()
    x = ImageData.load_dict(jdict['x'])
    y = ClassData.load_dict(jdict['y'])
    metrics = model.fit(x, y)
    return JSONResponse(metrics)


class ShapeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(content, cls=ShapeEncoder).encode('utf-8')


@app.route("/predict", methods=["POST"])
async def predict(request):
    update_ts()
    jdict = await request.json()
    x = ImageData.load_dict(jdict['x'])
    y = model.predict(x)
    # encode me
    return ShapeJSONResponse(y)


@app.route("/schema")
def openapi_schema(request):
    return schemas.OpenAPIResponse(request=request)


if __name__ == "__main__":
    pkgs: Dict[str, str] = {}
    for fp in scm.all_files():
        dir = os.path.dirname(fp)
        pkgs[dir] = ""

    logging.info("starting server version '5316caa-99cc386' on port: 8080")
    uvicorn.run("__main__:app", host="0.0.0.0", port=8080, log_level="info", workers=1, reload=True, reload_dirs=pkgs.keys())
        
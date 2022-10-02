
import json
import logging
from typing import Any, Dict
from dataclasses import dataclass
from pathlib import Path
import os
import shutil

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

from classifier import ConvMultiClassImageClassifier
from classifier import *
from arc.data.shapes.image import ImageData
from arc.data.shapes.classes import ClassData

logging.basicConfig(level=logging.INFO)

parser = ArgumentParser()
parser.add_arguments(ConvMultiClassImageClassifier.opts(), dest="convmulticlassimageclassifier")

args = parser.parse_args()

model_file = Path("./model.pkl")
cfg_file = Path("./config.json")

scm = SCM()

if model_file.is_file():
    model: ConvMultiClassImageClassifier = ConvMultiClassImageClassifier.load()
elif cfg_file.is_file():
    model = ConvMultiClassImageClassifier.load_json("./config.json")
else:
    model = ConvMultiClassImageClassifier.from_opts(args.convmulticlassimageclassifier)

uri = os.getenv("MODEL_URI")
model.uri = uri


app = Starlette(debug=True)

schemas = SchemaGenerator(
    {"openapi": "3.0.0", "info": {"title": "ConvMultiClassImageClassifier", "version": "6911508-3c5b933"}}
)


@app.route("/health")
def health(request):
    return JSONResponse({"status": "alive"})


@app.route("/info")
def info(request):
    # model_dict = model.opts().to_dict()
    return JSONResponse({"name": model.__class__.__name__, "version": scm.sha(), "env-sha": scm.env_sha(), "phase": model.phase().value})


@app.route("/compile", methods=["POST"])
async def compile(request):
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


@app.route("/save", methods=["POST"])
def save(request):
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
def load(request):
    # TODO: configurable
    path = "./model.pkl"
    model = ConvMultiClassImageClassifier.load(path)
    return JSONResponse({"message": "model loaded"})


@app.route("/fit", methods=["POST"])
async def fit(request):
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

    logging.info("starting server version '6911508-3c5b933' on port: 8080")
    uvicorn.run("__main__:app", host="0.0.0.0", port=8080, log_level="debug", workers=1, reload=True, reload_dirs=pkgs.keys())
        
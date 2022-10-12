
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

from trainer import Trainer
from trainer import *
from arc.data.shapes.image import ImageData
from arc.data.shapes.classes import ClassData

logging.basicConfig(level=logging.INFO)

scm = SCM()

app = Starlette(debug=True)

schemas = SchemaGenerator(
    {"openapi": "3.0.0", "info": {"title": "Trainer", "version": "5316caa-787d83f"}}
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
    # model_dict = model.opts().to_dict()
    return JSONResponse({"version": scm.sha(), "env-sha": scm.env_sha()})


@app.route('/train', methods=["POST"])
async def train(request):
    update_ts()
    jdict = await request.json()
    trainer = Trainer[ImageData, ClassData]()
    res = trainer.train(**jdict)

    ret = {}
    for model_uri, report in res.items():
        ret[model_uri] = report.repr_json()

    return JSONResponse(ret)


@app.route("/schema")
def openapi_schema(request):
    return schemas.OpenAPIResponse(request=request)


if __name__ == "__main__":
    pkgs: Dict[str, str] = {}
    for fp in scm.all_files():
        dir = os.path.dirname(fp)
        pkgs[dir] = ""

    logging.info("starting server version '5316caa-787d83f' on port: 8080")
    uvicorn.run("__main__:app", host="0.0.0.0", port=8080, log_level="debug", workers=1, reload=True, reload_dirs=pkgs.keys())
        

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

from job_test import ClassifyDigitsJob
from job_test import *
from arc.data.shapes.image import ImageData
from arc.data.shapes.classes import ClassData

logging.basicConfig(level=logging.INFO)

parser = ArgumentParser()
parser.add_arguments(ClassifyDigitsJob.opts(), dest="classifydigitsjob")

args = parser.parse_args()

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
    {"openapi": "3.0.0", "info": {"title": "ClassifyDigitsJob", "version": "6911508-b19d1ea"}}
)

@app.route("/health")
def health(request):
    return JSONResponse({"status": "alive"})

@app.route("/info")
def info(request):
    return JSONResponse({"version": scm.sha()})


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
    leaders = job.leaderboard()
    ret = []
    for leader in leaders:
        ret.append(leader.repr_json())
    return JSONResponse({"leaderboard": ret})


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
    params = request.query_params
    batch_size = params.get("batch_size", DEFAULT_BATCH_SIZE)

    x, y = job.sample(int(batch_size))
    resp = {"x": x.repr_json(), "y": y.repr_json()}
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
            model = SupervisedModelClient[ImageData, ClassData](model_uri)
        else:
            model = SupervisedModelClient[ImageData, ClassData](model_uri, **opts)

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

    logging.info("starting server version '6911508-b19d1ea' on port: 8080")
    uvicorn.run("__main__:app", host="0.0.0.0", port=8080, log_level="debug", workers=1, reload=True, reload_dirs=pkgs.keys())
        
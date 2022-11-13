from typing import List

from simple_parsing import ArgumentParser
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.schemas import SchemaGenerator
from starlette.routing import Route, WebSocketRoute, BaseRoute
import uvicorn

from .resource_test import *
from .resource_test import Foo


class FooServer(Foo):
    async def _copy_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.copy(**jdict)
        if hasattr(ret, "__dict__"):
            ret = ret.__dict__
        return JSONResponse(ret)

    async def _delete_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.delete(**jdict)
        ret = {"response": None}
        return JSONResponse(ret)

    async def _deploy_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.deploy(**jdict)
        ret = ret.to_dict()
        return JSONResponse(ret)

    async def _develop_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.develop(**jdict)
        ret = ret.to_dict()
        return JSONResponse(ret)

    async def _diff_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.diff(**jdict)
        ret = {"response": ret}
        return JSONResponse(ret)

    async def _health_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.health(**jdict)

        return JSONResponse(ret)

    async def _info_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.info(**jdict)

        return JSONResponse(ret)

    async def _lock_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.lock(**jdict)
        ret = {"response": None}
        return JSONResponse(ret)

    async def _logs_req(self, websocket):
        await websocket.accept()
        self._check_lock(websocket.headers)

        # Process incoming messages
        jdict = websocket.query_params

        for ret in self.logs(**jdict):
            ret = {"response": ret}
            print("seding json")
            await websocket.send_json(ret)
            print("sent")

        print("sending end")
        await websocket.send_json({"end": True})
        print("all done sending data, closing socket")
        await websocket.close()

    async def _merge_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.merge(**jdict)
        if hasattr(ret, "__dict__"):
            ret = ret.__dict__
        return JSONResponse(ret)

    async def _notebook_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.notebook(**jdict)
        ret = {"response": None}
        return JSONResponse(ret)

    async def _save_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.save(**jdict)
        ret = {"response": None}
        return JSONResponse(ret)

    async def _source_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.source(**jdict)
        ret = {"response": ret}
        return JSONResponse(ret)

    async def _store_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.store(**jdict)
        ret = {"response": ret}
        return JSONResponse(ret)

    async def _sync_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.sync(**jdict)
        ret = {"response": None}
        return JSONResponse(ret)

    async def _test_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.test(**jdict)
        ret = {"response": None}
        return JSONResponse(ret)

    async def _to_dict_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.to_dict(**jdict)

        return JSONResponse(ret)

    async def _to_json_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.to_json(**jdict)
        ret = {"response": ret}
        return JSONResponse(ret)

    async def _to_yaml_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.to_yaml(**jdict)
        ret = {"response": ret}
        return JSONResponse(ret)

    async def _unlock_req(self, request):
        jdict = await request.json()
        self._check_lock(request.headers)

        ret = self.unlock(**jdict)
        ret = {"response": None}
        return JSONResponse(ret)

    def _routes(self) -> List[BaseRoute]:
        return [
            Route("/copy", endpoint=self._copy_req),
            Route("/delete", endpoint=self._delete_req),
            Route("/deploy", endpoint=self._deploy_req),
            Route("/develop", endpoint=self._develop_req),
            Route("/diff", endpoint=self._diff_req),
            Route("/health", endpoint=self._health_req),
            Route("/info", endpoint=self._info_req),
            Route("/lock", endpoint=self._lock_req),
            WebSocketRoute("/logs", endpoint=self._logs_req),
            Route("/merge", endpoint=self._merge_req),
            Route("/notebook", endpoint=self._notebook_req),
            Route("/save", endpoint=self._save_req),
            Route("/source", endpoint=self._source_req),
            Route("/store", endpoint=self._store_req),
            Route("/sync", endpoint=self._sync_req),
            Route("/test", endpoint=self._test_req),
            Route("/to_dict", endpoint=self._to_dict_req),
            Route("/to_json", endpoint=self._to_json_req),
            Route("/to_yaml", endpoint=self._to_yaml_req),
            Route("/unlock", endpoint=self._unlock_req),
        ]


if __name__ == "__main__":
    pass

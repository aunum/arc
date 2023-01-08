from typing import List
import logging
import os
import json
import urllib

# from simple_parsing import ArgumentParser
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.schemas import SchemaGenerator
from starlette.routing import Route, WebSocketRoute, BaseRoute
import uvicorn
from arc.core.resource import is_annotation_match  # noqa

from resource_test import *
from resource_test import LotsOfUnions
import typing
import resource_test
import arc.kind
import arc.config

log_level = os.getenv("LOG_LEVEL")
if log_level is None:
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=log_level)


class LotsOfUnionsServer(LotsOfUnions):
    async def _diff_req(self, request):
        """Request for function:
        diff(self, uri: str) -> str
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.diff(**_jdict)

        print("called function: ", _ret)
        _ret = {"response": _ret}

        return JSONResponse(_ret)

    async def _echo_req(self, request):
        """Request for function:
        echo(self, txt: Optional[str] = None) -> str
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        if "txt" in _jdict:

            if _jdict["txt"] is None:
                pass
            elif type(_jdict["txt"]) == str:
                pass
            else:
                raise ValueError(
                    f"Argument could not be deserialized: txt - type: {type(_jdict['key'])}"
                )

        print("calling function: ", _jdict)
        _ret = self.echo(**_jdict)

        print("called function: ", _ret)
        _ret = {"response": _ret}

        return JSONResponse(_ret)

    async def _health_req(self, request):
        """Request for function:
        health(self) -> Dict[str, Any]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")

        print("calling function: ", _jdict)
        _ret = self.health(**_jdict)

        print("called function: ", _ret)

        return JSONResponse(_ret)

    async def _info_req(self, request):
        """Request for function:
        info(self) -> Dict[str, Any]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")

        print("calling function: ", _jdict)
        _ret = self.info(**_jdict)

        print("called function: ", _ret)

        return JSONResponse(_ret)

    async def _lock_req(self, request):
        """Request for function:
        lock(self, key: Optional[str] = None, timeout: Optional[int] = None) -> None
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")

        if "key" in _jdict:

            if _jdict["key"] is None:
                pass
            elif type(_jdict["key"]) == str:
                pass
            else:
                raise ValueError(
                    f"Argument could not be deserialized: key - type: {type(_jdict['key'])}"
                )

        if "timeout" in _jdict:

            if _jdict["timeout"] is None:
                pass
            elif type(_jdict["timeout"]) == int:
                pass
            else:
                raise ValueError(
                    f"Argument could not be deserialized: timeout - type: {type(_jdict['key'])}"
                )

        print("calling function: ", _jdict)
        _ret = self.lock(**_jdict)

        print("called function: ", _ret)
        _ret = {"response": None}

        return JSONResponse(_ret)

    async def _logs_req(self, websocket):
        """Request for function:
        logs(self) -> Iterable[str]
        """

        await websocket.accept()
        headers = websocket.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        # Process incoming messages
        qs = urllib.parse.parse_qs(str(websocket.query_params))

        _jdict = {}
        if "data" in qs and len(qs["data"]) > 0:
            _jdict = json.loads(qs["data"][0])

        print("jdict: ", _jdict)
        for _ret in self.logs(**_jdict):
            _ret = {"response": _ret}

            print("seding json")
            await websocket.send_json(_ret)
            print("sent")

        print("all done sending data, closing socket")
        await websocket.close()

    async def _merge_req(self, request):
        """Request for function:
        merge(self, uri: str) -> ~R
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.merge(**_jdict)

        print("called function: ", _ret)
        _ret = _ret.to_dict()

        return JSONResponse(_ret)

    async def _notebook_req(self, request):
        """Request for function:
        notebook(self) -> None
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.notebook(**_jdict)

        print("called function: ", _ret)
        _ret = {"response": None}

        return JSONResponse(_ret)

    async def _optional_lists_req(self, request):
        """Request for function:
        optional_lists(self, y: Union[List[__main__.Ham], Dict[str, __main__.Ham]], as_dict: bool = True) -> Union[List[__main__.Ham], Dict[str, __main__.Ham]]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        if json_is_type_match(typing.List[resource_test.Ham], _jdict["y"]):
            print("checking type match match for typing.List")

            _obj = object.__new__(typing.List)
            for _k, _v in _jdict["y"].items():
                setattr(_obj, _k, _v)
            _jdict["y"] = _obj

        elif json_is_type_match(typing.Dict[str, resource_test.Ham], _jdict["y"]):
            print("checking type match match for typing.Dict")
        else:
            raise ValueError(
                f"Argument could not be deserialized: y - type: {type(_jdict['key'])}"
            )

        print("calling function: ", _jdict)
        _ret = self.optional_lists(**_jdict)

        print("called function: ", _ret)
        if isinstance(_ret, list) or isinstance(_ret, dict):
            pass
        elif isinstance(_ret, list) or isinstance(_ret, dict):
            pass
        else:
            raise ValueError(
                f'Argument could not be deserialized: typing.Union[typing.List[__main__.Ham], typing.Dict[str, __main__.Ham]] -- type: {type(_ret)}"'
            )

        return JSONResponse(_ret)

    async def _optional_obj_req(self, request):
        """Request for function:
        optional_obj(self, h: Union[__main__.Ham, Dict[str, Any]], return_dict: Optional[bool] = None) -> Union[__main__.Ham, Dict[str, Any]]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        if is_annotation_match(resource_test.Ham.__annotations__, _jdict["h"]):
            print("checking annotation match for resource_test.Ham")

            _obj = object.__new__(resource_test.Ham)
            for _k, _v in _jdict["h"].items():
                setattr(_obj, _k, _v)
            _jdict["h"] = _obj

        elif json_is_type_match(typing.Dict[str, typing.Any], _jdict["h"]):
            print("checking type match match for typing.Dict")
        else:
            raise ValueError(
                f"Argument could not be deserialized: h - type: {type(_jdict['key'])}"
            )

        if "return_dict" in _jdict:

            if _jdict["return_dict"] is None:
                pass
            elif type(_jdict["return_dict"]) == bool:
                pass
            else:
                raise ValueError(
                    f"Argument could not be deserialized: return_dict - type: {type(_jdict['key'])}"
                )

        print("calling function: ", _jdict)
        _ret = self.optional_obj(**_jdict)

        print("called function: ", _ret)
        if isinstance(_ret, resource_test.Ham):
            _ret = _ret.__dict__
        elif isinstance(_ret, list) or isinstance(_ret, dict):
            pass
        else:
            raise ValueError(
                f'Argument could not be deserialized: typing.Union[__main__.Ham, typing.Dict[str, typing.Any]] -- type: {type(_ret)}"'
            )

        return JSONResponse(_ret)

    async def _returns_optional_req(self, request):
        """Request for function:
        returns_optional(self, a: Union[str, int]) -> Optional[str]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        if type(_jdict["a"]) == str:
            pass
        elif type(_jdict["a"]) == int:
            pass
        else:
            raise ValueError(
                f"Argument could not be deserialized: a - type: {type(_jdict['key'])}"
            )

        print("calling function: ", _jdict)
        _ret = self.returns_optional(**_jdict)

        print("called function: ", _ret)
        if isinstance(_ret, str):
            _ret = {"response": _ret}
        elif _ret is None:
            _ret = {"response": None}
        else:
            raise ValueError(
                f'Argument could not be deserialized: typing.Optional[str] -- type: {type(_ret)}"'
            )

        return JSONResponse(_ret)

    async def _save_req(self, request):
        """Request for function:
        save(self, out_dir: str = './artifacts') -> None
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.save(**_jdict)

        print("called function: ", _ret)
        _ret = {"response": None}

        return JSONResponse(_ret)

    async def _source_req(self, request):
        """Request for function:
        source(self) -> str
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.source(**_jdict)

        print("called function: ", _ret)
        _ret = {"response": _ret}

        return JSONResponse(_ret)

    async def _sync_req(self, request):
        """Request for function:
        sync(self) -> None
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.sync(**_jdict)

        print("called function: ", _ret)
        _ret = {"response": None}

        return JSONResponse(_ret)

    async def _unlock_req(self, request):
        """Request for function:
        unlock(self, key: Optional[str] = None, force: bool = False) -> None
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")

        if "key" in _jdict:

            if _jdict["key"] is None:
                pass
            elif type(_jdict["key"]) == str:
                pass
            else:
                raise ValueError(
                    f"Argument could not be deserialized: key - type: {type(_jdict['key'])}"
                )

        print("calling function: ", _jdict)
        _ret = self.unlock(**_jdict)

        print("called function: ", _ret)
        _ret = {"response": None}

        return JSONResponse(_ret)

    async def _base_names_req(self, request):
        """Request for function:
        base_names() -> List[str]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.base_names(**_jdict)

        print("called function: ", _ret)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    async def _clean_artifacts_req(self, request):
        """Request for function:
        clean_artifacts(dir: str = './artifacts') -> None
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.clean_artifacts(**_jdict)

        print("called function: ", _ret)
        _ret = {"response": None}

        return JSONResponse(_ret)

    async def _find_req(self, request):
        """Request for function:
        find(locator: arc.kind.ObjectLocator) -> List[str]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        _obj = object.__new__(arc.kind.ObjectLocator)
        for _k, _v in _jdict["locator"].items():
            setattr(_obj, _k, _v)
        _jdict["locator"] = _obj

        print("calling function: ", _jdict)
        _ret = self.find(**_jdict)

        print("called function: ", _ret)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    async def _from_env_req(self, request):
        """Request for function:
        from_env() -> ~R
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.from_env(**_jdict)

        print("called function: ", _ret)
        _ret = _ret.to_dict()

        return JSONResponse(_ret)

    async def _labels_req(self, request):
        """Request for function:
        labels() -> Dict[str, Any]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.labels(**_jdict)

        print("called function: ", _ret)

        return JSONResponse(_ret)

    async def _load_req(self, request):
        """Request for function:
        load(dir: str = './artifacts') -> ~R
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.load(**_jdict)

        print("called function: ", _ret)
        _ret = _ret.to_dict()

        return JSONResponse(_ret)

    async def _name_req(self, request):
        """Request for function:
        name() -> str
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.name(**_jdict)

        print("called function: ", _ret)
        _ret = {"response": _ret}

        return JSONResponse(_ret)

    async def _opts_schema_req(self, request):
        """Request for function:
        opts_schema() -> Dict[str, Any]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.opts_schema(**_jdict)

        print("called function: ", _ret)

        return JSONResponse(_ret)

    async def _schema_req(self, request):
        """Request for function:
        schema() -> str
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.schema(**_jdict)

        print("called function: ", _ret)
        _ret = {"response": _ret}

        return JSONResponse(_ret)

    async def _short_name_req(self, request):
        """Request for function:
        short_name() -> str
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        print("calling function: ", _jdict)
        _ret = self.short_name(**_jdict)

        print("called function: ", _ret)
        _ret = {"response": _ret}

        return JSONResponse(_ret)

    async def _store_cls_req(self, request):
        """Request for function:
        store_cls(clean: bool = True, dev_dependencies: bool = False, sync_strategy: arc.config.RemoteSyncStrategy = <RemoteSyncStrategy.IMAGE: 'image'>) -> str
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        if "sync_strategy" in _jdict:
            _jdict["sync_strategy"] = arc.config.RemoteSyncStrategy(
                _jdict["sync_strategy"]
            )

        print("calling function: ", _jdict)
        _ret = self.store_cls(**_jdict)

        print("called function: ", _ret)
        _ret = {"response": _ret}

        return JSONResponse(_ret)

    async def _versions_req(self, request):
        """Request for function:
        versions(repositories: Optional[List[str]] = None, cfg: Optional[arc.config.Config] = None) -> List[str]
        """

        body = await request.body()
        print("len body: ", len(body))
        print("body: ", body)

        _jdict = {}
        if len(body) != 0:
            _jdict = json.loads(body)

        headers = request.headers
        logging.debug(f"headers: {headers}")
        self._check_lock(headers)

        if "repositories" in _jdict:

            if _jdict["repositories"] is None:
                pass
            elif json_is_type_match(typing.List[str], _jdict["repositories"]):
                print("checking type match match for typing.List")

                _obj = object.__new__(typing.List)
                for _k, _v in _jdict["repositories"].items():
                    setattr(_obj, _k, _v)
                _jdict["repositories"] = _obj

            else:
                raise ValueError(
                    f"Argument could not be deserialized: repositories - type: {type(_jdict['key'])}"
                )

        if "cfg" in _jdict:

            if _jdict["cfg"] is None:
                pass
            elif is_annotation_match(arc.config.Config.__annotations__, _jdict["cfg"]):
                print("checking annotation match for arc.config.Config")

                _obj = object.__new__(arc.config.Config)
                for _k, _v in _jdict["cfg"].items():
                    setattr(_obj, _k, _v)
                _jdict["cfg"] = _obj

            else:
                raise ValueError(
                    f"Argument could not be deserialized: cfg - type: {type(_jdict['key'])}"
                )

        print("calling function: ", _jdict)
        _ret = self.versions(**_jdict)

        print("called function: ", _ret)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    def _routes(self) -> List[BaseRoute]:
        return [
            Route("/diff", endpoint=self._diff_req, methods=["POST"]),
            Route("/echo", endpoint=self._echo_req, methods=["POST"]),
            Route("/health", endpoint=self._health_req, methods=["GET", "POST"]),
            Route("/info", endpoint=self._info_req, methods=["POST"]),
            Route("/lock", endpoint=self._lock_req, methods=["POST"]),
            WebSocketRoute("/logs", endpoint=self._logs_req),
            Route("/merge", endpoint=self._merge_req, methods=["POST"]),
            Route("/notebook", endpoint=self._notebook_req, methods=["POST"]),
            Route(
                "/optional_lists", endpoint=self._optional_lists_req, methods=["POST"]
            ),
            Route("/optional_obj", endpoint=self._optional_obj_req, methods=["POST"]),
            Route(
                "/returns_optional",
                endpoint=self._returns_optional_req,
                methods=["POST"],
            ),
            Route("/save", endpoint=self._save_req, methods=["POST"]),
            Route("/source", endpoint=self._source_req, methods=["POST"]),
            Route("/sync", endpoint=self._sync_req, methods=["POST"]),
            Route("/unlock", endpoint=self._unlock_req, methods=["POST"]),
            Route("/base_names", endpoint=self._base_names_req, methods=["POST"]),
            Route(
                "/clean_artifacts", endpoint=self._clean_artifacts_req, methods=["POST"]
            ),
            Route("/find", endpoint=self._find_req, methods=["POST"]),
            Route("/from_env", endpoint=self._from_env_req, methods=["POST"]),
            Route("/labels", endpoint=self._labels_req, methods=["POST"]),
            Route("/load", endpoint=self._load_req, methods=["POST"]),
            Route("/name", endpoint=self._name_req, methods=["POST"]),
            Route("/opts_schema", endpoint=self._opts_schema_req, methods=["POST"]),
            Route("/schema", endpoint=self._schema_req, methods=["POST"]),
            Route("/short_name", endpoint=self._short_name_req, methods=["POST"]),
            Route("/store_cls", endpoint=self._store_cls_req, methods=["POST"]),
            Route("/versions", endpoint=self._versions_req, methods=["POST"]),
        ]


o = LotsOfUnionsServer.from_env()
pkgs = o._reload_dirs()

app = Starlette(routes=o._routes())

# self.schemas = SchemaGenerator(
#     {"openapi": "3.0.0", "info": {"title": LotsOfUnions, "version": o.scm.sha()}}
# )

if __name__ == "__main__":
    logging.info(f"starting server version '{o.scm.sha()}' on port: 8080")
    uvicorn.run(
        "__main__:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        workers=1,
        reload=True,
        reload_dirs=pkgs.keys(),
    )

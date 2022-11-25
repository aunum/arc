
from typing import List
import logging

# from simple_parsing import ArgumentParser
# from starlette.applications import Starlette
from starlette.responses import JSONResponse
# from starlette.schemas import SchemaGenerator
from starlette.routing import Route, WebSocketRoute, BaseRoute
# import uvicorn

from .resource_test import *
from .resource_test import Foo
import arc.scm
import arc.config
import dataclasses_jsonschema.type_defs
import arc.kind
import typing

class FooServer(Foo):

    async def _copy_req(self, request):
        """Request for function: 
        copy(self) -> arc.kind.PID
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.copy(**_jdict)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    async def _delete_req(self, request):
        """Request for function: 
        delete(self) -> None
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.delete(**_jdict)
        _ret = {'response': None}

        return JSONResponse(_ret)

    async def _deploy_req(self, request):
        """Request for function: 
        deploy(self: arc.core.resource.Resource, scm: Optional[arc.scm.SCM] = None, clean: bool = True, dev_dependencies: bool = False, sync_strategy: arc.config.RemoteSyncStrategy = <RemoteSyncStrategy.IMAGE: 'image'>, **kwargs) -> arc.core.resource.Resource
        """

        _jdict = await request.json()
        self._check_lock(request.headers)

        if 'scm' in _jdict:

            if type(_jdict['scm']) == None:
                pass
            elif self._is_annotation_match(arc.scm.SCM.__annotations__, _jdict['scm']):

                _obj = object.__new__(arc.scm.SCM)
                for _k, _v in _jdict['scm'].items():
                    setattr(_obj, _k, _v)
                _jdict['scm'] = _obj

            else:
                raise ValueError('Argument could not be deserialized: scm')

        if 'sync_strategy' in _jdict:

            _obj = object.__new__(arc.config.RemoteSyncStrategy)
            for _k, _v in _jdict['sync_strategy'].items():
                setattr(_obj, _k, _v)
            _jdict['sync_strategy'] = _obj


        _ret = self.deploy(**_jdict)
        _ret = _ret.to_dict()

        return JSONResponse(_ret)

    async def _develop_req(self, request):
        """Request for function: 
        develop(self: arc.core.resource.Resource, clean: bool = True, dev_dependencies: bool = False, reuse: bool = True, **kwargs) -> arc.core.resource.Resource
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.develop(**_jdict)
        _ret = _ret.to_dict()

        return JSONResponse(_ret)

    async def _diff_req(self, request):
        """Request for function: 
        diff(self, uri: str) -> str
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.diff(**_jdict)
        _ret = {'response': _ret}

        return JSONResponse(_ret)

    async def _health_req(self, request):
        """Request for function: 
        health(self) -> Dict[str, Any]
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.health(**_jdict)

        return JSONResponse(_ret)

    async def _info_req(self, request):
        """Request for function: 
        info(self) -> Dict[str, Any]
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.info(**_jdict)

        return JSONResponse(_ret)

    async def _lock_req(self, request):
        """Request for function: 
        lock(self, key: Optional[str] = None, timeout: Optional[int] = None) -> None
        """

        _jdict = await request.json()
        self._check_lock(request.headers)

        if 'key' in _jdict:

            if type(_jdict['key']) == None:
                pass
            elif type(_jdict['key']) == str:
                pass
            else:
                raise ValueError('Argument could not be deserialized: key')

        if 'timeout' in _jdict:

            if type(_jdict['timeout']) == None:
                pass
            elif type(_jdict['timeout']) == int:
                pass
            else:
                raise ValueError('Argument could not be deserialized: timeout')


        _ret = self.lock(**_jdict)
        _ret = {'response': None}

        return JSONResponse(_ret)

    async def _logs_req(self, websocket):
        """Request for function:
        logs(self) -> Iterable[str]
        """

        await websocket.accept()
        self._check_lock(websocket.headers)

        # Process incoming messages
        _jdict = websocket.query_params

        for _ret in self.logs(**_jdict):
            _ret = {'response': _ret}

            print("seding json")
            await websocket.send_json(_ret)
            print("sent")

        print("sending end")
        await websocket.send_json({"end": True})
        print("all done sending data, closing socket")
        await websocket.close()
                
    async def _merge_req(self, request):
        """Request for function: 
        merge(self, uri: str) -> ~R
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.merge(**_jdict)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    async def _notebook_req(self, request):
        """Request for function: 
        notebook(self) -> None
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.notebook(**_jdict)
        _ret = {'response': None}

        return JSONResponse(_ret)

    async def _save_req(self, request):
        """Request for function: 
        save(self, out_dir: str = './artifacts') -> None
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.save(**_jdict)
        _ret = {'response': None}

        return JSONResponse(_ret)

    async def _source_req(self, request):
        """Request for function: 
        source(self) -> str
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.source(**_jdict)
        _ret = {'response': _ret}

        return JSONResponse(_ret)

    async def _store_req(self, request):
        """Request for function: 
        store(self, dev_dependencies: bool = False, clean: bool = True) -> str
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.store(**_jdict)
        _ret = {'response': _ret}

        return JSONResponse(_ret)

    async def _sync_req(self, request):
        """Request for function: 
        sync(self) -> None
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.sync(**_jdict)
        _ret = {'response': None}

        return JSONResponse(_ret)

    async def _test_req(self, request):
        """Request for function: 
        test(self) -> None
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.test(**_jdict)
        _ret = {'response': None}

        return JSONResponse(_ret)

    async def _to_dict_req(self, request):
        """Request for function: 
        to_dict(self, omit_none: bool = True, validate: bool = False, validate_enums: bool = True, schema_type: dataclasses_jsonschema.type_defs.SchemaType = <SchemaType.DRAFT_06: 'Draft6'>) -> Dict[str, Any]
        """

        _jdict = await request.json()
        self._check_lock(request.headers)

        if 'schema_type' in _jdict:

            _obj = object.__new__(dataclasses_jsonschema.type_defs.SchemaType)
            for _k, _v in _jdict['schema_type'].items():
                setattr(_obj, _k, _v)
            _jdict['schema_type'] = _obj


        _ret = self.to_dict(**_jdict)

        return JSONResponse(_ret)

    async def _to_json_req(self, request):
        """Request for function: 
        to_json(self, omit_none: bool = True, validate: bool = False, **json_kwargs) -> str
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.to_json(**_jdict)
        _ret = {'response': _ret}

        return JSONResponse(_ret)

    async def _to_yaml_req(self, request):
        """Request for function: 
        to_yaml(self, omit_none: bool = True, validate: bool = False, **yaml_kwargs) -> str
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.to_yaml(**_jdict)
        _ret = {'response': _ret}

        return JSONResponse(_ret)

    async def _unlock_req(self, request):
        """Request for function: 
        unlock(self, key: Optional[str] = None, force: bool = False) -> None
        """

        _jdict = await request.json()
        self._check_lock(request.headers)

        if 'key' in _jdict:

            if type(_jdict['key']) == None:
                pass
            elif type(_jdict['key']) == str:
                pass
            else:
                raise ValueError('Argument could not be deserialized: key')


        _ret = self.unlock(**_jdict)
        _ret = {'response': None}

        return JSONResponse(_ret)

    async def _all_json_schemas_req(self, request):
        """Request for function: 
        all_json_schemas(schema_type: dataclasses_jsonschema.type_defs.SchemaType = <SchemaType.DRAFT_06: 'Draft6'>, validate_enums: bool = True) -> Dict[str, Any]
        """

        _jdict = await request.json()
        self._check_lock(request.headers)

        if 'schema_type' in _jdict:

            _obj = object.__new__(dataclasses_jsonschema.type_defs.SchemaType)
            for _k, _v in _jdict['schema_type'].items():
                setattr(_obj, _k, _v)
            _jdict['schema_type'] = _obj


        _ret = self.all_json_schemas(**_jdict)

        return JSONResponse(_ret)

    async def _base_names_req(self, request):
        """Request for function: 
        base_names() -> List[str]
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.base_names(**_jdict)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    async def _clean_artifacts_req(self, request):
        """Request for function: 
        clean_artifacts(dir: str = './artifacts') -> None
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.clean_artifacts(**_jdict)
        _ret = {'response': None}

        return JSONResponse(_ret)

    async def _field_mapping_req(self, request):
        """Request for function: 
        field_mapping() -> Dict[str, str]
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.field_mapping(**_jdict)

        return JSONResponse(_ret)

    async def _find_req(self, request):
        """Request for function: 
        find(locator: arc.kind.ObjectLocator) -> List[str]
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _obj = object.__new__(arc.kind.ObjectLocator)
        for _k, _v in _jdict['locator'].items():
            setattr(_obj, _k, _v)
        _jdict['locator'] = _obj


        _ret = self.find(**_jdict)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    async def _from_dict_req(self, request):
        """Request for function: 
        from_dict(data: Dict[str, Any], validate: bool = True, validate_enums: bool = True, schema_type: dataclasses_jsonschema.type_defs.SchemaType = <SchemaType.DRAFT_06: 'Draft6'>) -> ~T
        """

        _jdict = await request.json()
        self._check_lock(request.headers)

        if 'schema_type' in _jdict:

            _obj = object.__new__(dataclasses_jsonschema.type_defs.SchemaType)
            for _k, _v in _jdict['schema_type'].items():
                setattr(_obj, _k, _v)
            _jdict['schema_type'] = _obj


        _ret = self.from_dict(**_jdict)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    async def _from_env_req(self, request):
        """Request for function: 
        from_env() -> ~R
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.from_env(**_jdict)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    async def _from_json_req(self, request):
        """Request for function: 
        from_json(data: Union[str, bytes], validate: bool = True, **json_kwargs) -> ~T
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        if type(_jdict['data']) == str:
            pass
        elif type(_jdict['data']) == bytes:
            pass
        else:
            raise ValueError('Argument could not be deserialized: data')


        _ret = self.from_json(**_jdict)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    async def _from_object_req(self, request):
        """Request for function: 
        from_object(obj: Any, exclude: Tuple[Union[str, Tuple[str, ForwardRef('FieldExcludeList')]], ...] = ()) -> ~T
        """

        _jdict = await request.json()
        self._check_lock(request.headers)

        if 'exclude' in _jdict:

            _obj = object.__new__(typing.Tuple)
            for _k, _v in _jdict['exclude'].items():
                setattr(_obj, _k, _v)
            _jdict['exclude'] = _obj


        _ret = self.from_object(**_jdict)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    async def _from_yaml_req(self, request):
        """Request for function: 
        from_yaml(data: Union[str, bytes], validate: bool = True, **yaml_kwargs) -> ~T
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        if type(_jdict['data']) == str:
            pass
        elif type(_jdict['data']) == bytes:
            pass
        else:
            raise ValueError('Argument could not be deserialized: data')


        _ret = self.from_yaml(**_jdict)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    async def _json_schema_req(self, request):
        """Request for function: 
        json_schema(embeddable: bool = False, schema_type: dataclasses_jsonschema.type_defs.SchemaType = <SchemaType.DRAFT_06: 'Draft6'>, validate_enums: bool = True, **kwargs) -> Dict[str, Any]
        """

        _jdict = await request.json()
        self._check_lock(request.headers)

        if 'schema_type' in _jdict:

            _obj = object.__new__(dataclasses_jsonschema.type_defs.SchemaType)
            for _k, _v in _jdict['schema_type'].items():
                setattr(_obj, _k, _v)
            _jdict['schema_type'] = _obj


        _ret = self.json_schema(**_jdict)

        return JSONResponse(_ret)

    async def _labels_req(self, request):
        """Request for function: 
        labels() -> Dict[str, Any]
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.labels(**_jdict)

        return JSONResponse(_ret)

    async def _load_req(self, request):
        """Request for function: 
        load(dir: str = './artifacts') -> ~R
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.load(**_jdict)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    async def _name_req(self, request):
        """Request for function: 
        name() -> str
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.name(**_jdict)
        _ret = {'response': _ret}

        return JSONResponse(_ret)

    async def _opts_schema_req(self, request):
        """Request for function: 
        opts_schema() -> Dict[str, Any]
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.opts_schema(**_jdict)

        return JSONResponse(_ret)

    async def _schema_req(self, request):
        """Request for function: 
        schema() -> str
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.schema(**_jdict)
        _ret = {'response': _ret}

        return JSONResponse(_ret)

    async def _short_name_req(self, request):
        """Request for function: 
        short_name() -> str
        """

        _jdict = await request.json()
        self._check_lock(request.headers)


        _ret = self.short_name(**_jdict)
        _ret = {'response': _ret}

        return JSONResponse(_ret)

    async def _store_cls_req(self, request):
        """Request for function: 
        store_cls(clean: bool = True, dev_dependencies: bool = False, sync_strategy: arc.config.RemoteSyncStrategy = <RemoteSyncStrategy.IMAGE: 'image'>) -> str
        """

        _jdict = await request.json()
        self._check_lock(request.headers)

        if 'sync_strategy' in _jdict:

            _obj = object.__new__(arc.config.RemoteSyncStrategy)
            for _k, _v in _jdict['sync_strategy'].items():
                setattr(_obj, _k, _v)
            _jdict['sync_strategy'] = _obj


        _ret = self.store_cls(**_jdict)
        _ret = {'response': _ret}

        return JSONResponse(_ret)

    async def _versions_req(self, request):
        """Request for function: 
        versions(repositories: Optional[List[str]] = None, cfg: Optional[arc.config.Config] = None) -> List[str]
        """

        _jdict = await request.json()
        self._check_lock(request.headers)

        if 'repositories' in _jdict:

            if type(_jdict['repositories']) == None:
                pass
            elif type(_jdict['repositories']) == typing.List:
                pass
            else:
                raise ValueError('Argument could not be deserialized: repositories')

        if 'cfg' in _jdict:

            if type(_jdict['cfg']) == None:
                pass
            elif self._is_annotation_match(arc.config.Config.__annotations__, _jdict['cfg']):

                _obj = object.__new__(arc.config.Config)
                for _k, _v in _jdict['cfg'].items():
                    setattr(_obj, _k, _v)
                _jdict['cfg'] = _obj

            else:
                raise ValueError('Argument could not be deserialized: cfg')


        _ret = self.versions(**_jdict)
        _ret = _ret.__dict__

        return JSONResponse(_ret)

    def _routes(self) -> List[BaseRoute]:
        return [Route('/copy', endpoint=self._copy_req), Route('/delete', endpoint=self._delete_req), Route('/deploy', endpoint=self._deploy_req), Route('/develop', endpoint=self._develop_req), Route('/diff', endpoint=self._diff_req), Route('/health', endpoint=self._health_req), Route('/info', endpoint=self._info_req), Route('/lock', endpoint=self._lock_req), WebSocketRoute('/logs', endpoint=self._logs_req), Route('/merge', endpoint=self._merge_req), Route('/notebook', endpoint=self._notebook_req), Route('/save', endpoint=self._save_req), Route('/source', endpoint=self._source_req), Route('/store', endpoint=self._store_req), Route('/sync', endpoint=self._sync_req), Route('/test', endpoint=self._test_req), Route('/to_dict', endpoint=self._to_dict_req), Route('/to_json', endpoint=self._to_json_req), Route('/to_yaml', endpoint=self._to_yaml_req), Route('/unlock', endpoint=self._unlock_req), Route('/all_json_schemas', endpoint=self._all_json_schemas_req), Route('/base_names', endpoint=self._base_names_req), Route('/clean_artifacts', endpoint=self._clean_artifacts_req), Route('/field_mapping', endpoint=self._field_mapping_req), Route('/find', endpoint=self._find_req), Route('/from_dict', endpoint=self._from_dict_req), Route('/from_env', endpoint=self._from_env_req), Route('/from_json', endpoint=self._from_json_req), Route('/from_object', endpoint=self._from_object_req), Route('/from_yaml', endpoint=self._from_yaml_req), Route('/json_schema', endpoint=self._json_schema_req), Route('/labels', endpoint=self._labels_req), Route('/load', endpoint=self._load_req), Route('/name', endpoint=self._name_req), Route('/opts_schema', endpoint=self._opts_schema_req), Route('/schema', endpoint=self._schema_req), Route('/short_name', endpoint=self._short_name_req), Route('/store_cls', endpoint=self._store_cls_req), Route('/versions', endpoint=self._versions_req)]


if __name__ == "__main__":
    o = FooServer.from_env()
    o.serve()
        
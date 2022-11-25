
from urllib import request, parse
import json
import logging

from arc.core.resource import Client
import arc.kind
import arc.core.resource
import typing
import arc.scm
import arc.config
import socket
from websocket import create_connection
import dataclasses_jsonschema.type_defs
import dataclasses_jsonschema
import simple_parsing.helpers.serialization.serializable
import dataclasses_jsonschema.field_types

class FooClient(Client):

    def copy(self) -> arc.kind.PID:
        """Copy the process

        Returns:
            PID: A process ID
        """

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/copy",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = object.__new__(arc.kind.PID)
        for k, v in _jdict.items():
            setattr(_ret, k, v)

        return _ret
            
    def delete(self) -> None:
        """Delete the resource"""

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/delete",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def deploy(self: arc.core.resource.Resource, scm: typing.Optional[arc.scm.SCM] = None, clean: bool = True, dev_dependencies: bool = False, sync_strategy: arc.config.RemoteSyncStrategy = 'image', **kwargs) -> arc.core.resource.Resource:
        """Create a deployment of the class, which will allow for the generation of instances remotely

        Args:
            scm (Optional[SCM], optional): SCM to use. Defaults to None.
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            sync_strategy (RemoteSyncStrategy, optional): Sync strategy to use. Defaults to RemoteSyncStrategy.IMAGE.

        Returns:
            Client: A client for the server
        """

        _params = json.dumps({'scm': scm.__dict__, 'clean': clean.__dict__, 'dev_dependencies': dev_dependencies.__dict__, 'sync_strategy': sync_strategy.__dict__, 'kwargs': kwargs.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/deploy",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = arc.core.resource.Resource.from_dict(_jdict)

        return _ret
            
    def develop(self: arc.core.resource.Resource, clean: bool = True, dev_dependencies: bool = False, reuse: bool = True, **kwargs) -> arc.core.resource.Resource:
        """Create a deployment of the class, and sync local code to it

        Args:
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            reuse (bool, optional): Whether to reuse existing running servers. Defaults to True.

        Returns:
            Client: A client for the server
        """

        _params = json.dumps({'clean': clean.__dict__, 'dev_dependencies': dev_dependencies.__dict__, 'reuse': reuse.__dict__, 'kwargs': kwargs.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/develop",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = arc.core.resource.Resource.from_dict(_jdict)

        return _ret
            
    def diff(self, uri: str) -> str:
        """Diff of the given object from the URI

        Args:
            uri (str): URI to diff

        Returns:
            str: A diff
        """

        _params = json.dumps({'uri': uri.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/diff",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def health(self) -> typing.Dict[str, typing.Any]:
        """Health of the resource

        Returns:
            Dict[str, Any]: Resource health
        """

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/health",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict

        return _ret
            
    def info(self) -> typing.Dict[str, typing.Any]:
        """Info about the resource

        Returns:
            Dict[str, Any]: Resource info
        """

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/info",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict

        return _ret
            
    def lock(self, key: typing.Optional[str] = None, timeout: typing.Optional[int] = None) -> None:
        """Lock the process to only operate with the caller

        Args:
            key (Optional[str], optional): An optional key to secure the lock
            timeout (Optional[int], optional): Whether to unlock after a set amount of time. Defaults to None.
        """

        _params = json.dumps({'key': key.__dict__, 'timeout': timeout.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/lock",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def logs(self) -> typing.Iterable[str]:
        """Logs for the resource

        Returns:
            Iterable[str]: A stream of logs
        """
        _server_addr = f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes:{self.server_port}"

        # you need to create your own socket here
        _sock = socket.create_connection((f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes", self.server_port))

        _encoded = parse.urlencode({})
        _ws = create_connection(
            f"ws://{_server_addr}/logs?{_encoded}",
            header=[f"client-uuid: {self.uid}"],
            socket=_sock,
        )
        try:
            while True:
                _, _data = _ws.recv_data()

                _jdict = json.loads(_data)
                _end = _jdict["end"]
                if _end:
                    break
                _ret = _jdict['response']

                yield _ret

        except Exception as e:
            print("stream exception: ", e)
            raise e

    def merge(self, uri: str) -> arc.core.resource.Resource:
        """Merge with the given resource

        Args:
            uri (str): Resource to merge with

        Returns:
            Resource: A Resource
        """

        _params = json.dumps({'uri': uri.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/merge",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = arc.core.resource.Resource.from_dict(_jdict)

        return _ret
            
    def notebook(self) -> None:
        """Launch a notebook for the object"""

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/notebook",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def save(self, out_dir: str = './artifacts') -> None:
        """Save the object

        Args:
            out_dir (str, optional): Directory to output the artiacts. Defaults to "./artifacts".
        """

        _params = json.dumps({'out_dir': out_dir.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/save",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def source(self) -> str:
        """Source code for the object"""

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/source",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def store(self, dev_dependencies: bool = False, clean: bool = True) -> str:
        """Create a server image with the saved artifact

        Args:
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            clean (bool, optional): Whether to clean the generated files. Defaults to True.

        Returns:
            str: URI for the image
        """

        _params = json.dumps({'dev_dependencies': dev_dependencies.__dict__, 'clean': clean.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/store",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def sync(self) -> None:
        """Sync changes to a remote process"""

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/sync",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def test(self) -> None:
        

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/test",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def to_dict(self, omit_none: bool = True, validate: bool = False, validate_enums: bool = True, schema_type: dataclasses_jsonschema.type_defs.SchemaType = dataclasses_jsonschema.type_defs.SchemaType.DRAFT_06) -> typing.Dict[str, typing.Any]:
        """Converts the dataclass instance to a JSON encodable dict, with optional JSON schema validation.

        If omit_none (default True) is specified, any items with value None are removed
        """

        _params = json.dumps({'omit_none': omit_none.__dict__, 'validate': validate.__dict__, 'validate_enums': validate_enums.__dict__, 'schema_type': schema_type.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/to_dict",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict

        return _ret
            
    def to_json(self, omit_none: bool = True, validate: bool = False, **json_kwargs) -> str:
        

        _params = json.dumps({'omit_none': omit_none.__dict__, 'validate': validate.__dict__, 'json_kwargs': json_kwargs.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/to_json",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def to_yaml(self, omit_none: bool = True, validate: bool = False, **yaml_kwargs) -> str:
        

        _params = json.dumps({'omit_none': omit_none.__dict__, 'validate': validate.__dict__, 'yaml_kwargs': yaml_kwargs.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/to_yaml",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def unlock(self, key: typing.Optional[str] = None, force: bool = False) -> None:
        """Unlock the kind

        Args:
            key (Optional[str], optional): Key to unlock, if needed. Defaults to None.
            force (bool, optional): Force unlock without a key. Defaults to False.
        """

        _params = json.dumps({'key': key.__dict__, 'force': force.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/unlock",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def all_json_schemas(self, schema_type: dataclasses_jsonschema.type_defs.SchemaType = dataclasses_jsonschema.type_defs.SchemaType.DRAFT_06, validate_enums: bool = True) -> typing.Dict[str, typing.Any]:
        """Returns JSON schemas for all subclasses"""

        _params = json.dumps({'schema_type': schema_type.__dict__, 'validate_enums': validate_enums.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/all_json_schemas",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict

        return _ret
            
    def base_names(self) -> typing.List[str]:
        """Bases for the resource

        Raises:
            SystemError: Server bases

        Returns:
            List[str]: Bases of the server
        """

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/base_names",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def clean_artifacts(self, dir: str = './artifacts') -> None:
        """Clean any created artifacts

        Args:
            dir (str, optional): Directory where artifacts exist. Defaults to "./artifacts".
        """

        _params = json.dumps({'dir': dir.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/clean_artifacts",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def field_mapping(self) -> typing.Dict[str, str]:
        """Defines the mapping of python field names to JSON field names.

        The main use-case is to allow JSON field names which are Python keywords
        """

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/field_mapping",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict

        return _ret
            
    def find(self, locator: arc.kind.ObjectLocator) -> typing.List[str]:
        """Find objects

        Args:
            locator (ObjectLocator): A locator of objects

        Returns:
            List[str]: A list of object uris
        """

        _params = json.dumps({'locator': locator.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/find",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def from_dict(self, data: typing.Dict[str, typing.Any], validate: bool = True, validate_enums: bool = True, schema_type: dataclasses_jsonschema.type_defs.SchemaType = dataclasses_jsonschema.type_defs.SchemaType.DRAFT_06) -> dataclasses_jsonschema.JsonSchemaMixin:
        """Returns a dataclass instance with all nested classes converted from the dict given"""

        _params = json.dumps({'data': data.__dict__, 'validate': validate.__dict__, 'validate_enums': validate_enums.__dict__, 'schema_type': schema_type.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/from_dict",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = dataclasses_jsonschema.JsonSchemaMixin.from_dict(_jdict)

        return _ret
            
    def from_env(self) -> arc.core.resource.Resource:
        """Create the server from the environment, it will look for a saved artifact,
        a config.json, or command line arguments

        Returns:
            Server: A server
        """

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/from_env",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = arc.core.resource.Resource.from_dict(_jdict)

        return _ret
            
    def from_json(self, data: typing.Union[str, bytes], validate: bool = True, **json_kwargs) -> dataclasses_jsonschema.JsonSchemaMixin:
        

        _params = json.dumps({'data': data.__dict__, 'validate': validate.__dict__, 'json_kwargs': json_kwargs.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/from_json",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = dataclasses_jsonschema.JsonSchemaMixin.from_dict(_jdict)

        return _ret
            
    def from_object(self, obj: typing.Any, exclude: typing.Tuple[typing.Union[str, typing.Tuple[str, dataclasses_jsonschema.FieldExcludeList]], ...] = ()) -> dataclasses_jsonschema.JsonSchemaMixin:
        """Returns a dataclass instance from another object (typically an ORM model).
        The `exclude` parameter is a tuple of field names or (field.name, nested_exclude)
        to exclude from the conversion. For example `exclude=('artist_name', ('albums', ('tracks',))` will exclude
        the `artist_name` and `tracks` from related albums
        """

        _params = json.dumps({'obj': obj, 'exclude': exclude.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/from_object",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = dataclasses_jsonschema.JsonSchemaMixin.from_dict(_jdict)

        return _ret
            
    def from_opts(self, opts: typing.Type[simple_parsing.helpers.serialization.serializable.Serializable]) -> arc.core.resource.Resource:
        """Load server from Opts

        Args:
            cls (Type[&quot;Server&quot;]): Server
            opts (Opts): Opts to load from

        Returns:
            Server: A server
        """

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/from_opts",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = arc.core.resource.Resource.from_dict(_jdict)

        return _ret
            
    def from_yaml(self, data: typing.Union[str, bytes], validate: bool = True, **yaml_kwargs) -> dataclasses_jsonschema.JsonSchemaMixin:
        

        _params = json.dumps({'data': data.__dict__, 'validate': validate.__dict__, 'yaml_kwargs': yaml_kwargs.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/from_yaml",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = dataclasses_jsonschema.JsonSchemaMixin.from_dict(_jdict)

        return _ret
            
    def json_schema(self, embeddable: bool = False, schema_type: dataclasses_jsonschema.type_defs.SchemaType = dataclasses_jsonschema.type_defs.SchemaType.DRAFT_06, validate_enums: bool = True, **kwargs) -> typing.Dict[str, typing.Any]:
        """Returns the JSON schema for the dataclass, along with the schema of any nested dataclasses
        within the 'definitions' field.

        Enable the embeddable flag to generate the schema in a format for embedding into other schemas
        or documents supporting JSON schema such as Swagger specs.

        If embedding the schema into a swagger api, specify 'swagger_version' to generate a spec compatible with that
        version.
        """

        _params = json.dumps({'embeddable': embeddable.__dict__, 'schema_type': schema_type.__dict__, 'validate_enums': validate_enums.__dict__, 'kwargs': kwargs.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/json_schema",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict

        return _ret
            
    def labels(self) -> typing.Dict[str, typing.Any]:
        """Labels for the resource

        Args:
            scm (Optional[SCM], optional): SCM to use. Defaults to None.

        Returns:
            Dict[str, Any]: Labels for the server
        """

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/labels",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict

        return _ret
            
    def load(self, dir: str = './artifacts') -> arc.core.resource.Resource:
        """Load the object

        Args:
            dir (str): Directory to the artifacts
        """

        _params = json.dumps({'dir': dir.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/load",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = arc.core.resource.Resource.from_dict(_jdict)

        return _ret
            
    def name(self) -> str:
        """Name of the resource

        Returns:
            str: Name of the server
        """

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/name",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def opts(self) -> typing.Optional[typing.Type[simple_parsing.helpers.serialization.serializable.Serializable]]:
        """Options for the server

        Returns:
            Optional[Type[Serializable]]: Options for the server
        """

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/opts",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _deserialized: bool = False
        if not _deserialized:
            try:
                _ret = object.__new__(typing.Optional)
                for k, v in _jdict.items():
                    setattr(_ret, k, v)
            except:  # noqa
                pass
        if not _deserialized:
            try:
                _ret = _jdict['response']
            except:  # noqa
                pass
        if not _deserialized:
            raise ValueError('unable to deserialize returned value')

        return _ret
            
    def opts_schema(self) -> typing.Dict[str, typing.Any]:
        """Schema for the server options

        Returns:
            Dict[str, Any]: JsonSchema for the server options
        """

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/opts_schema",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict

        return _ret
            
    def schema(self) -> str:
        """Schema of the object

        Returns:
            str: Object schema
        """

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/schema",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def short_name(self) -> str:
        """Short name for the resource

        Returns:
            str: A short name
        """

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/short_name",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def store_cls(self, clean: bool = True, dev_dependencies: bool = False, sync_strategy: arc.config.RemoteSyncStrategy = 'image') -> str:
        """Create an image from the server class that can be used to create servers from scratch

        Args:
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            sync_strategy (RemoteSyncStrategy, optional): Sync strategy to use. Defaults to RemoteSyncStrategy.IMAGE.

        Returns:
            str: URI for the image
        """

        _params = json.dumps({'clean': clean.__dict__, 'dev_dependencies': dev_dependencies.__dict__, 'sync_strategy': sync_strategy.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/store_cls",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
    def versions(self, repositories: typing.Optional[typing.List[str]] = None, cfg: typing.Optional[arc.config.Config] = None) -> typing.List[str]:
        """Find all versions of this type

        Args:
            cls (Type[Server]): the Server class
            repositories (List[str], optional): extra repositories to check
            cfg (Config, optional): Config to use

        Returns:
            List[str]: A list of versions
        """

        _params = json.dumps({'repositories': repositories.__dict__, 'cfg': cfg.__dict__}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/versions",
            data=_params,
            headers={"content-type": "application/json"}
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict['response']

        return _ret
            
        
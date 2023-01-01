from urllib import request, parse
import json
import logging
import urllib
from typing import Type

from arc.core.resource import Client, is_annotation_match  # noqa
import typing
from types import NoneType
import socket
from websocket import create_connection
import arc.core.resource
import resource_test
import arc.kind
import simple_parsing.helpers.serialization.serializable
import arc.config


class LotsOfUnionsClient(Client):
    def __init__(
        self,
        a: typing.Union[str, int],
        b: typing.Union[typing.Dict[str, typing.Any], typing.List[str]],
        c: typing.Optional[bool] = None,
        **kwargs,
    ) -> None:
        """A LotsOfUnions resource

        Args:
            a (Union[str, int]): An a
            b (Union[Dict[str, Any], List[str]]): A b
            c (Optional[bool], optional): A c. Defaults to None.
        """
        super().__init__(a=a, b=b, c=c, **kwargs)

    def diff(self, uri: str) -> str:
        """Diff of the given object from the URI

        Args:
            uri (str): URI to diff

        Returns:
            str: A diff
        """

        _params = json.dumps({"uri": uri}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/diff",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def echo(self, txt: typing.Optional[str] = None) -> str:
        """Echo a string back

        Args:
            txt (str): String to echo

        Returns:
            str: String echoed with a hello
        """
        if isinstance(txt, NoneType):
            _txt = None
        elif isinstance(txt, str):
            _txt = txt
        else:
            raise ValueError("Do not know how to serialize parameter 'txt'")

        _params = json.dumps({"txt": _txt}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/echo",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def health(self) -> typing.Dict[str, typing.Any]:
        """Health of the resource

        Returns:
            Dict[str, Any]: Resource health
        """

        _params = json.dumps({}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/health",
            data=_params,
            headers=_headers,
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
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/info",
            data=_params,
            headers=_headers,
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
        if isinstance(key, NoneType):
            _key = None
        elif isinstance(key, str):
            _key = key
        else:
            raise ValueError("Do not know how to serialize parameter 'key'")
        if isinstance(timeout, NoneType):
            _timeout = None
        elif isinstance(timeout, int):
            _timeout = timeout
        else:
            raise ValueError("Do not know how to serialize parameter 'timeout'")

        _params = json.dumps({"key": _key, "timeout": _timeout}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/lock",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def logs(self) -> typing.Iterable[str]:
        """Logs for the resource

        Returns:
            Iterable[str]: A stream of logs
        """
        _server_addr = f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes:{self.server_port}"

        # you need to create your own socket here
        _sock = socket.create_connection((f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes", self.server_port))

        _encoded = urllib.parse.urlencode({"data": json.dumps({})})
        _ws = create_connection(
            f"ws://{_server_addr}/logs?{_encoded}",
            header=[f"client-uuid: {str(self.uid)}"],
            socket=_sock,
        )
        try:
            while True:
                code, _data = _ws.recv_data()
                if code == 8:
                    break
                _jdict = json.loads(_data)
                _ret = _jdict["response"]

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

        _params = json.dumps({"uri": uri}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/merge",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = arc.core.resource.Resource.from_dict(_jdict)

        return _ret

    def notebook(self) -> None:
        """Launch a notebook for the object"""

        _params = json.dumps({}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/notebook",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def optional_obj(
        self,
        h: typing.Union[resource_test.Ham, typing.Dict[str, typing.Any]],
        return_dict: typing.Optional[bool] = None,
    ) -> typing.Union[resource_test.Ham, typing.Dict[str, typing.Any]]:
        """Recieves either a Ham or a dictionary and optionally returns a ham

        Args:
            h (Union[Ham, Dict[str, Any]]): A Ham or a dictionary of Ham

        Returns:
            Union[Ham, Dict[str, Any]]: A Ham or nothing
        """
        if isinstance(h, resource_test.Ham):
            _h = h.__dict__
        elif isinstance(h, typing.Dict):
            _h = h.__dict__
        else:
            raise ValueError("Do not know how to serialize parameter 'h'")
        if isinstance(return_dict, NoneType):
            _return_dict = None
        elif isinstance(return_dict, bool):
            _return_dict = return_dict
        else:
            raise ValueError("Do not know how to serialize parameter 'return_dict'")

        _params = json.dumps({"h": _h, "return_dict": _return_dict}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/optional_obj",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _deserialized: bool = False
        if not _deserialized:
            try:
                _ret = object.__new__(typing.Union)
                for k, v in _jdict.items():
                    setattr(_ret, k, v)
            except:  # noqa
                pass
        if not _deserialized:
            try:
                _ret = _jdict
            except:  # noqa
                pass
        if not _deserialized:
            raise ValueError("unable to deserialize returned value")

        return _ret

    def returns_optional(self, a: typing.Union[str, int]) -> typing.Optional[str]:
        """Optionally returns the given string or returns None if int

        Args:
            a (Union[str, int]): A string or int

        Returns:
            Optional[str]: An optional string
        """
        if isinstance(a, str):
            _a = a
        elif isinstance(a, int):
            _a = a
        else:
            raise ValueError("Do not know how to serialize parameter 'a'")

        _params = json.dumps({"a": _a}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/returns_optional",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _deserialized: bool = False
        if not _deserialized:
            try:
                _ret = _jdict["response"]
            except:  # noqa
                pass
        if not _deserialized:
            try:
                _ret = _jdict["response"]
            except:  # noqa
                pass
        if not _deserialized:
            raise ValueError("unable to deserialize returned value")

        return _ret

    def save(self, out_dir: str = "./artifacts") -> None:
        """Save the object

        Args:
            out_dir (str, optional): Directory to output the artiacts. Defaults to "./artifacts".
        """

        _params = json.dumps({"out_dir": out_dir}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/save",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def source(self) -> str:
        """Source code for the object"""

        _params = json.dumps({}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/source",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def sync(self) -> None:
        """Sync changes to a remote process"""

        _params = json.dumps({}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/sync",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def unlock(self, key: typing.Optional[str] = None, force: bool = False) -> None:
        """Unlock the kind

        Args:
            key (Optional[str], optional): Key to unlock, if needed. Defaults to None.
            force (bool, optional): Force unlock without a key. Defaults to False.
        """
        if isinstance(key, NoneType):
            _key = None
        elif isinstance(key, str):
            _key = key
        else:
            raise ValueError("Do not know how to serialize parameter 'key'")

        _params = json.dumps({"key": _key, "force": force}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/unlock",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def base_names(self) -> typing.List[str]:
        """Bases for the resource

        Raises:
            SystemError: Server bases

        Returns:
            List[str]: Bases of the server
        """

        _params = json.dumps({}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/base_names",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def clean_artifacts(self, dir: str = "./artifacts") -> None:
        """Clean any created artifacts

        Args:
            dir (str, optional): Directory where artifacts exist. Defaults to "./artifacts".
        """

        _params = json.dumps({"dir": dir}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/clean_artifacts",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def find(self, locator: arc.kind.ObjectLocator) -> typing.List[str]:
        """Find objects

        Args:
            locator (ObjectLocator): A locator of objects

        Returns:
            List[str]: A list of object uris
        """

        _params = json.dumps({"locator": locator.__dict__}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/find",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def from_env(self) -> arc.core.resource.Resource:
        """Create the server from the environment, it will look for a saved artifact,
        a config.json, or command line arguments

        Returns:
            Server: A server
        """

        _params = json.dumps({}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/from_env",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = arc.core.resource.Resource.from_dict(_jdict)

        return _ret

    def from_opts(
        self, opts: typing.Type[simple_parsing.helpers.serialization.serializable.Serializable]
    ) -> arc.core.resource.Resource:
        """Load server from Opts

        Args:
            cls (Type[&quot;Server&quot;]): Server
            opts (Opts): Opts to load from

        Returns:
            Server: A server
        """

        _params = json.dumps({}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/from_opts",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = arc.core.resource.Resource.from_dict(_jdict)

        return _ret

    def labels(self) -> typing.Dict[str, typing.Any]:
        """Labels for the resource

        Args:
            scm (Optional[SCM], optional): SCM to use. Defaults to None.

        Returns:
            Dict[str, Any]: Labels for the server
        """

        _params = json.dumps({}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/labels",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict

        return _ret

    def load(self, dir: str = "./artifacts") -> arc.core.resource.Resource:
        """Load the object

        Args:
            dir (str): Directory to the artifacts
        """

        _params = json.dumps({"dir": dir}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/load",
            data=_params,
            headers=_headers,
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
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/name",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def opts_schema(self) -> typing.Dict[str, typing.Any]:
        """Schema for the server options

        Returns:
            Dict[str, Any]: JsonSchema for the server options
        """

        _params = json.dumps({}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/opts_schema",
            data=_params,
            headers=_headers,
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
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/schema",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def short_name(self) -> str:
        """Short name for the resource

        Returns:
            str: A short name
        """

        _params = json.dumps({}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/short_name",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def store_cls(
        self, clean: bool = True, dev_dependencies: bool = False, sync_strategy: arc.config.RemoteSyncStrategy = "image"
    ) -> str:
        """Create an image from the server class that can be used to create servers from scratch

        Args:
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            sync_strategy (RemoteSyncStrategy, optional): Sync strategy to use. Defaults to RemoteSyncStrategy.IMAGE.

        Returns:
            str: URI for the image
        """

        _params = json.dumps(
            {"clean": clean, "dev_dependencies": dev_dependencies, "sync_strategy": sync_strategy}
        ).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/store_cls",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def versions(
        self, repositories: typing.Optional[typing.List[str]] = None, cfg: typing.Optional[arc.config.Config] = None
    ) -> typing.List[str]:
        """Find all versions of this type

        Args:
            cls (Type[Server]): the Server class
            repositories (List[str], optional): extra repositories to check
            cfg (Config, optional): Config to use

        Returns:
            List[str]: A list of versions
        """
        if isinstance(repositories, NoneType):
            _repositories = None
        elif isinstance(repositories, typing.List):
            _repositories = repositories.__dict__
        else:
            raise ValueError("Do not know how to serialize parameter 'repositories'")
        if isinstance(cfg, NoneType):
            _cfg = None
        elif isinstance(cfg, arc.config.Config):
            _cfg = cfg.__dict__
        else:
            raise ValueError("Do not know how to serialize parameter 'cfg'")

        _params = json.dumps({"repositories": _repositories, "cfg": _cfg}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/versions",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def _super_init(self, uri: str) -> None:
        super().__init__(uri)

    @classmethod
    def from_uri(cls: Type["LotsOfUnionsClient"], uri: str) -> "LotsOfUnionsClient":
        c = cls.__new__(cls)
        c._super_init(uri)
        return c

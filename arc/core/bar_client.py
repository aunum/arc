from urllib import request, parse
import json
import logging
import urllib

from arc.core.resource import Client
import typing
from types import NoneType
import socket
from websocket import create_connection
import arc.core.resource
import arc.kind
import simple_parsing.helpers.serialization.serializable
import arc.config


class BarClient(Client):
    def __init__(self, a: str, b: int, **kwargs) -> None:
        """A Bar resource

        Args:
            a (str): A string
            b (int): An int
        """
        super().__init__(a=a, b=b, **kwargs)

    def add(self, x: int, y: int) -> int:
        """Add x to y

        Args:
            x (int): Number
            y (int): Number

        Returns:
            int: Sum
        """

        _params = json.dumps({"x": x, "y": y}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/add",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def diff(self, uri: str) -> str:
        """Diff of the given object from the URI

        Args:
            uri (str): URI to diff

        Returns:
            str: A diff
        """

        _params = json.dumps({"uri": uri}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/diff",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def echo(self, txt: str) -> str:
        """Echo a string back

        Args:
            txt (str): String to echo

        Returns:
            str: String echoed with a hello
        """

        _params = json.dumps({"txt": txt}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/echo",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
        _req = request.Request(
            f"{self.server_addr}/health",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict

        return _ret

    def lock(
        self, key: typing.Optional[str] = None, timeout: typing.Optional[int] = None
    ) -> None:
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
        _req = request.Request(
            f"{self.server_addr}/lock",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
        _server_addr = (
            f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes:{self.server_port}"
        )

        # you need to create your own socket here
        _sock = socket.create_connection(
            (f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes", self.server_port)
        )

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
        _req = request.Request(
            f"{self.server_addr}/merge",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def save(self, out_dir: str = "./artifacts") -> None:
        """Save the object

        Args:
            out_dir (str, optional): Directory to output the artiacts. Defaults to "./artifacts".
        """

        _params = json.dumps({"out_dir": out_dir}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/save",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def set(self, a: str, b: int) -> None:
        """Set the params

        Args:
            a (str): A string
            b (int): An int
        """

        _params = json.dumps({"a": a, "b": b}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/set",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def source(self) -> str:
        """Source code for the object"""

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/source",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def store(self, dev_dependencies: bool = False, clean: bool = True) -> str:
        """Create a server image with the saved artifact

        Args:
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            clean (bool, optional): Whether to clean the generated files. Defaults to True.

        Returns:
            str: URI for the image
        """

        _params = json.dumps(
            {"dev_dependencies": dev_dependencies, "clean": clean}
        ).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/store",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def stream(self, a: str, num: int) -> typing.Iterator[str]:
        """Stream back the string for the given number of times

        Args:
            a (str): String to stream
            num (int): Number of times to return

        Yields:
            Iterator[str]: An iterator
        """
        _server_addr = (
            f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes:{self.server_port}"
        )

        # you need to create your own socket here
        _sock = socket.create_connection(
            (f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes", self.server_port)
        )

        _encoded = urllib.parse.urlencode({"data": json.dumps({"a": a, "num": num})})
        _ws = create_connection(
            f"ws://{_server_addr}/stream?{_encoded}",
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

    def sync(self) -> None:
        """Sync changes to a remote process"""

        _params = json.dumps({}).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/sync",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
        _req = request.Request(
            f"{self.server_addr}/unlock",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
        _req = request.Request(
            f"{self.server_addr}/base_names",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
        _req = request.Request(
            f"{self.server_addr}/clean_artifacts",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
        _req = request.Request(
            f"{self.server_addr}/find",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
        _req = request.Request(
            f"{self.server_addr}/from_env",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = arc.core.resource.Resource.from_dict(_jdict)

        return _ret

    def from_opts(
        self,
        opts: typing.Type[
            simple_parsing.helpers.serialization.serializable.Serializable
        ],
    ) -> arc.core.resource.Resource:
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
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
        _req = request.Request(
            f"{self.server_addr}/labels",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
        _req = request.Request(
            f"{self.server_addr}/load",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
        _req = request.Request(
            f"{self.server_addr}/opts_schema",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
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
        _req = request.Request(
            f"{self.server_addr}/short_name",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def store_cls(
        self,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: arc.config.RemoteSyncStrategy = "image",
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
            {
                "clean": clean,
                "dev_dependencies": dev_dependencies,
                "sync_strategy": sync_strategy,
            }
        ).encode("utf8")
        _req = request.Request(
            f"{self.server_addr}/store_cls",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

    def versions(
        self,
        repositories: typing.Optional[typing.List[str]] = None,
        cfg: typing.Optional[arc.config.Config] = None,
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

        _params = json.dumps({"repositories": _repositories, "cfg": _cfg}).encode(
            "utf8"
        )
        _req = request.Request(
            f"{self.server_addr}/versions",
            data=_params,
            headers={"content-type": "application/json", "client-uuid": str(self.uid)},
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        _jdict = json.loads(_data)
        _ret = _jdict["response"]

        return _ret

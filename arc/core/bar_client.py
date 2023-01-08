
from urllib import request, parse
import json
import logging
import urllib
import os
from typing import Type
from pathlib import Path

import lib_programname
from arc.core.resource import Client, is_annotation_match, json_is_type_match, deep_isinstance # noqa
import typing
import resource_test
from types import NoneType
import socket
from websocket import create_connection
import arc.core.resource
import arc.kind
import simple_parsing.helpers.serialization.serializable
import arc.config

if lib_programname.get_path_executed_script() == Path(os.path.dirname(__file__)).joinpath(Path('resource_test.py')):
    print("\n\n!!!!!!!! importing from __main__!!!!! \n\n")
    import __main__ as resource_test

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

        _params = json.dumps({'x': x, 'y': y}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/add",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: int
        _ret = _jdict

        return _ret
            
    def bake_hams(self, ham_by_name: typing.Dict[str, resource_test.Ham]) -> typing.Dict[str, resource_test.Ham]:
        """Bake the given hams

        Args:
            ham_by_name (Dict[str, Ham]): A map of Ham to name

        Returns:
            Dict[str, bool]: Whether the Hams were baked
        """

        _params = json.dumps({'ham_by_name': ham_by_name}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/bake_hams",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: typing.Dict[str, resource_test.Ham]
        if not json_is_type_match(typing.Dict[str, resource_test.Ham], _jdict):
            raise ValueError('JSON returned does not match type: typing.Dict[str, __main__.Ham]')
        _ret_dict: typing.Dict[str, resource_test.Ham] = {}
        for k, v in _jdict.items():
            if not is_annotation_match(resource_test.Ham.__annotations__, v):
                raise ValueError('JSON returned does not match type: resource_test.Ham')
            _ret = object.__new__(resource_test.Ham)  # type: ignore
            for k, v in v.items():
                setattr(_ret, k, v)
            _ret_dict[k] = _ret  # type: ignore
        _ret = _ret_dict

        return _ret
            
    def diff(self, uri: str) -> str:
        """Diff of the given object from the URI

        Args:
            uri (str): URI to diff

        Returns:
            str: A diff
        """

        _params = json.dumps({'uri': uri}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/diff",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: str
        _ret = _jdict

        return _ret
            
    def echo(self, txt: str) -> str:
        """Echo a string back

        Args:
            txt (str): String to echo

        Returns:
            str: String echoed with a hello
        """

        _params = json.dumps({'txt': txt}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/echo",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: str
        _ret = _jdict

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
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: typing.Dict[str, typing.Any]
        if not json_is_type_match(typing.Dict[str, typing.Any], _jdict):
            raise ValueError('JSON returned does not match type: typing.Dict[str, typing.Any]')
        _ret_dict: typing.Dict[str, typing.Any] = {}
        for k, v in _jdict.items():
            _ret = v
            _ret_dict[k] = _ret  # type: ignore
        _ret = _ret_dict

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
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: typing.Dict[str, typing.Any]
        if not json_is_type_match(typing.Dict[str, typing.Any], _jdict):
            raise ValueError('JSON returned does not match type: typing.Dict[str, typing.Any]')
        _ret_dict: typing.Dict[str, typing.Any] = {}
        for k, v in _jdict.items():
            _ret = v
            _ret_dict[k] = _ret  # type: ignore
        _ret = _ret_dict

        return _ret
            
    def lock(self, key: typing.Optional[str] = None, timeout: typing.Optional[int] = None) -> None:
        """Lock the process to only operate with the caller

        Args:
            key (Optional[str], optional): An optional key to secure the lock
            timeout (Optional[int], optional): Whether to unlock after a set amount of time. Defaults to None.
        """
        if deep_isinstance(key, None):
            _key = None  # type: ignore
        elif deep_isinstance(key, str):
            _key = key  # type: ignore
        else:
            raise ValueError(f"Do not know how to serialize parameter 'key' of type '{type(key)}'")
        if deep_isinstance(timeout, None):
            _timeout = None  # type: ignore
        elif deep_isinstance(timeout, int):
            _timeout = timeout  # type: ignore
        else:
            raise ValueError(f"Do not know how to serialize parameter 'timeout' of type '{type(timeout)}'")

        _params = json.dumps({'key': _key, 'timeout': _timeout}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/lock",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: None
        _ret = _jdict

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
                if 'reponse' in _jdict:
                    _jdict = _jdict['response']
                _ret: typing.Iterable[str]
                _ret = _jdict

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

        _params = json.dumps({'uri': uri}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/merge",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: arc.core.resource.Resource
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
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: None
        _ret = _jdict

        return _ret
            
    def save(self, out_dir: str = './artifacts') -> None:
        """Save the object

        Args:
            out_dir (str, optional): Directory to output the artiacts. Defaults to "./artifacts".
        """

        _params = json.dumps({'out_dir': out_dir}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/save",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: None
        _ret = _jdict

        return _ret
            
    def set(self, a: str, b: int) -> None:
        """Set the params

        Args:
            a (str): A string
            b (int): An int
        """

        _params = json.dumps({'a': a, 'b': b}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/set",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: None
        _ret = _jdict

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
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: str
        _ret = _jdict

        return _ret
            
    def stream(self, a: str, num: int) -> typing.Iterator[str]:
        """Stream back the string for the given number of times

        Args:
            a (str): String to stream
            num (int): Number of times to return

        Yields:
            Iterator[str]: An iterator
        """
        _server_addr = f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes:{self.server_port}"

        # you need to create your own socket here
        _sock = socket.create_connection((f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes", self.server_port))


        _encoded = urllib.parse.urlencode({"data": json.dumps({'a': a, 'num': num})})
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
                if 'reponse' in _jdict:
                    _jdict = _jdict['response']
                _ret: typing.Iterator[str]
                _ret = _jdict

                yield _ret

        except Exception as e:
            print("stream exception: ", e)
            raise e

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
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: None
        _ret = _jdict

        return _ret
            
    def unlock(self, key: typing.Optional[str] = None, force: bool = False) -> None:
        """Unlock the kind

        Args:
            key (Optional[str], optional): Key to unlock, if needed. Defaults to None.
            force (bool, optional): Force unlock without a key. Defaults to False.
        """
        if deep_isinstance(key, None):
            _key = None  # type: ignore
        elif deep_isinstance(key, str):
            _key = key  # type: ignore
        else:
            raise ValueError(f"Do not know how to serialize parameter 'key' of type '{type(key)}'")

        _params = json.dumps({'key': _key, 'force': force}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/unlock",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: None
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
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/base_names",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: typing.List[str]
        _ret = _jdict

        return _ret
            
    def clean_artifacts(self, dir: str = './artifacts') -> None:
        """Clean any created artifacts

        Args:
            dir (str, optional): Directory where artifacts exist. Defaults to "./artifacts".
        """

        _params = json.dumps({'dir': dir}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/clean_artifacts",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: None
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
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/find",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: typing.List[str]
        _ret = _jdict

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
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: arc.core.resource.Resource
        _ret = arc.core.resource.Resource.from_dict(_jdict)

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
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/from_opts",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: arc.core.resource.Resource
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
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: typing.Dict[str, typing.Any]
        if not json_is_type_match(typing.Dict[str, typing.Any], _jdict):
            raise ValueError('JSON returned does not match type: typing.Dict[str, typing.Any]')
        _ret_dict: typing.Dict[str, typing.Any] = {}
        for k, v in _jdict.items():
            _ret = v
            _ret_dict[k] = _ret  # type: ignore
        _ret = _ret_dict

        return _ret
            
    def load(self, dir: str = './artifacts') -> arc.core.resource.Resource:
        """Load the object

        Args:
            dir (str): Directory to the artifacts
        """

        _params = json.dumps({'dir': dir}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/load",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: arc.core.resource.Resource
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
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: str
        _ret = _jdict

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
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: typing.Dict[str, typing.Any]
        if not json_is_type_match(typing.Dict[str, typing.Any], _jdict):
            raise ValueError('JSON returned does not match type: typing.Dict[str, typing.Any]')
        _ret_dict: typing.Dict[str, typing.Any] = {}
        for k, v in _jdict.items():
            _ret = v
            _ret_dict[k] = _ret  # type: ignore
        _ret = _ret_dict

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
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: str
        _ret = _jdict

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
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: str
        _ret = _jdict

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

        _params = json.dumps({'clean': clean, 'dev_dependencies': dev_dependencies, 'sync_strategy': sync_strategy}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/store_cls",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: str
        _ret = _jdict

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
        if deep_isinstance(repositories, None):
            _repositories = None  # type: ignore
        elif deep_isinstance(repositories, typing.List[str]):
            _repositories = repositories.__dict__  # type: ignore
        else:
            raise ValueError(f"Do not know how to serialize parameter 'repositories' of type '{type(repositories)}'")
        if deep_isinstance(cfg, None):
            _cfg = None  # type: ignore
        elif deep_isinstance(cfg, arc.config.Config):
            _cfg = cfg.__dict__  # type: ignore
        else:
            raise ValueError(f"Do not know how to serialize parameter 'cfg' of type '{type(cfg)}'")

        _params = json.dumps({'repositories': _repositories, 'cfg': _cfg}).encode("utf8")
        _headers = {"content-type": "application/json", "client-uuid": str(self.uid)}
        _req = request.Request(
            f"{self.server_addr}/versions",
            data=_params,
            headers=_headers,
        )
        _resp = request.urlopen(_req)
        _data = _resp.read().decode("utf-8")
        print("_data: ", _data)
        _jdict = json.loads(_data)

        if 'reponse' in _jdict:
            _jdict = _jdict['response']
        print("_jdict: ", _jdict)

        _ret: typing.List[str]
        _ret = _jdict

        return _ret
            

    def _super_init(self, uri: str) -> None:
        super().__init__(uri)

    @classmethod
    def from_uri(cls: Type["BarClient"], uri: str) -> "BarClient":
        c = cls.__new__(cls)
        c._super_init(uri)
        return c
        
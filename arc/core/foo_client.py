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


class FooClient(Client):
    def copy(self) -> arc.kind.PID:
        """Copy the process

        Returns:
            PID: A process ID
        """
        params = json.dumps({}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/copy",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = object.__new__(arc.kind.PID)
        for k, v in jdict.items():
            setattr(ret, k, v)
        return ret

    def delete(self) -> None:
        """Delete the resource"""
        params = json.dumps({}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/delete",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]

        return ret

    def deploy(
        self: arc.core.resource.Resource,
        scm: typing.Optional[arc.scm.SCM] = None,
        clean: bool = True,
        dev_dependencies: bool = False,
        sync_strategy: arc.config.RemoteSyncStrategy = "image",
        **kwargs,
    ) -> arc.core.resource.Resource:
        """Create a deployment of the class, which will allow for the generation of instances remotely

        Args:
            scm (Optional[SCM], optional): SCM to use. Defaults to None.
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            sync_strategy (RemoteSyncStrategy, optional): Sync strategy to use. Defaults to RemoteSyncStrategy.IMAGE.

        Returns:
            Client: A client for the server
        """
        params = json.dumps(
            {
                "scm": scm,
                "clean": clean,
                "dev_dependencies": dev_dependencies,
                "sync_strategy": sync_strategy,
                "kwargs": kwargs,
            }
        ).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/deploy",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = arc.core.resource.Resource.from_dict(jdict)

        return ret

    def develop(
        self: arc.core.resource.Resource,
        clean: bool = True,
        dev_dependencies: bool = False,
        reuse: bool = True,
        **kwargs,
    ) -> arc.core.resource.Resource:
        """Create a deployment of the class, and sync local code to it

        Args:
            clean (bool, optional): Whether to clean generated files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            reuse (bool, optional): Whether to reuse existing running servers. Defaults to True.

        Returns:
            Client: A client for the server
        """
        params = json.dumps(
            {
                "clean": clean,
                "dev_dependencies": dev_dependencies,
                "reuse": reuse,
                "kwargs": kwargs,
            }
        ).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/develop",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = arc.core.resource.Resource.from_dict(jdict)

        return ret

    def diff(self, uri: str) -> str:
        """Diff of the given object from the URI

        Args:
            uri (str): URI to diff

        Returns:
            str: A diff
        """
        params = json.dumps({"uri": uri}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/diff",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]

        return ret

    def health(self) -> typing.Dict[str, typing.Any]:
        """Health of the resource

        Returns:
            Dict[str, Any]: Resource health
        """
        params = json.dumps({}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/health",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict

        return ret

    def info(self) -> typing.Dict[str, typing.Any]:
        """Info about the resource

        Returns:
            Dict[str, Any]: Resource info
        """
        params = json.dumps({}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/info",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict

        return ret

    def lock(self, key: typing.Optional[str] = None, timeout: typing.Optional[int] = None) -> None:
        """Lock the process to only operate with the caller

        Args:
            key (Optional[str], optional): An optional key to secure the lock
            timeout (Optional[int], optional): Whether to unlock after a set amount of time. Defaults to None.
        """
        params = json.dumps({"key": key, "timeout": timeout}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/lock",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]

        return ret

    def logs(self) -> str:
        """Logs for the resource

        Returns:
            Iterable[str]: A stream of logs
        """
        server_addr = f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes:{self.server_port}"

        # you need to create your own socket here
        sock = socket.create_connection((f"{self.pod_name}.pod.{self.pod_namespace}.kubernetes", self.server_port))

        encoded = parse.urlencode({})
        ws = create_connection(
            f"ws://{server_addr}/logs?{encoded}",
            header=[f"client-uuid: {self.uid}"],
            socket=sock,
        )
        try:
            while True:
                _, data = ws.recv_data()

                jdict = json.loads(data)
                end = jdict["end"]
                if end:
                    break
                ret = jdict["response"]

                yield ret

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
        params = json.dumps({"uri": uri}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/merge",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = arc.core.resource.Resource.from_dict(jdict)

        return ret

    def notebook(self) -> None:
        """Launch a notebook for the object"""
        params = json.dumps({}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/notebook",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]

        return ret

    def save(self, out_dir: str = "./artifacts") -> None:
        """Save the object

        Args:
            out_dir (str, optional): Directory to output the artiacts. Defaults to "./artifacts".
        """
        params = json.dumps({"out_dir": out_dir}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/save",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]

        return ret

    def serve(self, port: int = 8080, log_level: str = "info", reload: bool = True) -> None:
        """Serve the class

        Args:
            port (int, optional): Port to serve one. Defaults to 8080.
            log_level (str, optional): Log level. Defaults to "info".
            reload (bool, optional): Whether to hot reload. Defaults to True.
        """
        params = json.dumps({"port": port, "log_level": log_level, "reload": reload}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/serve",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]

        return ret

    def source(self) -> str:
        """Source code for the object"""
        params = json.dumps({}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/source",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]

        return ret

    def store(self, dev_dependencies: bool = False, clean: bool = True) -> str:
        """Create a server image with the saved artifact

        Args:
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            clean (bool, optional): Whether to clean the generated files. Defaults to True.

        Returns:
            str: URI for the image
        """
        params = json.dumps({"dev_dependencies": dev_dependencies, "clean": clean}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/store",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]

        return ret

    def sync(self) -> None:
        """Sync changes to a remote process"""
        params = json.dumps({}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/sync",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]

        return ret

    def test(self) -> None:

        params = json.dumps({}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/test",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]

        return ret

    def to_dict(
        self,
        omit_none: bool = True,
        validate: bool = False,
        validate_enums: bool = True,
        schema_type: dataclasses_jsonschema.type_defs.SchemaType = dataclasses_jsonschema.type_defs.SchemaType.DRAFT_06,
    ) -> typing.Dict[str, typing.Any]:
        """Converts the dataclass instance to a JSON encodable dict, with optional JSON schema validation.

        If omit_none (default True) is specified, any items with value None are removed
        """
        params = json.dumps(
            {
                "omit_none": omit_none,
                "validate": validate,
                "validate_enums": validate_enums,
                "schema_type": schema_type,
            }
        ).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/to_dict",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict

        return ret

    def to_json(self, omit_none: bool = True, validate: bool = False, **json_kwargs) -> str:

        params = json.dumps({"omit_none": omit_none, "validate": validate, "json_kwargs": json_kwargs}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/to_json",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]

        return ret

    def to_yaml(self, omit_none: bool = True, validate: bool = False, **yaml_kwargs) -> str:

        params = json.dumps({"omit_none": omit_none, "validate": validate, "yaml_kwargs": yaml_kwargs}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/to_yaml",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]

        return ret

    def unlock(self, key: typing.Optional[str] = None, force: bool = False) -> None:
        """Unlock the kind

        Args:
            key (Optional[str], optional): Key to unlock, if needed. Defaults to None.
            force (bool, optional): Force unlock without a key. Defaults to False.
        """
        params = json.dumps({"key": key, "force": force}).encode("utf8")
        req = request.Request(
            f"{self.server_addr}/unlock",
            data=params,
            headers={"content-type": "application/json"},
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]

        return ret

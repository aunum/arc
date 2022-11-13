from dataclasses import dataclass
from types import FunctionType
from typing import List, Dict, Type, Any, Iterable, get_args, get_type_hints, get_origin
import inspect
from inspect import Parameter

from typing_inspect import is_generic_type


SERVER_PORT = "8080"


class ParamBuilder:
    name: str
    param: Parameter
    imports: List[str]

    def __init__(self, name: str, param: Parameter) -> None:
        self.name = name
        self.param = param

    def gen(self) -> str:
        if self.name == "self":
            return ""

        _op = getattr(param.annotation, "to_dict", None)
        if callable(_op):
            params.append(f"'{k}': {k}.to_dict()")
            continue

        params.append(f"'{k}': {k}")


class FunctionBuilder:
    name: str
    fn: FunctionType
    imports: List[str]

    def __init__(self, name: str, fn: FunctionType) -> None:
        self.name = name
        self.fn = fn  # type: ignore

    def gen(self) -> str:
        sig = inspect.signature(self.fn, eval_str=True, follow_wrapped=True)
        print("sig: ", sig)

        for k in sig.parameters:
            if k == "self":
                continue
            param = sig.parameters[k]
            param_builder = ParamBuilder(param)

        return ""


class ClientBuilder:
    """Build a client for the given object"""

    obj: Type

    def __init__(self, obj: Type) -> None:
        if not hasattr(obj, "__dict__"):
            raise ValueError("Object must have __dict__ attribute")
        self.obj = obj

    def generate(self) -> str:
        imports: Dict[str, Any] = {}
        methods_code: str = ""
        fns = inspect.getmembers(self.obj, predicate=inspect.isfunction)
        for name, fn in fns:
            if name.startswith("_"):
                continue
            fbuilder = FunctionBuilder(name, fn)
            methods_code + fbuilder.gen()
            for _import in fbuilder.imports:
                imports[_import] = ""

        import_statements = "\n".join(imports.keys())
        return f"""
from arc.core.resource import Client
{import_statements}

class {self.obj.__name__}Client(Client):

{methods_code}
"""

    def _generate(self) -> str:
        fns = inspect.getmembers(self.obj, predicate=inspect.isfunction)
        print("fns: ", fns)
        print("type fns: ", type(fns))
        params: List[str] = []
        methods: List[str] = []
        imports: Dict[str, str] = {}
        for name, fn in fns:
            if name.startswith("_"):
                continue

            print("name: ", name)
            print("fn: ", fn)
            print("fn dict: ", fn)
            print("type fn: ", type(fn))
            sig = inspect.signature(fn, eval_str=True, follow_wrapped=True)
            print("sig: ", sig)
            print("sig str: ", str(sig))

            for k in sig.parameters:
                print("-------")
                print("k: ", k)
                print("type k: ", type(k))

                param = sig.parameters[k]

                print("param: ", param)
                print("dir param: ", dir(param))
                print("param annotation: ", param.annotation)
                print("param annotation mod: ", param.annotation.__module__)
                print("param name: ", param.name)
                print("param default: ", param.default)
                print("param kind: ", param.kind)
                # print("param annot: ", param.annotation)
                print("param annotation args: ", get_args(param.annotation))

                # I need to recursively call into the args, get create an import for it

                if k == "self":
                    continue
                _op = getattr(param.annotation, "to_dict", None)
                if callable(_op):
                    params.append(f"'{k}': {k}.to_dict()")
                    continue

                params.append(f"'{k}': {k}")

            import_statements: Dict[str, Any] = {}
            hints = get_type_hints(fn)

            def proc_hint(h: Type):
                print("===================")
                print("processing hint....")
                print("===================")
                mod = h.__module__
                print("h mod: ", mod)

                if mod == "builtins":
                    return

                if is_generic_type(h):
                    print("is generic")
                    args = get_args(h)
                    for arg in args:
                        print("processing arg: ", arg)
                        proc_hint(arg)

                    origin = get_origin(h)
                    if origin == list:
                        origin = List
                    if origin == dict:
                        origin = Dict
                    h = origin  # type: ignore

                # TODO: handle Union

                import_statements[f"from {mod} import {h.__name__}"] = None

            for hint in hints:
                print("hint: ", hint)
                h = hints[hint]
                proc_hint(h)

            ret = hints["return"]
            ret_op = getattr(ret, "from_dict", None)
            ser_line = "ret = jdict['response']"
            print("ret_op: ", ret_op)
            if callable(ret_op):
                ser_line = "ret = ret.from_dict(jdict)"

            params_joined = ",".join(params)

            if isinstance(ret, Iterable):
                client_fn = f"""
    def {name}{sig}:
        server_addr = f"{{self.pod_name}}.pod.{{self.pod_namespace}}.kubernetes:{SERVER_PORT}"

        # you need to create your own socket here
        sock = socket.create_connection((f"{{self.pod_name}}.pod.{{self.pod_namespace}}.kubernetes", SERVER_PORT))
        if self.uid is None:
            self.uid = uuid.uuid4()
        
        encoded = parse.urlencode({{{params_joined}}})
        ws = create_connection(
            f"ws://{{server_addr}}/{name}?{{encoded}}",
            header=[f"client-uuid: {{self.uid}}"],
            socket=sock,
        )
        try:
            while True:
                _, data = ws.recv_data()

                jdict = json.loads(data)
                end = jdict["end"]
                if end:
                    break
                {ser_line}
                yield ret

        except Exception as e:
            print("stream exception: ", e)
            raise e
"""
            else:
                client_fn = f"""
    def {name}{sig}:
        params = json.dumps({{{params_joined}}}).encode("utf8")
        req = request.Request(
            f"{{self.server_addr}}/{name}",
            data=params,
            headers={{"content-type": "application/json"}}
        )
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        {ser_line}
        return ret
            """
            methods.append(client_fn)

        imports_joined = "\n".join(import_statements.keys())
        methods_joined = "\n".join(methods)
        client_file = f"""
from urllib import request, parse
import json
import logging

from arc.serve.server import Client
{imports_joined}

class {self.obj.__name__}Client(Client):
{methods_joined}
        """

        return client_file

    def write(self, path: str = "./") -> str:
        pass

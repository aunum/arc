"""Entrypoint for the container"""


from typing import Callable, Optional
import inspect
from pathlib import PurePath

from git import Object

from arc.scm import SCM
from arc.image.build import REPO_ROOT, DEFAULT_PORT
from arc.config import RemoteSyncStrategy


def generate_entrypoint(
    func: Callable, port: int = DEFAULT_PORT, sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.CONTAINER
) -> str:
    """Generate the entrypoint for the container

    Args:
        func (Callable): function to use
        port (int, optional): port number
        strategy (RemoteSyncStrategy, optional): sync strategy. Defaults to Container

    Returns:
        str: an entrypoint command that can be used with python -c
    """

    func_module = inspect.getmodule(func)
    if func_module is None:
        raise SystemError(f"could not find module for func {func_module}")

    if func_module.__name__ == "__main__":
        return generate_main_entrypoint(func, port, sync_strategy)

    return generate_module_entrypoint(func, func_module.__name__, port, sync_strategy)


def _func_container_path(func: Callable, scm: Optional[SCM] = None) -> str:
    """Get the path of the function as it will be in the container"""

    if scm is None:
        scm = SCM()
    repo_root = PurePath(str(scm.git_repo.working_dir))

    func_filepath = PurePath(inspect.getfile(func))
    root_relative = func_filepath.relative_to(repo_root)
    container_path = PurePath(REPO_ROOT).joinpath(root_relative)
    return str(container_path)


def obj_container_path(obj: Object, scm: Optional[SCM] = None) -> str:
    """Get the path of the function as it will be in the container"""

    if scm is None:
        scm = SCM()
    repo_root = PurePath(str(scm.git_repo.working_dir))

    func_filepath = PurePath(inspect.getfile(obj))
    root_relative = func_filepath.relative_to(repo_root)
    container_path = PurePath(REPO_ROOT).joinpath(root_relative)
    return str(container_path)


def generate_module_entrypoint(func: Callable, module_name: str, port: int, sync_strategy: RemoteSyncStrategy) -> str:
    """Generate the entrypoint for the container for a standard module

    Args:
        module_name (str): module name
        func_name (str): function name
        port (int): port number
        strategy (RemoteSyncStrategy): sync strategy

    Returns:
        str: an entrypoint command that can be used with python -c
    """

    func_name = func.__name__
    container_path = _func_container_path(func)

    return f"""# This module is used as the entrypoint for the container
import logging
import os
import time
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler

logging.basicConfig(level=logging.INFO)

logging.info("sync strategy is {sync_strategy.value}")
if "{sync_strategy.value}" == "{RemoteSyncStrategy.CONTAINER.value}":
    while not os.path.exists("{container_path}"):
        logging.info("waiting for source to be copied...")
        time.sleep(1)
    logging.info("source has been copied")

# Is this safe to assume it will be in the container?
from arc.kube import run
run._REMOTE_CALL = True

from {module_name} import {func_name}

def lives() -> str:
    return "alive"

# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ("/RPC2",)

# Create server
with SimpleXMLRPCServer(("localhost", {port}),
                        requestHandler=RequestHandler, allow_none=True) as server:

    # register healthcheck
    server.register_function(lives)

    # register the function
    server.register_function({func_name})

    logging.info("running server for func '{module_name}.{func_name}' on port {port}")

    # Run the server's main loop
    server.serve_forever()
"""


def generate_main_entrypoint(func: Callable, port: int, sync_strategy: RemoteSyncStrategy) -> str:
    """Generate the entrypoint for the container for a __main__ module

    Args:
        func (str): function
        port (int): port number
        strategy (RemoteSyncStrategy): sync strategy

    Returns:
        str: an entrypoint command that can be used with python -c
    """
    container_path = _func_container_path(func)

    return f"""# This module is used as the entrypoint for the container
import logging
import os
import time
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler

import pickle

logging.basicConfig(level=logging.INFO)

logging.info("sync strategy is {sync_strategy.value}")
if "{sync_strategy.value}" == "{RemoteSyncStrategy.CONTAINER.value}":
    while not os.path.exists("{container_path}"):
        logging.info("waiting for source to be copied...")
        time.sleep(1)
    logging.info("source has been copied")

from arc.kube import run
run._REMOTE_CALL = True

import importlib.util
spec = importlib.util.spec_from_file_location("entrypoint", "{container_path}")
entrypoint_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entrypoint_mod)

def lives() -> str:
    return "alive"

def receive(args_bytes: bytes, kwargs_bytes: bytes) -> bytes:
    args = pickle.loads(args_bytes.data)
    kwargs = pickle.loads(kwargs_bytes.data)
    ret = entrypoint_mod.{func.__name__}(*args, **kwargs) 
    return pickle.dumps(ret)

# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ("/RPC2",)

# Create server
with SimpleXMLRPCServer(("localhost", {port}),
                        requestHandler=RequestHandler, allow_none=True) as server:

    # register healthcheck
    server.register_function(lives)

    # register the function
    server.register_function(receive)

    logging.info("running server for func '__main__.{func.__name__}' in file '{container_path}' on port {port}")

    # Run the server's main loop
    server.serve_forever()
"""


def generate_notebook_entrypoint(func_name: str, port: int, strategy: RemoteSyncStrategy) -> str:
    """Generate the entrypoint for the container for a notebook

    Args:
        func_name (str): function name
        port (int): port number

    Returns:
        str: an entrypoint command that can be used with python -c
    """
    # https://chapeau.freevariable.com/2017/12/module-frontier.html
    raise NotImplementedError("not yet implemented!")

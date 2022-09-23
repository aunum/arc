from dataclasses import dataclass, field
from typing import Optional
import os
from enum import Enum

import git
import tomli
from typing import Dict, Protocol

from arc.scm import SCM


class Opts(Protocol):
    # as already noted in comments, checking for this attribute is currently
    # the most reliable way to ascertain that something is a dataclass
    __dataclass_fields__: Dict


class RemoteSyncStrategy(str, Enum):
    """Strategy by which code source is synced remotely"""

    IMAGE = "image"
    """Create a new image to copy file changes"""

    CONTAINER = "container"
    """Copy the file changes directly into a running container"""


@dataclass
class Config:
    """Configuration for Arc"""

    registry_url: Optional[str] = None
    image_repository: Optional[str] = None
    docker_socket: Optional[str] = None
    kube_namespace: str = field(default_factory=str)
    remote_sync_strategy: Optional[RemoteSyncStrategy] = None

    def apply_defaults(self):
        if self.kube_namespace == "":
            repo_name = SCM().name()
            self.kube_namespace = repo_name.lower()

        if self.remote_sync_strategy is None:
            self.remote_sync_strategy = RemoteSyncStrategy.CONTAINER

    def load_pyproject(self):
        repo = git.Repo(".", search_parent_directories=True)
        root_repo_path = repo.working_tree_dir
        pyproject_path = os.path.join(str(root_repo_path), "pyproject.toml")

        if os.path.exists(pyproject_path):
            with open(pyproject_path, "rb") as f:
                pyproject_dict = tomli.load(f)

                try:
                    pyproject_dict["tool"]["arc"]
                except KeyError:
                    return

                try:
                    registry_url = pyproject_dict["tool"]["arc"]["registry_url"]
                    if self.registry_url is None:
                        self.registry_url = registry_url
                except KeyError:
                    pass

                try:
                    image_repository = pyproject_dict["tool"]["arc"]["image_repository"]
                    if self.image_repository is None:
                        self.image_repository = image_repository
                except KeyError:
                    pass

                try:
                    docker_socket = pyproject_dict["tool"]["arc"]["docker_socket"]
                    if self.docker_socket is None:
                        self.docker_socket = docker_socket
                except KeyError:
                    pass

                try:
                    kube_namespace = pyproject_dict["tool"]["arc"]["kube_namespace"]
                    if self.kube_namespace is None:
                        self.kube_namespace = kube_namespace
                except KeyError:
                    pass

                try:
                    remote_sync_strategy = pyproject_dict["tool"]["arc"]["remote_sync_strategy"]
                    if self.remote_sync_strategy is None:
                        self.remote_sync_strategy = RemoteSyncStrategy[remote_sync_strategy]
                except KeyError:
                    pass

    def __post_init__(self):
        self.load_pyproject()
        self.apply_defaults()

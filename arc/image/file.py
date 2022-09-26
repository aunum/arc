from typing import List, Optional, Union
import json
import os

import git

from arc.scm import SCM

ARC_DOCKERFILE_NAME = "Dockerfile.arc"


class ContainerFile:
    """A container file for building images"""

    _statements: List[str] = ["# this file was generated by arc"]
    _revision: str

    def __init__(self) -> None:
        self._revision = SCM().sha()

    def from_(self, image: str) -> None:
        statement = f"FROM {image}"
        self._statements.append(statement)

    def run(self, cmd: str) -> None:
        statement = f"RUN {cmd}"
        self._statements.append(statement)
    
    def shell(self, cmd: List[str]):
        statement = f"SHELL {json.dumps(cmd)}"
        self._statements.append(statement)

    def cmd(self, cmd: List[str]) -> None:
        statement = f"CMD {json.dumps(cmd)}"
        self._statements.append(statement)

    def label(self, key: str, value: str) -> None:
        statement = f'LABEL "{key}"="{value}"'
        self._statements.append(statement)

    def expose(self, port: int, protocol: Optional[str] = None) -> None:
        statement = f"EXPOSE {port}"
        if protocol is not None:
            statement = f"EXPOSE {port}/{protocol}"
        self._statements.append(statement)

    def env(self, key: str, value: str) -> None:
        statement = f'ENV {key}="{value}"'
        self._statements.append(statement)

    def copy(self, src: Union[str, List[str]], dest: str) -> None:
        statment = None
        if isinstance(src, str):
            statment = f"COPY {src} {dest}"
        else:
            src.append(dest)
            statment = f"COPY {json.dumps(src)}"

        self._statements.append(statment)

    def add(self, src: Union[str, List[str]], dest: str) -> None:
        statment = None
        if isinstance(src, str):
            statment = f"ADD {src} {dest}"
        else:
            src.append(dest)
            statment = f"ADD {json.dumps(src)}"
        self._statements.append(statment)

    def entrypoint(self, cmd: List[str]) -> None:
        statement = f"ENTRYPOINT {json.dumps(cmd)}"
        self._statements.append(statement)

    def volume(self, path: str) -> None:
        statement = f"VOLUME {path}"
        self._statements.append(statement)

    def user(self, user: str, group: Optional[str] = None) -> None:
        statement = f"USER {user}"
        if group is not None:
            statement = f"USER {user}:{group}"
        self._statements.append(statement)

    def workdir(self, path: str) -> None:
        statement = f"WORKDIR {path}"
        self._statements.append(statement)

    def arg(self, name: str, default: Optional[str] = None) -> None:
        statement = f"ARG {name}"
        if default is not None:
            statement = f"ARG {name}={default}"
        self._statements.append(statement)

    def __str__(self) -> str:
        return "\n".join(self._statements)


def containerfile_path() -> str:
    # we need to change this to project root instead of repository root, we need to walk up the tree till we find the root
    repo = git.Repo(".", search_parent_directories=True)
    root_repo_path = repo.working_tree_dir

    return os.path.join(str(root_repo_path), ARC_DOCKERFILE_NAME)


def write_containerfile(c: ContainerFile) -> str:
    dockerfile_path = containerfile_path()
    with open(dockerfile_path, "w") as f:
        f.write(str(c))
    return dockerfile_path


def delete_containerfile() -> None:
    os.remove(containerfile_path())
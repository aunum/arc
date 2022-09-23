from typing import Optional, Dict, Any, List
import os
import logging
import yaml
import sys

from docker import APIClient
import enlighten

from arc.image.file import ContainerFile, write_containerfile, ARC_DOCKERFILE_NAME
from arc.image.id import ImageID
from arc.config import Config, RemoteSyncStrategy
from arc.image.client import default_socket
from arc.scm import SCM

TOMLDict = Dict[str, Any]

REPO_ROOT = "/app"

DEFAULT_PORT = 8000


def img_tag(strategy: RemoteSyncStrategy, scm: Optional[SCM] = None, tag_prefix: Optional[str] = None) -> str:
    """Generate a repo hash by sync strategy

    Args:
        strategy (RemoteSyncStrategy): Strategy to use
        scm (SCM, optional): SCM to use. Defaults to None.
        tag_prefix (str, optional): Tag prefix to use. Defaults to None.

    Returns:
        str: a SHA256 hash
    """
    if scm is None:
        scm = SCM()

    hash = ""
    if strategy == RemoteSyncStrategy.IMAGE:
        hash = scm.sha()
    elif strategy == RemoteSyncStrategy.CONTAINER:
        hash = scm.base_sha()
    else:
        raise ValueError("uknown sync strategy")

    if tag_prefix is not None:
        return tag_prefix + hash

    return hash


def img_id(
    strategy: RemoteSyncStrategy,
    registry_url: Optional[str] = None,
    repository: Optional[str] = None,
    tag: Optional[str] = None,
    tag_prefix: Optional[str] = None,
    scm: Optional[SCM] = None,
) -> ImageID:
    if repository is None:
        repository = Config().image_repository
        if repository is None:
            raise ValueError("image_namespace not provided or found in pyproject.toml")

    if scm is None:
        scm = SCM()

    if tag is None:
        tag = img_tag(strategy, scm, tag_prefix=tag_prefix)

    if registry_url is None:
        # check in pyproject.toml
        registry_url = Config().registry_url

        if registry_url is None:
            registry_url = "docker.io"

    return ImageID(host=registry_url, repository=repository, tag=tag)


def build_containerfile(
    base_image: Optional[str] = None,
    dev_dependencies: bool = False,
    scm: Optional[SCM] = None,
    cfg: Optional[Config] = None,
    command: Optional[List[str]] = None,
    sync_strategy: Optional[RemoteSyncStrategy] = None,
) -> ContainerFile:
    """Build a Containerfile for the repo

    Args:
        base_image (Optional[str], optional): base image to use. Defaults to None.
        dev_dependencies (bool, optional): install dev dependencies. Defaults to False.
        scm (SCM, optional): SCM to use. Defaults to None.
        cfg (Config, optional): Config to use. Defaults to None.
        command (List[str], optional): Optional command to add to the container

    Returns:
        ContainerFile: A Containerfile
    """
    if scm is None:
        scm = SCM()

    if cfg is None:
        cfg = Config()

    container_file: Optional[ContainerFile] = None
    if scm.is_poetry_project():
        logging.info("building image for poetry project")
        if sync_strategy is None:
            sync_strategy = cfg.remote_sync_strategy
        if sync_strategy == RemoteSyncStrategy.IMAGE:
            container_file = build_poetry_containerfile(scm.load_pyproject(), base_image, dev_dependencies)
        elif sync_strategy == RemoteSyncStrategy.CONTAINER:
            container_file = build_poetry_base_containerfile(scm.load_pyproject(), base_image, dev_dependencies)
        else:
            raise SystemError("unknown sync strategy")

    if container_file is None:
        raise ValueError("Cannot build containterfile due to unknown project type")

    if command is not None:
        container_file.cmd(command)

    return container_file


def build_poetry_base_containerfile(
    pyproject_dict: Dict[str, Any],
    base_image: Optional[str] = None,
    dev_dependencies: bool = False,
    scm: Optional[SCM] = None,
) -> ContainerFile:
    """Build a Containerfile for a Poetry project

    Args:
        pyproject_dict (Dict[str, Any]): a parsed pyproject file
        base_image (str, optional): base image to use. Defaults to None.
        dev_dependencies (bool, optional): whether to install dev dependencies. Defaults to False.
        scm (SCM, optional): SCM to use. Defaults to None.

    Returns:
        ContainerFile: A Containerfile
    """
    if scm is None:
        scm = SCM()

    # check for poetry keys
    try:
        dependencies = pyproject_dict["tool"]["poetry"]["dependencies"]
    except KeyError:
        raise ValueError("no poetry.tool.dependencies section found in pyproject.toml")

    container_file = ContainerFile()

    # find base image
    if base_image is None:
        try:
            info = sys.version_info
            container_file.from_(f"python:{info.major}.{info.minor}.{info.micro}")
        except KeyError:
            raise ValueError("no poetry.tool.dependencies.python found in pyproject.toml")
    else:
        container_file.from_(base_image)

    # build image
    # container_file.env("POETRY_HOME", "/opt/poetry")
    # container_file.run("python3 -m venv $POETRY_HOME && $POETRY_HOME/bin/pip install poetry==1.2.0")
    # container_file.run("git clone https://github.com/python-poetry/poetry /poetry")
    # container_file.workdir("/poetry")
    # container_file.env("VIRTUAL_ENV", "/poetry-env")
    # container_file.env("PATH", "/poetry-env/bin:$POETRY_HOME/bin:$PATH")
    # container_file.run("python3 -m venv $VIRTUAL_ENV && poetry install")

    container_file.env("PYTHONUNBUFFERED", "1")
    container_file.env("PYTHONDONTWRITEBYTECODE", "1")
    container_file.env("PIP_NO_CACHE_DIR", "off")
    container_file.env("PIP_DISABLE_PIP_VERSION_CHECK", "on")
    container_file.env("POETRY_NO_INTERACTION", "1")
    # container_file.env("POETRY_VIRTUALENVS_CREATE", "false")
    container_file.env("PYTHONPATH", f"${{PYTHONPATH}}:/{REPO_ROOT}")

    # apt install -y libffi-dev
    container_file.run("apt update && apt install -y watchdog")
    container_file.run("pip install poetry==1.2.0 && poetry --version")
    # container_file.run("pip uninstall -y setuptools && pip install setuptools")

    container_file.workdir(REPO_ROOT)

    container_file.copy("poetry.lock pyproject.toml", f"{REPO_ROOT}/")
    # container_file.run("poetry run python -m pip install --upgrade setuptools")

    if dev_dependencies:
        container_file.run("poetry install --no-ansi")
    else:
        container_file.run("poetry install --no-ansi --no-dev")

    # NOTE: there is likely a better way of doing this; copying the .git directory
    # with the tar sync was causing errors, and it is needed for the algorithms to
    # work currently
    container_file.copy(".git", f"{REPO_ROOT}/.git/")

    container_file.expose(DEFAULT_PORT)

    return container_file


def build_poetry_containerfile(
    pyproject_dict: Dict[str, Any],
    base_image: Optional[str] = None,
    dev_dependencies: bool = False,
    scm: Optional[SCM] = None,
) -> ContainerFile:
    """Build a Containerfile for a Poetry project

    Args:
        pyproject_dict (Dict[str, Any]): a parsed pyproject file
        base_image (str, optional): base image to use. Defaults to None.
        dev_dependencies (bool, optional): whether to install dev dependencies. Defaults to False.
        scm (SCM, optional): SCM to use. Defaults to None.

    Returns:
        ContainerFile: A Containerfile
    """
    if scm is None:
        scm = SCM()

    container_file = build_poetry_base_containerfile(pyproject_dict, base_image, dev_dependencies, scm)

    # Fun stuff here because we don't want to mess with .dockerignore, exclude patterns
    # will be added soon https://github.com/moby/moby/issues/15771
    pkgs: Dict[str, List[str]] = {}
    for fp in scm.all_files():
        dir = os.path.dirname(fp)
        if dir in pkgs:
            pkgs[dir].append(fp)
        else:
            pkgs[dir] = [fp]

    for pkg, files in pkgs.items():
        if pkg != "":
            container_file.copy(files, os.path.join(f"{REPO_ROOT}/", pkg + "/"))
        else:
            container_file.copy(files, os.path.join(f"{REPO_ROOT}/"))

    container_file.copy(".git", f"{REPO_ROOT}/.git")

    return container_file


def build_conda_containerfile() -> ContainerFile:
    raise NotImplementedError("not yet implemented!")


def build_pip_containerfile() -> ContainerFile:
    raise NotImplementedError("not yet implemented!")


def build_img(
    c: ContainerFile,
    sync_strategy: RemoteSyncStrategy,
    registry_url: Optional[str] = None,
    repository: Optional[str] = None,
    tag: Optional[str] = None,
    docker_socket: Optional[str] = None,
    scm: Optional[SCM] = None,
    labels: Optional[Dict[str, str]] = None,
    tag_prefix: Optional[str] = None,
) -> ImageID:
    """Build image from Containerfile

    Args:
        c (ContainerFile): Containerfile to use
        registry_url (str, optional): registry URL. Defaults to None.
        repository (str, optional): repository name. Defaults to None.
        tag (str, optional): tag for image. Defaults to None.
        docker_socket (str, optional): docker socket to use. Defaults to None.
        scm (SCM, optional): SCM to use. Defaults to None.
        labels (Dict[str, str], optional): Labels to add to the image. Defaults to None.
        tag_prefix (str, optional): Prefix for the image tag. Defaults to None.

    Returns:
        ImageID: An ImageID
    """

    containerfile_path = write_containerfile(c)

    if docker_socket is None:
        docker_socket = default_socket()

    cli = APIClient(base_url=docker_socket)

    if scm is None:
        scm = SCM()

    image_id = img_id(
        sync_strategy, registry_url=registry_url, repository=repository, tag=tag, scm=scm, tag_prefix=tag_prefix
    )

    logging.info(f"building image using id '{image_id}'")

    for line in cli.build(
        path=os.path.dirname(containerfile_path),
        rm=True,
        tag=image_id.ref(),
        dockerfile=ARC_DOCKERFILE_NAME,
        decode=True,
        labels=labels,
    ):
        try:
            line = str(line["stream"])
            if line != "\n":
                print(line.strip("\n"))
        except Exception:
            print(yaml.dump(line))

    return image_id


def push_img(id: ImageID, docker_socket: str = None) -> None:
    """Push image

    Args:
        id (ImageID): image ID to push
        docker_socket (str, optional): docker socket to use. Defaults to None.
    """
    manager = enlighten.get_manager()
    counters: Dict[str, enlighten.Counter] = {}

    if docker_socket is None:
        docker_socket = default_socket()

    client = APIClient(base_url=docker_socket)

    logging.info("pushing docker image")

    for line in client.push(id.ref(), stream=True, decode=True):
        print(line)
        # print(line)
        # try:
        #     status = str(line["status"])
        #     counter_id = line["id"]
        #     try:
        #         counters[counter_id]
        #     except Exception:
        #         counters[counter_id] = manager.counter(desc=f"{line['id']} {status}")

        #     counters[line["id"]].desc = f"{line['id']} {status}"
        #     if status == "Pushing":
        #         counters[counter_id].total = line["progressDetail"]["total"]

        #         counters[counter_id].count = line["progressDetail"]["current"]
        #         if counters[counter_id].enabled:
        #             currentTime = time.time()
        #             counters[counter_id].refresh(elapsed=currentTime - counters[counter_id].start)
        #     else:
        #         counters[counter_id].refresh()
        # except Exception:
        #     if "status" in line:
        #         print(line["status"])
        #     elif "aux" in line:
        #         break
        #     else:
        #         print(yaml.dump(line))

    # for _, counter in counters.items():
    #     counter.clear()
    #     counter.close()

    logging.info("done pushing image")
    return


## We need to be able to build an image from S3/OCI/GS


def find_or_build_img(
    docker_socket: Optional[str] = None,
    scm: Optional[SCM] = None,
    cfg: Optional[Config] = None,
    sync_strategy: RemoteSyncStrategy = RemoteSyncStrategy.CONTAINER,
    dev_dependencies: bool = False,
    command: Optional[List[str]] = None,
    tag: Optional[str] = None,
    tag_prefix: Optional[str] = None,
    labels: Optional[Dict[str, str]] = None,
) -> ImageID:
    """Find the current image or build and push it

    Args:
        docker_socket (str, optional): docker socket to use. Defaults to None.
        scm (SCM, optional): SCM to use
        cfg (Config, optional): Config to use
        sync_strategy (RemoteSyncStrategy, optional): How to sync data
        command (List[str], optional): Optional command to add to the container
        tag (List[str], optional): Optional tag of the image
        tag_prefix (List[str], optional): Optional prefix for the tag of the image
        labels (Dict[str, str], optional): Labels to add to the image. Defaults to None.

    Returns:
        ImageID: An image ID
    """
    if docker_socket is None:
        docker_socket = default_socket()

    cli = APIClient(base_url=docker_socket)

    if scm is None:
        scm = SCM()

    if cfg is None:
        cfg = Config()

    desired_id = img_id(sync_strategy, scm=scm, tag=tag, tag_prefix=tag_prefix)

    # check if tag exists in current image cache
    for img in cli.images():
        ids = img["RepoTags"]
        if ids is None:
            logging.info("no image ids found")
            continue
        for id in ids:
            # print(f"checking id '{id}' against desired id '{desired_id}'")
            if str(id) == str(desired_id):
                logging.info("cached image found locally")
                return desired_id

    # if not then build
    logging.info("image not found locally... building")
    container_file = build_containerfile(
        command=command, sync_strategy=sync_strategy, dev_dependencies=dev_dependencies
    )

    image_id = build_img(container_file, sync_strategy, tag=tag, labels=labels, tag_prefix=tag_prefix)
    push_img(image_id)

    return image_id


def img_command(container_path: str, scm: Optional[SCM] = None) -> List[str]:
    """Create the CMD for the image based on the project type

    Args:
        container_path (str): Path to the executable
        scm (Optional[SCM], optional): An optional SCM to pass. Defaults to None.

    Returns:
        List[str]: A CMD list
    """
    if scm is None:
        scm = SCM()

    command = ["python", container_path]
    if scm.is_poetry_project():
        command = ["poetry", "run", "python", str(container_path)]

    return command


def cache_img() -> None:
    # https://github.com/senthilrch/kube-fledged
    return

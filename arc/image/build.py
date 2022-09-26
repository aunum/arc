from typing import Optional, Dict, Any, List
import os
import logging
import yaml
import sys
import subprocess

from docker import APIClient
import enlighten
from docker_image import reference

from arc.image.file import ContainerFile, write_containerfile, ARC_DOCKERFILE_NAME, delete_containerfile
from arc.image.id import ImageID
from arc.config import Config, RemoteSyncStrategy
from arc.image.client import default_socket
from arc.scm import SCM
from arc.util.rootpath import detect, load_conda_yaml

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
    image_repo: Optional[str] = None,
    tag: Optional[str] = None,
    tag_prefix: Optional[str] = None,
    scm: Optional[SCM] = None,
) -> ImageID:
    if image_repo is None:
        image_repo = Config().image_repo

    if scm is None:
        scm = SCM()

    if tag is None:
        tag = img_tag(strategy, scm, tag_prefix=tag_prefix)

    ref = reference.Reference.parse(image_repo)
    host, repo = ref.split_hostname()

    return ImageID(host=host, repository=repo, tag=tag)


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

    if sync_strategy is None:
        sync_strategy = cfg.remote_sync_strategy

    project_root = detect()
    project_root = os.path.join(REPO_ROOT, scm.rel_project_path())

    print("project root: ", project_root)
    if project_root is None:
        raise ValueError("could not find project root, looking for .git | requirements.txt" +
                         " | environment.yml | pyproject.toml")

    container_file: Optional[ContainerFile] = None
    if scm.is_poetry_project():
        logging.info("building image for poetry project")
        if sync_strategy == RemoteSyncStrategy.IMAGE:
            container_file = build_poetry_containerfile(scm.load_pyproject(), project_root, base_image,
                                                        dev_dependencies)
        elif sync_strategy == RemoteSyncStrategy.CONTAINER:
            container_file = build_poetry_base_containerfile(scm.load_pyproject(), project_root, base_image,
                                                             dev_dependencies)
        else:
            raise SystemError("unknown sync strategy")
    
    elif scm.is_pip_project():
        logging.info("building image for pip project")
        if sync_strategy == RemoteSyncStrategy.IMAGE:
            container_file = build_pip_containerfile(project_root, base_image)
        elif sync_strategy == RemoteSyncStrategy.CONTAINER:
            container_file = build_pip_base_containerfile(project_root, base_image)
        else:
            raise SystemError("unknown sync strategy")

    elif scm.is_conda_project():
        logging.info("building image for conda project")
        if sync_strategy == RemoteSyncStrategy.IMAGE:
            container_file = build_conda_containerfile(project_root, base_image)
        elif sync_strategy == RemoteSyncStrategy.CONTAINER:
            container_file = build_conda_base_containerfile(project_root, base_image)
        else:
            raise SystemError("unknown sync strategy")

    if container_file is None:
        raise ValueError("Cannot build containterfile due to unknown project type")

    if command is not None:
        container_file.cmd(command)

    return container_file


def _add_repo_files(
    container_file: ContainerFile,
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


def build_poetry_base_containerfile(
    pyproject_dict: Dict[str, Any],
    project_root: str,
    base_image: Optional[str] = None,
    dev_dependencies: bool = False,
    scm: Optional[SCM] = None,
) -> ContainerFile:
    """Build a Containerfile for a Poetry project

    Args:
        pyproject_dict (Dict[str, Any]): a parsed pyproject file
        project_root (str): Root of the python project
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
        pyproject_dict["tool"]["poetry"]["dependencies"]
    except KeyError:
        raise ValueError("no poetry.tool.dependencies section found in pyproject.toml")

    container_file = ContainerFile()

    # find base image
    if base_image is None:
        try:
            info = sys.version_info
            container_file.from_(f"python:{info.major}.{info.minor}.{info.micro}")
        except KeyError:
            raise ValueError("could not determine python version")
    else:
        container_file.from_(base_image)

    container_file.env("PYTHONUNBUFFERED", "1")
    container_file.env("PYTHONDONTWRITEBYTECODE", "1")
    container_file.env("PIP_NO_CACHE_DIR", "off")
    container_file.env("PIP_DISABLE_PIP_VERSION_CHECK", "on")
    container_file.env("POETRY_NO_INTERACTION", "1")
    # container_file.env("POETRY_VIRTUALENVS_CREATE", "false")

    container_file.env("PYTHONPATH", f"${{PYTHONPATH}}:/{REPO_ROOT}:/{project_root}")

    # apt install -y libffi-dev
    container_file.run("apt update && apt install -y watchdog")
    container_file.run("pip install poetry==1.2.0 && poetry --version")
    # container_file.run("pip uninstall -y setuptools && pip install setuptools")

    container_file.workdir(project_root)

    container_file.copy("poetry.lock pyproject.toml", f"{project_root}/")
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
    project_root: str,
    base_image: Optional[str] = None,
    dev_dependencies: bool = False,
    scm: Optional[SCM] = None,
) -> ContainerFile:
    """Build a Containerfile for a Poetry project

    Args:
        pyproject_dict (Dict[str, Any]): a parsed pyproject file
        project_root (str): Root of the python project
        base_image (str, optional): base image to use. Defaults to None.
        dev_dependencies (bool, optional): whether to install dev dependencies. Defaults to False.
        scm (SCM, optional): SCM to use. Defaults to None.

    Returns:
        ContainerFile: A Containerfile
    """
    if scm is None:
        scm = SCM()

    container_file = build_poetry_base_containerfile(pyproject_dict, project_root, base_image, dev_dependencies, scm)
    container_file = _add_repo_files(container_file, scm)

    return container_file


def build_conda_base_containerfile(project_root: str, base_image: Optional[str] = None, scm: Optional[SCM] = None) -> ContainerFile:
    if scm is None:
        scm = SCM()

    container_file = ContainerFile()

    # find base image
    if base_image is None:
        try:
            out = subprocess.check_output(["conda", "--version"])
            conda_ver = str(out).split(" ")
            if len(conda_ver) != 2:
                raise ValueError(f"could not determine conda version from: {conda_ver}")
            img = f"continuumio/miniconda:{conda_ver[1]}"
            logging.info(f"using base image: {img}")
            container_file.from_(img)
        except KeyError:
            logging.warn("could not determine conda version, trying latest")
            container_file.from_("continuumio/miniconda:latest")
    else:
        container_file.from_(base_image)

    # this needs to be project_root
    container_file.env("PYTHONPATH", f"${{PYTHONPATH}}:/{REPO_ROOT}:/{project_root}")

    container_file.run("apt update && apt install -y watchdog")

    container_file.workdir(project_root)
    container_file.copy("environment.yml", f"{project_root}/")

    conda_yaml = load_conda_yaml()
    if "name" not in conda_yaml:
        raise ValueError("cannot find 'name' in environment.yml")
    
    env_name = conda_yaml["name"]

    # https://stackoverflow.com/questions/55123637/activate-conda-environment-in-docker
    container_file.shell(["conda", "run", "--no-capture-output", "-n", env_name, "/bin/bash", "-c"])

    # NOTE: there is likely a better way of doing this; copying the .git directory
    # with the tar sync was causing errors, and it is needed for the algorithms to
    # work currently
    container_file.copy(".git", f"{REPO_ROOT}/.git/")

    container_file.expose(DEFAULT_PORT)

    return container_file


def build_conda_containerfile(project_root: str, base_image: Optional[str] = None, scm: Optional[SCM] = None) -> ContainerFile:
    container_file = build_conda_base_containerfile(project_root, base_image, scm)
    container_file = _add_repo_files(container_file, scm)
    return container_file


def build_pip_base_containerfile(project_root: str, base_image: Optional[str] = None, scm: Optional[SCM] = None) -> ContainerFile:
    if scm is None:
        scm = SCM()

    container_file = ContainerFile()

    # find base image
    if base_image is None:
        try:
            info = sys.version_info
            container_file.from_(f"python:{info.major}.{info.minor}.{info.micro}")
        except KeyError:
            raise ValueError("could not determine python version")
    else:
        container_file.from_(base_image)

    container_file.env("PYTHONUNBUFFERED", "1")
    container_file.env("PYTHONDONTWRITEBYTECODE", "1")
    container_file.env("PIP_NO_CACHE_DIR", "off")
    container_file.env("PIP_DISABLE_PIP_VERSION_CHECK", "on")

    container_file.env("PYTHONPATH", f"${{PYTHONPATH}}:/{REPO_ROOT}:/{project_root}")

    container_file.run("apt update && apt install -y watchdog")

    container_file.workdir(project_root)

    container_file.copy("requirements.txt", f"{project_root}/")

    container_file.run("python -m pip install -r requirements.txt")

    # NOTE: there is likely a better way of doing this; copying the .git directory
    # with the tar sync was causing errors, and it is needed for the algorithms to
    # work currently
    container_file.copy(".git", f"{REPO_ROOT}/.git/")

    container_file.expose(DEFAULT_PORT)

    return container_file


def build_pip_containerfile(project_root: str, base_image: Optional[str] = None, scm: Optional[SCM] = None) -> ContainerFile:
    container_file = build_pip_base_containerfile(project_root, base_image, scm)
    container_file = _add_repo_files(container_file, scm)
    return container_file


def build_img(
    c: ContainerFile,
    sync_strategy: RemoteSyncStrategy,
    image_repo: Optional[str] = None,
    tag: Optional[str] = None,
    docker_socket: Optional[str] = None,
    scm: Optional[SCM] = None,
    labels: Optional[Dict[str, str]] = None,
    tag_prefix: Optional[str] = None,
) -> ImageID:
    """Build image from Containerfile

    Args:
        c (ContainerFile): Containerfile to use
        image_repo (str, optional): repository name. Defaults to None.
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
        sync_strategy, image_repo=image_repo, tag=tag, scm=scm, tag_prefix=tag_prefix
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

    delete_containerfile()
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

    elif scm.is_pip_project():
        command = ["python", str(container_path)]

    elif scm.is_conda_project():
        conda_yaml = load_conda_yaml()
        if "name" not in conda_yaml:
            raise ValueError("cannot find 'name' in environment.yml")
        
        env_name = conda_yaml["name"]
        command = ["conda", "run", "--no-capture-output", "-n", env_name, "python", str(container_path)]

    else:
        raise ValueError("project type unknown")

    return command


def cache_img() -> None:
    # https://github.com/senthilrch/kube-fledged
    return

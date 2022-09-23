from typing import Any, Dict, List
import json
import time

import docker
from docker.utils.utils import parse_repository_tag
from docker.utils.config import load_general_config
from docker.auth import resolve_repository_name, load_config
from opencontainers.distribution.reggie import (
    NewClient,
    WithUsernamePassword,
    WithDebug,
    WithName,
    WithReference,
    WithDigest,
)


def clean_repo_name(name: str) -> str:
    """Clean the repo name

    Args:
        name (str): Name of the repo

    Returns:
        str: Repo name
    """
    if len(name.split("/")) == 1:
        name = f"library/{name}"
    return name


def get_oci_client(uri: str, cli: docker.APIClient = None) -> NewClient:
    """Get OCI client for a URI

    Args:
        uri (str): URI to find client for
        cli (docker.APIClient, optional): Docker client. Defaults to None.

    Returns:
        NewClient: an OCI client
    """
    # if cli is None:
    #     cli = docker.APIClient()

    repository, tag = parse_repository_tag(uri)
    registry, repo_name = resolve_repository_name(repository)

    general_configs = load_general_config()

    auth_configs = load_config(
        config_dict=general_configs,
        credstore_env=None,
    )
    auth_cfg = auth_configs.resolve_authconfig(registry)

    if "ServerAddress" in auth_cfg:
        server_addr = auth_cfg["ServerAddress"]
    elif "serveraddress" in auth_cfg:
        server_addr = auth_cfg["serveraddress"]
    else:
        raise ValueError("server address not found in auth config")

    if "Username" in auth_cfg:
        username = auth_cfg["Username"]
    elif "username" in auth_cfg:
        username = auth_cfg["username"]
    else:
        raise ValueError("username not found in auth config")

    if "Password" in auth_cfg:
        password = auth_cfg["Password"]
    elif "password" in auth_cfg:
        password = auth_cfg["password"]
    else:
        raise ValueError("password not found in auth config")

    client = NewClient(
        server_addr,
        WithUsernamePassword(username, password),
        WithDebug(True),
    )
    return client


def get_repo_tags(repo: str, cli: docker.APIClient = None) -> List[str]:
    """Get image tags

    Args:
        repo (str): Repo URI
        cli (docker.APIClient, optional): Docker client. Defaults to None.

    Returns:
        List[str]: A list of tags
    """

    repository, tag = parse_repository_tag(repo)
    registry, repo_name = resolve_repository_name(repository)

    repo_name = clean_repo_name(repo_name)

    client = get_oci_client(repo, cli)

    req = client.NewRequest("GET", "/v2/<name>/tags/list", WithName(repo_name))
    response = client.Do(req)
    return response.json()["tags"]


def get_img_labels(uri: str, cli: docker.APIClient = None) -> Dict[str, Any]:
    """Get any labels for an image

    Args:
        uri (str): URI to get labels for
        cli (docker.APIClient, optional): Docker client. Defaults to None.

    Returns:
        Dict[str, Any]: Dictionary of labels
    """
    repository, tag = parse_repository_tag(uri)
    registry, repo_name = resolve_repository_name(repository)

    client = get_oci_client(uri, cli)

    repo_name = clean_repo_name(repo_name)

    req = client.NewRequest(
        "GET", "/v2/<name>/manifests/<reference>", WithName(repo_name), WithReference(tag)
    ).SetHeader("Accept", "application/vnd.docker.distribution.manifest.v2+json")
    response = client.Do(req)

    digest = response.json()["config"]["digest"]
    req = client.NewRequest("GET", "/v2/<name>/blobs/<digest>", WithName(repo_name), WithDigest(digest)).SetHeader(
        "Accept", "application/vnd.docker.distribution.manifest.v2+json"
    )
    response = client.Do(req)
    js = response.json()

    if "Labels" not in js["config"]:
        raise ValueError(f"'Labels' not found in response from registry: {js}")

    labels = js["config"]["Labels"]

    return labels


def get_img_refs(uri: str, cli: docker.APIClient = None) -> Dict[str, Any]:
    """Get any references of an image

    Args:
        uri (str): Image URI
        cli (docker.APIClient, optional): Docker client. Defaults to None.

    Returns:
        Dict[str, Any]: Image refs if exist or nothing
    """

    labels = get_img_labels(uri, cli)
    if "refs" not in labels:
        return {}
    return json.loads(labels["refs"])

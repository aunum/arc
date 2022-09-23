import json

import docker
from docker.utils.utils import parse_repository_tag
from docker.auth import resolve_repository_name
from opencontainers.distribution.reggie import (
    NewClient,
    WithUsernamePassword,
    WithDefaultName,
    WithDebug,
    WithName,
    WithReference,
    WithDigest,
)


def test_client():
    pass

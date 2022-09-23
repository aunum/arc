from dataclasses import dataclass
from typing import Type


@dataclass
class URI:
    """An OCI URI"""

    repo: str
    """Repo name"""

    artifact_type: str
    """Type of artifact"""

    name: str
    """Name of the artifact"""

    version: str
    """Version of artifact"""

    @classmethod
    def parse(cls: Type["URI"], uri: str) -> "URI":
        s = uri.split(":")
        if len(s) < 2:
            raise ValueError("not a complete oci uri")
        repo = s[0]
        tag = s[1]

        t = tag.split("-")
        if len(t) < 3:
            raise ValueError("tag is not an arc artifact")

        return cls(repo, t[0], t[1], "-".join(t[2:]))

    def __str__(self) -> str:
        return f"{self.repo}:{self.artifact_type}-{self.name}-{self.version}"

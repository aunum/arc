from dataclasses import dataclass
from typing import TypeVar, Type
from urllib.parse import urljoin

from docker_image import reference


IT = TypeVar("IT", bound="ImageID")


@dataclass
class ImageID:
    host: str
    repository: str
    tag: str

    @classmethod
    def from_ref(cls: Type[IT], image_ref: str) -> IT:
        ref = reference.Reference.parse(image_ref)
        host, repo = ref.split_hostname()

        return cls(host=host, repository=repo, tag=ref["tag"])

    def ref(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"{urljoin(self.host, self.repository)}:{self.tag}"

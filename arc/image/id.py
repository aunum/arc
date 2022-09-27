from dataclasses import dataclass
from typing import TypeVar, Type
from urllib.parse import urljoin

from docker_image import reference


ID = TypeVar("ID", bound="ImageID")


@dataclass
class ImageID:
    host: str
    repository: str
    tag: str

    @classmethod
    def from_ref(cls: Type[ID], image_ref: str) -> ID:
        ref = reference.Reference.parse(image_ref)
        host, repo = ref.split_hostname()

        return cls(host=host, repository=repo, tag=ref["tag"])

    def ref(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f"{urljoin(self.host, self.repository)}:{self.tag}"

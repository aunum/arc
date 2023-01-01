from __future__ import annotations
from abc import ABC, abstractmethod, abstractproperty
from dataclasses import dataclass
from typing import Dict, Iterable, List, Any, Optional, Type, TypeVar

from simple_parsing.helpers import Serializable

OBJECT_URI_ENV = "OBJECT_URI"

K = TypeVar("K", bound="Kind")


@dataclass
class PID:
    """An ID for a running process"""

    object_uri: str
    """URI the process is built from"""

    process_uri: str
    """URI where the process is running"""


class ObjectLocator(ABC):
    """An object locator locates objects"""

    @abstractmethod
    def locate(self) -> List[str]:
        """Locate the object

        Returns:
            List[str]: A list of object URIs
        """
        pass


# TODO: should this be a mixin or regular object?
class ObjectStore(ABC):
    """An object store for objects"""

    @abstractmethod
    def store(self) -> str:
        pass

    @classmethod
    @abstractmethod
    def find(self, locator: ObjectLocator) -> List[str]:
        pass

    @classmethod
    @abstractmethod
    def versions(self) -> List[str]:
        pass


class Kind(ABC):
    """A Kind of object, this is the interface all Arc objects must satisfy"""

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """Name of the object

        Returns:
            str: Name of the server
        """
        pass

    @classmethod
    @abstractmethod
    def short_name(cls) -> str:
        """Short name for the object

        Returns:
            str: A short name
        """
        pass

    @classmethod
    @abstractmethod
    def base_names(cls) -> List[str]:
        """Bases for the object

        Returns:
            List[str]: Bases of the object
        """
        pass

    @abstractproperty
    def object_uri(self) -> str:
        """URI for the object

        Returns:
            str: A URI for the object
        """
        pass

    @abstractproperty
    def process_uri(self) -> str:
        """URI for the process

        Returns:
            str: A URI for the process
        """
        pass

    @abstractmethod
    def lock(self, key: Optional[str] = None, timeout: Optional[int] = None) -> None:
        """Lock the process to only operate with the caller

        Args:
            key (Optional[str], optional): An optional key to secure the lock
            timeout (Optional[int], optional): Whether to unlock after a set amount of time. Defaults to None.
        """
        pass

    @abstractmethod
    def unlock(self, key: Optional[str] = None, force: bool = False) -> None:
        """Unlock the kind

        Args:
            key (Optional[str], optional): Key to unlock, if needed. Defaults to None.
            force (bool, optional): Force unlock without a key. Defaults to False.
        """
        pass

    @classmethod
    @abstractmethod
    def store_cls(self, dev_dependencies: bool = False, clean: bool = True) -> str:
        """Create an artifact of the class

        Args:
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            clean (bool, optional): Whether to clean the generated files. Defaults to True.

        Returns:
            str: URI for the artifact
        """
        pass

    @abstractmethod
    def store(self, dev_dependencies: bool = False, clean: bool = True) -> str:
        """Create a artifact with the current objects state stored

        Args:
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            clean (bool, optional): Whether to clean the generated files. Defaults to True.

        Returns:
            str: URI for the artifact
        """
        pass

    @abstractmethod
    def copy(self) -> K:
        """Copy the kind

        Returns:
            Kind: A kind
        """
        pass

    @abstractmethod
    def diff(self, uri: str) -> str:
        """Diff of the given object from the URI

        Args:
            uri (str): URI to diff

        Returns:
            str: A diff
        """
        pass

    @abstractmethod
    def merge(self, uri: str) -> K:
        """Merge with the given resource

        Args:
            uri (str): Resource to merge with

        Returns:
            Kind: A Kind
        """
        pass

    @abstractmethod
    def sync(self) -> None:
        """Sync changes to a remote process"""
        pass

    @abstractmethod
    def source(self) -> str:
        """Source code for the object"""
        pass

    @abstractmethod
    def delete(self) -> None:
        """Delete the resource"""
        pass

    @classmethod
    @abstractmethod
    def from_uri(cls: Type[K], uri: str) -> K:
        """Create an instance of the class from the uri

        Args:
            uri (str): URI of the object

        Returns:
            K: A Kind
        """
        pass

    @classmethod
    @abstractmethod
    def client(
        cls: Type[K],
        clean: bool = True,
        dev_dependencies: bool = False,
        reuse: bool = True,
        hot: bool = False,
    ) -> Type[K]:
        """Develop on the object remotely, hot reloading code changes

        Args:
            clean (bool, optional): Whether to clean generate files. Defaults to True.
            dev_dependencies (bool, optional): Whether to install dev dependencies. Defaults to False.
            reuse (bool, optional): Whether to reuse existing processes. Defaults to True.
            hot (bool, optional): Whether to hot reload changes

        Returns:
            Type[Kind]: A type of Kind
        """
        pass

    @abstractmethod
    def notebook(self: K) -> None:
        """Launch a notebook for the object"""
        pass

    @abstractmethod
    def logs(self) -> Iterable[str]:
        """Logs for the process

        Returns:
            Iterable[str]: A stream of logs
        """
        pass

    @abstractmethod
    def save(self, out_dir: str = "./artifacts") -> None:
        """Save the object

        Args:
            out_dir (str, optional): Directory to output the artiacts. Defaults to "./artifacts".
        """
        pass

    @classmethod
    @abstractmethod
    def load(cls: Type[K], dir: str = "./artifacts") -> K:
        """Load the object

        Args:
            dir (str): Directory to the artifacts
        """
        pass

    @abstractmethod
    def info(self) -> Dict[str, Any]:
        """Info about the object

        Returns:
            Dict[str, Any]: Object info
        """
        pass

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """Health of the object

        Returns:
            Dict[str, Any]: Object health
        """
        pass

    @classmethod
    @abstractmethod
    def labels(self) -> Dict[str, Any]:
        """Labels of the object

        Returns:
            Dict[str, Any]: Object labels
        """
        pass

    @classmethod
    @abstractmethod
    def schema(cls) -> str:
        """Schema of the object

        Returns:
            str: Object schema
        """
        pass

    @classmethod
    @abstractmethod
    def find(cls, locator: ObjectLocator) -> List[K]:
        """Find objects of this kind

        Args:
            locator (ObjectLocator): A locator of objects

        Returns:
            List[B]: A list of objects
        """
        pass

    @classmethod
    @abstractmethod
    def versions(cls) -> List[str]:
        """All versions of the base

        Returns:
            List[str]: List of URIs
        """
        pass

    @classmethod
    @abstractmethod
    def clean_artifacts(cls, dir: str = "./artifacts") -> None:
        """Clean any created artifacts

        Args:
            dir (str, optional): Directory where artifacts exist. Defaults to "./artifacts".
        """
        pass

    @classmethod
    @abstractmethod
    def opts_schema(cls) -> Dict[str, Any]:
        """Schema for the server options

        Returns:
            Dict[str, Any]: JsonSchema for the server options
        """
        pass

    @classmethod
    @abstractmethod
    def opts(cls) -> Optional[Type[Serializable]]:
        """Options for the server

        Returns:
            Optional[Type[Serializable]]: Options for the server
        """
        pass

    @classmethod
    @abstractmethod
    def from_opts(cls: Type[K], opts: Type[Serializable]) -> K:
        """Load from Opts

        Args:
            opts (Opts): Opts to load from

        Returns:
            Base: A base
        """
        pass


class Runtime(ABC):
    """A runtime for processes"""

    @abstractmethod
    def run(self, k: Kind) -> PID:
        """Run a kind

        Args:
            k (Kind): A kind

        Returns:
            PID: The process ID
        """
        pass

    @abstractmethod
    def runs(self, k: Kind) -> Kind:
        """Run a kind, and connect

        Args:
            k (Kind): A kind

        Returns:
            Kind: The kind on a runtime
        """
        pass

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Iterator, List, Optional, Tuple, TypeVar, Dict, Type, NewType
from arc.data.encoding import ShapeEncoder
from enum import Enum

import numpy as np
from dataclasses_jsonschema import JsonSchemaMixin, DEFAULT_SCHEMA_TYPE, JsonDict, SchemaType
from dataclasses_jsonschema import JsonSchemaMixin, FieldEncoder


Y = TypeVar("Y", bound="YData")


class Score(ABC):
    """A score keeper"""

    @classmethod
    @abstractmethod
    def report_cls(cls) -> Type[EvalReport]:
        pass

    @abstractmethod
    def report(self, model_uri: str, job_uri: str) -> EvalReport:
        pass


class EvalReport(ABC):
    """An evaluation report"""

    @abstractmethod
    def repr_json(self) -> Dict[str, Any]:
        """Convert object to a JSON serializable dict

        Returns:
            Dict[str, Any]: A JSON serializable dict
        """
        pass

    @classmethod
    @abstractmethod
    def load_dict(cls: Type[EvalReport], data: Dict[str, Any]) -> EvalReport:
        """Load object from JSON

        Args:
            cls (Type[ClassData]): the EvalReport class
            data (Dict[str, Any]): the dict to create from

        Returns:
            ClassData: An EvalReport object
        """
        pass

    @classmethod
    @abstractmethod
    def load(cls: Type[EvalReport], uri: str) -> EvalReport:
        """Load object from URI

        Args:
            cls (Type[EvalReport]): the EvalReport class
            uri (str): URI to load

        Returns:
            EvalReport: A report
        """
        pass

    @classmethod
    @abstractmethod
    def find(
        cls: Type[EvalReport], artifact_uri: Optional[str] = None, repositories: Optional[List[str]] = None
    ) -> List[EvalReport]:
        """Find all reports for a given model URI

        Args:
            cls (Type[EvalReport]): the EvalReport class
            artifact_uri (str, optional): artifact URI to find reports for
            repositories (List[str], optional): extra repositories to check

        Returns:
            List[EvalReport]: A list of reports
        """
        pass

    @abstractmethod
    def store(self, repository: Optional[str] = None) -> None:
        """Store the report as an artifact

        Args:
            repository (Optional[str], optional): An optional reporitory to store the report. Defaults to the Config value.
        """
        pass


class SupervisedScore(Generic[Y], Score):
    """A score for supervised jobs"""

    y_true: Y
    y_pred: Y

    def __init__(self, y_true: Y, y_pred: Y):
        self.y_true = y_true
        self.y_pred = y_pred


class BatchType(str, Enum):
    """Type of batch (train, test, valid)"""

    TRAIN = "train"
    TEST = "test"
    VALID = "valid"


NDArray = np.ndarray

D = TypeVar("D", bound="Data")


class Data(ABC, JsonSchemaMixin):
    """Job data"""

    @abstractmethod
    def as_ndarray(self) -> NDArray:
        """Data as an NDArray

        Returns:
            NDArray: An NDArray of data
        """
        pass

    @classmethod
    @abstractmethod
    def short_name(self) -> str:
        """Short name for the data

        Returns:
            str: A short name
        """
        pass

    # NOTE: we need these methods because dataclasses_jsonschema doesn't currently support
    # a way to transpose np.ndarray to a list https://github.com/s-knibbs/dataclasses-jsonschema#custom-validation-using-newtype
    # should maybe use https://github.com/jcrist/msgspec
    # https://github.com/florimondmanca/msgpack-asgi
    def repr_json(self) -> Dict[str, Any]:
        """Convert object to a JSON serializable dict

        Returns:
            Dict[str, Any]: A JSON serializable dict
        """
        return self.__dict__

    @classmethod
    def load_dict(cls: Type[Data], data: Dict[str, Any]) -> Data:
        """Load object from JSON

        Args:
            cls (Type[Data]): A Data class
            data (Dict[str, Any]): Dict to create from

        Returns:
            Data: A Data object
        """
        return cls(**data)


class XData(Data):
    """Input data"""

    pass


class YData(Data):
    """Output data"""

    @classmethod
    @abstractmethod
    def score_cls(cls) -> Type[Score]:
        pass

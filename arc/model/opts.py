from abc import ABC, abstractclassmethod, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar, List, Any
from dataclasses import field

from enum import Enum

T = TypeVar("T")


@dataclass
class Range(Generic[T]):
    """Range for a parameter"""

    low: T
    high: T
    step: T

    default: T


class Tunable:
    """Tunable parameter"""

    name: str
    """Name of the parameter"""


class Opts(ABC):
    """Config for a model"""

    @classmethod
    def to_yaml(self) -> str:

        pass


class MultiClassClassificationLossOpts(str, Enum):
    CATEGORICAL_CROSSENTROPY = "categorical_crossentropy"
    SOFTMAX_CROSS_ENTROPY_WITH_LOGITS_V2 = "softmax_cross_entropy_with_logits_v2"


class OptimizerOpts(str, Enum):
    ADAM = "adam"

from typing import Optional, ClassVar, TypeVar, Tuple, List, Generic, Dict

from abc import ABC, abstractmethod

T = TypeVar("T")


class NumericTunable(Generic[T]):
    def __init__(self, min: T, max: T, step: T) -> None:
        self._min = min
        self._max = max
        self._step = step

    def min(self) -> T:
        return self._min

    def max(self) -> T:
        return self._max

    def step(self) -> T:
        return self._step


class CategoricalTunable(Generic[T]):
    def __init__(self, options: List[T]) -> None:
        self._options = options

    def options(self) -> List[T]:
        return self._options


class TunableMixin(ABC):
    @abstractmethod
    def tunables(self) -> List[NumericTunable | CategoricalTunable]:
        pass

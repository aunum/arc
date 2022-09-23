from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Iterator, List, Optional, Tuple, TypeVar, Dict, Type, NewType
from enum import Enum

import numpy as np
from dataclasses_jsonschema import JsonSchemaMixin, DEFAULT_SCHEMA_TYPE, JsonDict, SchemaType
from dataclasses_jsonschema import JsonSchemaMixin, FieldEncoder

from arc.data.types import NDArray, Data


@dataclass
class TextData(Data):
    """Text data"""

    data: NDArray
    """The text data as an ND array"""

    def as_ndarray(self) -> NDArray:
        """Image data as an NDArray

        Returns:
            NDArray: An NDArray of image data
        """
        return self.data

    def serialize(self):
        """Serialize data to JSON"""
        pass

    def load_json(self) -> "Data":
        """Load object from JSON"""
        pass

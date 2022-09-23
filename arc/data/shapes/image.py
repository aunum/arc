from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Iterator, List, Optional, Tuple, TypeVar, Dict, Type, NewType
from arc.data.encoding import ShapeEncoder
from enum import Enum

import numpy as np
from dataclasses_jsonschema import JsonSchemaMixin, DEFAULT_SCHEMA_TYPE, JsonDict, SchemaType
from dataclasses_jsonschema import JsonSchemaMixin, FieldEncoder

from arc.data.types import Data, NDArray


@dataclass
class ImageData(Data):
    """Image data"""

    data: NDArray
    """The image data as an NDArray"""

    width: int
    """Width of the image"""

    height: int
    """Height of the image"""

    channels: int
    """Number of channels in the image"""

    num_images: int
    """Number of images"""

    @classmethod
    def short_name(self) -> str:
        """Short name for the data

        Returns:
            str: The short name
        """
        return "img"

    def as_ndarray(self) -> NDArray:
        """Image data as an NDArray

        Returns:
            NDArray: An NDArray of image data
        """
        return self.data

    def as_image_shape(self) -> NDArray:
        """Reshape data to be the shape of the image

        Returns:
            NDArray: An NDArray of shape of the image
        """
        return self.data.reshape(self.num_images, self.height, self.width, self.channels)

    def repr_json(self) -> Dict[str, Any]:
        """Convert object to a JSON serializable dict

        Returns:
            Dict[str, Any]: A JSON serializable dict
        """
        d = self.__dict__
        d["data"] = self.data.tolist()
        return d

    @classmethod
    def load_dict(cls: Type[ImageData], data: Dict[str, Any]) -> ImageData:
        """Load object from JSON

        Args:
            cls (Type[ImageData]): the ImageData class
            data (Dict[str, Any]): The dictionary data used to umpack

        Returns:
            ImageData: An ImageData object
        """
        data["data"] = np.asarray(data["data"])
        return cls(**data)

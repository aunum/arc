from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Type

import numpy as np

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

    def compatible(self, data: ImageData) -> bool:
        """Are the two types of data compatible

        Args:
            data (ImageData): The ImageData to check

        Returns:
            bool: Whether the data is compatible
        """
        if data.width != self.width:
            return False

        if data.height != self.height:
            return False

        if data.channels != self.channels:
            return False

        return True

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

from typing import Optional, Iterator, Dict
from pathlib import Path
import logging
import random

from tableschema import Schema
import pandas as pd
import numpy as np
from mnist import MNIST as MNISTLoader

from arc.data.cache import ResourceCache
from arc.data.cache_test import TEST_CACHE
from arc.data.types import *
from arc.data.job import SupervisedJob, DEFAULT_BATCH_SIZE, DEFAULT_EPOCH_SIZE, SupervisedJobClient
from arc.model.types import Model, SupervisedModel
from arc.data.shapes.classes import ClassData, ClassEncoding
from arc.data.shapes.image import ImageData
from arc.config import RemoteSyncStrategy


class ClassifyDigitsJob(SupervisedJob[ImageData, ClassData]):
    """A job to classify handwritten digits"""

    cache: ResourceCache

    x_train: np.ndarray
    y_train: np.ndarray
    x_test: np.ndarray
    y_test: np.ndarray

    def __init__(self, cache: Optional[ResourceCache] = None) -> None:
        if cache is None:
            cache = ResourceCache()

        self.cache = cache
        train_images_path = self.cache.get("http://yann.lecun.com/exdb/mnist/train-images-idx3-ubyte.gz")
        self.cache.get("http://yann.lecun.com/exdb/mnist/train-labels-idx1-ubyte.gz")
        self.cache.get("http://yann.lecun.com/exdb/mnist/t10k-images-idx3-ubyte.gz")
        self.cache.get("http://yann.lecun.com/exdb/mnist/t10k-labels-idx1-ubyte.gz")

        mnist = MNISTLoader(Path(train_images_path).parent.absolute(), return_type="numpy")
        self.x_train, self.y_train = mnist.load_training()
        self.x_test, self.y_test = mnist.load_testing()

        self.x_train = self.x_train / 255
        self.x_test = self.x_test / 255

    @property
    def description(self) -> str:
        """Description of the job"""

        return "Classify images of handwritten digits 0-9"

    @property
    def name(self) -> str:
        """Name of the job"""

        return "Classify Digits"

    def stream(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        batch_type: BatchType = BatchType.TRAIN,
        shuffle: bool = True,
    ) -> Iterator[Tuple[ImageData, ClassData]]:
        """Stream data

        Args:
            batch_size (int, optional): Size of the batch. Defaults to DEFAULT_BATCH_SIZE.
            batch_type (BatchType, optional): Type of the batch. Defaults to BatchType.TRAIN.
            shuffle (bool, optional): Shuffle data on epoch end. Default to True

        Yields:
            Iterator[Tuple[ImageData, ClassData]]: An iterator of X and Y
        """

        x, y = self._data_by_type(batch_type)

        for i in range(x.shape[0] // batch_size):
            xb = x[batch_size * i : batch_size * (i + 1)]
            yb = y[batch_size * i : batch_size * (i + 1)]

            # is this too costly computationally?
            yield ImageData(xb, 28, 28, 1, batch_size), ClassData(yb, 10, batch_size, ClassEncoding.CATEGORICAL)

        indices = np.arange(len(x))

        if shuffle:
            logging.info(f"shuffling data")
            np.random.shuffle(indices)
            # TODO: this may not be working

    def sample(self, batch_size: int = DEFAULT_BATCH_SIZE) -> Tuple[ImageData, ClassData]:
        """Sample data

        Args:
            batch_size (int, optional): Size of the batch. Defaults to DEFAULT_BATCH_SIZE.

        Returns:
            Tuple[ImageData, ClassData]: A tuple of X and Y
        """

        x, y = self.x_train, self.y_train
        i = random.randint(1, x.shape[0] // batch_size)

        xb = x[batch_size * i : batch_size * (i + 1)]
        yb = y[batch_size * i : batch_size * (i + 1)]

        return ImageData(xb, 28, 28, 1, batch_size), ClassData(yb, 10, batch_size, ClassEncoding.CATEGORICAL)

    def _data_by_type(self, batch_type: BatchType) -> Tuple[np.ndarray, np.ndarray]:
        x: Optional[np.ndarray] = None
        y: Optional[np.ndarray] = None
        if batch_type == BatchType.TRAIN:
            x = self.x_train
            y = self.y_train
        elif batch_type == BatchType.TEST:
            x = self.x_test
            y = self.y_test
        elif batch_type == BatchType.VALID:
            # TODO: these really need to be different
            x = self.x_test
            y = self.y_test
        else:
            raise ValueError("Unknown batch type")

        return x, y


def test_job_img():

    client = ClassifyDigitsJob.deploy(dev_dependencies=True)
    print("client: ", client)

    versions = ClassifyDigitsJob.versions()
    assert len(versions) > 1
    print("versions: ", versions)

    print("info: ", client.info())

    x, y = client.sample()
    print("sample x: ", x)
    print("sample y: ", y)

    for x, y in client.stream():
        print("stream x: ", x)
        print("stream y: ", y)

    leaderboard = client.leaderboard()
    print("leaderboard: ", leaderboard)

    return


def test_job_container():

    client = ClassifyDigitsJob.develop()
    print("client: ", client)

    print("info: ", client.info())

    x, y = client.sample()
    print("sample x: ", x)
    print("sample y: ", y)

    for x, y in client.stream():
        print("stream x: ", x)
        print("stream y: ", y)

    leaderboard = client.leaderboard()
    print("leaderboard: ", leaderboard)

    return

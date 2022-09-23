from typing import Iterator
import numpy as np
from urllib.parse import urlparse


def stream_ndarray(x: np.ndarray, n=32) -> Iterator[np.ndarray]:
    """Stream ndarray as batches

    Args:
        x (np.ndarray): Array to batch from
        n (int, optional): Number of items in the batch. Defaults to 32.

    Yields:
        Iterator[np.ndarray]: A generator of ndarray batches
    """
    for i in range(np.shape[0] // n):
        yield x[n * i : n * (i + 1)]


class S3Url:
    """An S3 URL parser"""

    def __init__(self, url):
        self._parsed = urlparse(url, allow_fragments=False)

    def bucket(self):
        return self._parsed.netloc

    def key(self):
        if self._parsed.query:
            return self._parsed.path.lstrip("/") + "?" + self._parsed.query
        else:
            return self._parsed.path.lstrip("/")

    def url(self):
        return self._parsed.geturl()

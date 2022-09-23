"""Cache data"""

from typing import Optional
import os
from urllib.parse import urlparse
import urllib.request
import shutil
from pathlib import Path
import logging
import gzip

import boto3
from xdg import xdg_data_home

# Local caching

# Kubernetes caching

# should this be hypercopy? hycp? how does this blend with caching?


class ResourceCache:
    """Cache resources"""

    base_path: str

    def __init__(self, base_path: Optional[str] = None) -> None:
        if base_path is None:
            base_path = os.path.join(str(xdg_data_home()), "arc", "data")
        self.base_path = base_path

    def save(self, uri: str, overwrite: bool = True, unpack: bool = True) -> str:
        """Save the given URI locally

        Args:
            uri (str): URI identifier
            overwrite (bool, optional): whether to overwrite. Defaults to True.

        Raises:
            ValueError: if URI format is unknown

        Returns:
            str: a filepath to the resource
        """
        path = self._get_local_path(uri)
        path_obj = Path(path)
        path_dir = path_obj.parent.absolute()

        os.makedirs(path_dir, exist_ok=overwrite)

        if uri[:5] == "s3://":
            s3 = boto3.client("s3")
            with open(path, "wb") as f:
                o = urlparse(uri, allow_fragments=False)
                s3.download_fileobj(o.netloc, o.path.lstrip("/"), f)

        elif uri[:7] == "http://" or uri[:8] == "https://":
            urllib.request.urlretrieve(uri, path)

        else:
            raise ValueError("unsupported URI type")

        if unpack:
            if self._can_unpack_shutil(path):
                logging.info(f"unpacking {path} to {path_dir}")
                shutil.unpack_archive(path, path_dir)
                return str(path_dir)
            elif self._can_upack_gz(path):
                out_file = path.rstrip(".gz")
                logging.info(f"unpacking {path} to {out_file}")
                with gzip.open(path, "rb") as f_in:
                    with open(out_file, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                        return out_file
            else:
                return path
        else:
            return path

    def get(self, uri: str, download: bool = True) -> str:
        """Get the URI resource path, if not present then download

        Args:
            uri (str): URI to get, supports s3:// or http(s)://
            download (bool, optional): Whether to download if it doesn't exist locally. Defaults to True.

        Raises:
            ValueError: If resource is not in cache and download is false

        Returns:
            str: Path to the resource
        """
        path = self._get_local_path(uri)
        if os.path.exists(path):
            # TODO: should check if cache is up to date
            logging.info(f"resource '{uri}' exists locally, returning path")
            if self._can_unpack_shutil(uri):
                return str(Path(path).parent.absolute())
            elif self._can_upack_gz(uri):
                return path.rstrip(".gz")
            return path
        if download:
            logging.info(f"resource '{uri}' doesn't exist in cache, downloading...")
            return self.save(uri)
        raise ValueError(f"resource {uri} not in cache and 'download' parameter is false")

    def clear(self) -> None:
        """Clear the cache"""

        shutil.rmtree(self.base_path)

    def refresh(self) -> None:
        """Refresh the cache"""

        raise NotImplementedError()

    def _get_local_path(self, uri: str) -> str:
        if uri[:5] == "s3://":
            return os.path.join(self.base_path, "s3", uri[5:])

        elif uri[:7] == "http://":
            return os.path.join(self.base_path, "web", uri[7:])

        elif uri[:8] == "https://":
            return os.path.join(self.base_path, "web", uri[8:])

        raise ValueError("unsupported URI type")

    def _can_upack_gz(self, uri: str) -> bool:
        return os.fspath(uri).endswith(".gz")

    def _can_unpack_shutil(self, uri: str) -> bool:
        for _, exts, _ in shutil.get_unpack_formats():
            filename = os.fspath(uri)
            for ext in exts:
                if filename.endswith(ext):
                    return True
        return False

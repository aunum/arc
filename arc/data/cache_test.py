import logging
import os

from xdg import xdg_data_home

from arc.data.cache import ResourceCache

TEST_CACHE = ResourceCache(base_path=os.path.join(str(xdg_data_home()), "arc-test", "data"))


def test_cache():
    cache = TEST_CACHE

    path1 = cache.save("http://yann.lecun.com/exdb/mnist/train-images-idx3-ubyte.gz")
    logging.info(f"saved mnist to {path1}")

    path2 = cache.get("http://yann.lecun.com/exdb/mnist/train-images-idx3-ubyte.gz")
    assert path1 == path2
    logging.info(f"saved mnist 2 to {path2}")

    cache.get("http://yann.lecun.com/exdb/mnist/t10k-images-idx3-ubyte.gz")

    path3 = cache.save("s3://ai2-public-datasets/arc-classification/ARC-QuestionClassificationData.zip")
    logging.info(f"saved arc QA to {path3}")

    path4 = cache.get("s3://ai2-public-datasets/arc-classification/ARC-QuestionClassificationData.zip")
    assert path3 == path4
    logging.info(f"cached arc QA at {path4}")

    cache.clear()

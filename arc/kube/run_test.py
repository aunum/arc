from arc.kube.run import pod
from arc.scm import SCM
from pathlib import Path
import pandas as pd
import numpy as np


@pod(clean=True)
def basic() -> str:
    return "hello world"


@pod(clean=True)
def params(a: str, b: int, c: bool) -> str:
    print("a: ", a, "b: ", b, "c: ", c)
    return f"{a} / {b} / {c}"


@pod(clean=True)
def transpose_df(df: pd.DataFrame) -> pd.DataFrame:
    print("transposing: ", df)
    out = df.transpose()
    print("transposed: ", out)
    return out


def test_run():
    basic_out = basic()
    print("-> out basic: ", basic_out)

    params_out = params("test", 1, True)
    print("-> out params: ", params_out)

    df = pd.DataFrame(np.random.randint(0, 100, size=(100, 4)), columns=list("ABCD"))
    print("transposing df: ", df)
    transposed = transpose_df(df)
    print("-> out transposed: ", transposed)

    return


if __name__ == "__main__":
    test_run()

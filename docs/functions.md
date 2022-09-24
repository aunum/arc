# Functions

Arc also offers a simple means of executing python functions on kubernetes

```python
from arc.kube.run import pod
import pandas as pd

@pod
def transpose_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.transpose()
    return out

df = pd.DataFrame(np.random.randint(0, 100, size=(100, 4)), columns=list("ABCD"))
transposed = transpose_df(df)
```

This functionality is similar to Ray but with a tighter integration to Kubernetes. No backend is required and dependencies are auto-magically synced to the cluster. As code changes, it's hot-reloaded into the cluster.
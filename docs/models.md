# Models

A model represents a machine learning model implemented in any ML framework. It is simply a wrapper that allows for seemless remote training and implements the common IO types to make it highly reusable and consistently evaluated.

Models utilize the common IO types:

```python
class SupervisedModel(Generic[X, Y]):
    ...
```

An MNIST model:
```python
from arc.model.types import SupervisedModel
from arc.data.shapes.image import ImageData
from arc.data.shapes.classes import ClassData

class MultiClassImageClassifier(SupervisedModel[ImageData, ClassData])
    ...
```

Models can be ran local or remote. When running remote, a model can be hot reloaded into the cluster or hardened.

```python
# launch model on k8s are return a client to utilize it, hot reload code into cluster
client = MultiClassImageClassifier.develop()
client.fit(x, y)
client.save()
...

# launch model on k8s as a hardened artifact
client = MultiClassImageClassifier.deploy()
```

Models can also be loaded from from saved artifacts using their OCI URI:

```python
client = SupervisedModelClient[ImageData, ClassData](uri="aunum/arc:model-convmulticlassclassifier-a34g32h94h")
client.fit(x, y)

# Save a new image with the fine tuned model
uri = client.save()
```
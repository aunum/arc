![logo](./static/logo.png "Logo")

Economies of models


Arc is a declarative, minimalist, automation forward machine learning platform. It aims to commoditize models by standardizing their IO, making it easy to consume models from _any_ source using your language of choice.   

Arc makes the machine learning development lifecycle incredibly lightweight and seemless. Arc models and datastreams can easily be shared and reused within a team, company, or the larger world.   

Arc makes use of its standardization patterns to provide rich automation around the selection, tuning, and hardening of models.

-- _Arc is pre-alpha, things can and will break, feel free to open issues and requests_ --

## Tenants

* Lightwieght
* Compositional, built out of primitives
* Explicit
* Vizualiztion should be ubiquitos and free
* Observable
* Cloud native
* Few dependencies
* Easy UX
* Rapid iteration

## Installation

```sh
pip install arc
```

Arc only requires a working `KUBECONFIG` and an image repository. Arc has 0 runtime dependencies and works with any vanilla Kubernetes cluster :)    

If you need a kubernetes cluster, Arc works will with [kind](https://kind.sigs.k8s.io/) locally

## Quick Start

See the [MNIST example](examples/mnist/README.md)

## Concepts

### X and Y
Much of Arc's capabilities revolve around standardized IO for models and tasks. Arc offers a compositional experience for defining the input and output of models.

Arc provides a set of basic data types for common ML tasks, a user can also implement the [Data class](arc/data/types.py) to extend the functionality to any data type.   

```python
X: ImageData | TextData | VideoData | AudioData | TableData
Y: ClassData | LabelData | TextData | ImageData  
```

By defining the common IO types we can now compose them into whatever task we need:

To create a multi-class image classifier we just parameterize the `Model` type with `ImageData` as our `X` and `ClassData` as our `Y`
```python
multi_class_img_classifier = SupervisedModel[ImageData, ClassData]
```

To create a multi-label text classifier we parameterize with `TextData` as our `X` and `LabelData` as our `Y`
```python
multi_label_text_classifier = SupervisedModel[TextData, LabelData]
```

To create a text to image model with parameterize with  `TextData` as our `X` and `ImageData` as our `Y`
```python
txt_to_img_model = SupervisedModel[TextData, ImageData]
```

By standardizing these types we create a highly ergonomic interface which allows us to consistently utilize and evaluate any ML model.

### Job
A job defines a task to be completed by a machine learning model.    

Jobs offer a means of streaming training data as well as a consistent way of evaluating models regardless of their framework. Jobs are executable containers built for k8s. It can be useful to think of jobs as an a more flexible Kaggle.

Jobs utilize the common IO types:

```python
class SupervisedJob(Generic[X, Y]):
    ...
```

An MNIST job:
```python
from arc.data.job import SupervisedJob
from arc.data.shapes.image import ImageData
from arc.data.shapes.classes import ClassData

class ClassifyDigitsJob(SupervisedJob[ImageData, ClassData])
    ...
```

Jobs are super simple to use with any model implementing the common IO types:
```python
# stream X, Y batches from job
for x, y in job.stream():
    metrics = model.fit(x, y)

# sample X, Y from job
sample_img, sample_class = job.sample(12)
y_pred = model.predict(sample_img)

# evaluate any model consistently
report = job.evaluate(model)
```

Jobs can be ran local or remote. When running remote, a job can be hot reloaded into the cluster or hardened.

```python
# launch job on k8s are return a client to utilize it, hot reload code into cluster
client = ClassifyDigitsJob.develop()
client.sample(1)
...

# launch job on k8s as a hardened artifact
client = ClassifyDigitsJob.deploy()
```

Jobs can also be loaded from saved artifacts using their OCI URI:
```python
client = SupervisedJobClient[ImageData, ClassData](uri="aunum/arc:job-classifydigits-a34g32h94h")
x, y = client.sample(1)
```
### Model
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

### Trainer
A Trainer can train one or many models for jobs

```python
from arc.model.trainer import Trainer
from arc.data.shapes.image import ImageData
from arc.data.shapes.classes import ClassData

# Create a multiclass image classifier trainer and run it on kubernetes
trainer = Trainer[ImageData, ClassData].deploy()

# Some models to train
models = ["aunum/arc:model-convmulticlassimageclassifier-d946d04-43845ac", "aunum/arc:model-densemulticlassimageclassifier-r906d05-11821re"]

# Train the models by launching them on kubernetes concurrently and streaming the job data to them, finally evaluating them
reports = trainer.train(job=ClassifyDigitsJob, model=models)
```

### Finder
A Finder offers a means of finding models for for a job based on the IO and distribution the model was trained on.

// TODO

### Functions
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


## Roadmap

### Core
- [x] Remote model saving
- [x] Trainer interface
- [ ] Finder interface
- [ ] Predictor interface
- [ ] Notebook support
- [ ] Conda build environments
- [ ] Pip build environments
- [ ] Whylogs integration
- [ ] Kubernetes provider
- [ ] Msgpack encoding
- [ ] Monetization
- [ ] Notebooks on running models as ephemeral containers
- [ ] Actors

### Data types
- [ ] Text
- [ ] Multi-label
- [ ] Video
- [ ] Audio
- [ ] Table
- [ ] Timeseries

### Integrations
- [ ] Huggingface
- [ ] Torch.hub
- [ ] AWS (sagemaker and comprehend)
- [ ] Tensorflow hub
- [ ] Google cloud
- [ ] Replicate

### UX
- [ ] UI
- [ ] Support a second language (Go or JS)
- [ ] CLI
- [ ] Docs
- [ ] Slack Bot
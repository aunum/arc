# Jobs

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
# Trainer
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
import logging

from arc.data.shapes.classes import ClassData
from arc.data.shapes.image import ImageData
from arc.data.job_test import ClassifyDigitsJob
from arc.model.trainer import Trainer

logging.basicConfig(level=logging.INFO)


print("creating trainer")
trainer = Trainer[ImageData, ClassData].develop()
model = "oldoceancreature/arc:model-convmulticlassimageclassifier-d946d04-43845ac"

print("training...")
reports = trainer.train(job=ClassifyDigitsJob, model=model, dev_dependencies=True)

print("reports: ", reports)

from typing import Optional
import logging
import os

import tensorflow as tf
from tensorflow.python import keras
from tensorflow.python.keras import layers
import cloudpickle as pickle

from arc.data.shapes.classes import ClassData, ClassEncoding
from arc.data.shapes.image import ImageData
from arc.data.job_test import ClassifyDigitsJob
from arc.model.types import ModelPhase, MultiClassImageClassifier
from arc.model.metrics import Metrics
from arc.model.opts import MultiClassClassificationLossOpts, OptimizerOpts
from arc.model.trainer import Trainer
from arc.util.rootpath import detect


logging.basicConfig(level=logging.INFO)


class ConvMultiClassImageClassifier(MultiClassImageClassifier):
    """A multi-class image classifier using convnet"""

    loss: MultiClassClassificationLossOpts = MultiClassClassificationLossOpts.CATEGORICAL_CROSSENTROPY
    optimizer: OptimizerOpts = OptimizerOpts.ADAM
    learning_rate: float = 0.001

    _model: Optional[keras.Sequential] = None
    _phase: ModelPhase = ModelPhase.INITIALIZED

    def __init__(
        self,
        loss: MultiClassClassificationLossOpts = MultiClassClassificationLossOpts.CATEGORICAL_CROSSENTROPY,
        optimizer: OptimizerOpts = OptimizerOpts.ADAM,
        learning_rate: float = 0.001,
    ) -> None:
        self.loss = loss
        self.optimizer = optimizer
        self.learning_rate = learning_rate

    def name(self) -> str:
        """Name of the model

        Returns:
            str: Model Name
        """
        return "ConvMultiClassImageClassifier"

    def phase(self) -> ModelPhase:
        """Phase of the model

        Returns:
            ModelPhase: Model phase
        """
        return self._phase

    def compile(self, x: ImageData, y: ClassData) -> None:
        """Compile the model

        Args:
            x (X): Sample input
            y (Y): Sample output
        """

        self.input_shape = x.as_image_shape().squeeze(axis=0).shape
        logging.info(f"x input shape: {self.input_shape}")

        self.num_classes = y.num_classes
        logging.info(f"y num classes: {self.num_classes}")

        self._model = keras.Sequential(
            [
                layers.InputLayer(self.input_shape),
                layers.Conv2D(32, kernel_size=(3, 3), activation="relu"),
                layers.MaxPooling2D(pool_size=(2, 2)),
                layers.Conv2D(64, kernel_size=(3, 3), activation="relu"),
                layers.MaxPooling2D(pool_size=(2, 2)),
                layers.Flatten(),
                layers.Dropout(0.5),
                layers.Dense(y.num_classes, activation="softmax"),
            ]
        )
        logging.info(self._model.summary())
        self._model.compile(loss=self.loss.value, optimizer=self.optimizer.value, metrics=["accuracy"])

        # TODO: get rid of this with a wrapper
        self._phase = ModelPhase.COMPILED
        pass

    def fit(
        self,
        x: ImageData,
        y: ClassData,
    ) -> Metrics:
        """Fit X to Y

        Args:
            x (ImageData): Input image data
            y (ClassData): Expected class data

        Returns:
            Metrics: Metrics
        """
        self._phase = ModelPhase.TRAINED
        if self._model is None:
            raise ValueError("model not compiled")

        return self._model.train_on_batch(x.as_image_shape(), y.as_one_hot().as_ndarray(), return_dict=True)

    def predict(self, x: ImageData) -> ClassData:
        """Predict Y given X

        Args:
            x (ImageData): Input image data

        Returns:
            ClassData: Output class data
        """
        if self._model is None:
            raise ValueError("model not compiled")

        y = self._model.predict_on_batch(x.as_image_shape())
        return ClassData(y, self.num_classes, x.num_images, ClassEncoding.PROBABILITIES).as_categorical()

    def save(self, out_dir: str = "./model") -> None:
        """Save the model

        Args:
            out_dir (str, optional): Directory to output the model. Defaults to "./model".
        """
        if self._model is None:
            raise ValueError("model is None")

        self._model.save(os.path.join(out_dir, "tf_model"))
        self._model = None
        out_path = os.path.join(out_dir, "model.pkl")
        with open(out_path, "wb") as f:
            pickle.dump(self, f)
        return

    @classmethod
    def load(cls, dir: str = "./model") -> "ConvMultiClassImageClassifier":
        """Load the model

        Args:
            dir (str, optional): Directory to the model. Defaults to "./model"
        """
        tf_model = tf.keras.models.load_model(os.path.join(dir, "tf_model"))
        path = os.path.join(dir, "model.pkl")
        with open(path, "r") as f:
            classifier: "ConvMultiClassImageClassifier" = pickle.loads(f)

        classifier._model = tf_model

        return classifier


if __name__ == "__main__":

    # print("current working dir: ", os.getcwd())
    # print("rootpath: ", detect())

    print("creating model in k8s...")
    model = ConvMultiClassImageClassifier.develop()
    print("model info: ", model.info())

    print("creating job in k8s...")
    job = ClassifyDigitsJob.develop()

    print("sampling job")
    sample_img, sample_class = job.sample(1)
    print("sample classes: ", sample_class)

    print("compiling model...")
    model.compile(sample_img, sample_class)

    max = 0
    for x, y in job.stream():
        metrics = model.fit(x, y)
        print("metrics: ", metrics)
        max += 1
        if max > 50:
            break

    print("predicting...")
    sample_img, sample_class = job.sample(12)
    y_pred = model.predict(sample_img)
    print("y pred: ", y_pred)

    print("evaluting...")
    report = job.evaluate(model)
    print(str(report))

    trainer = Trainer[ImageData, ClassData].develop()

    reports = trainer.train(job, model)

    # for uri, report in reports.items():
    #     print(f"report for {uri}: {report}")

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Iterator, List, Optional, Tuple, TypeVar, Dict, Type, NewType
from arc.data.encoding import ShapeEncoder
from enum import Enum
import json

import numpy as np
from dataclasses_jsonschema import JsonSchemaMixin, DEFAULT_SCHEMA_TYPE, JsonDict, SchemaType
from dataclasses_jsonschema import JsonSchemaMixin, FieldEncoder

from arc.data.types import NDArray, Data, EvalReport, SupervisedScore

from optparse import Option
from typing import TypeVar, Generic, Optional, List, Type, Dict, Any
from datetime import datetime
import logging

import numpy as np
from sklearn.metrics import confusion_matrix
from tabulate import tabulate
import blobz
import jsonpickle

from arc.data.types import NDArray, Data
from arc.config import Config
from arc.data.refs import MODEL_REF_LABEL, OBJECT_TYPE_LABEL, JOB_REF_LABEL
from arc.data.oci import URI
from arc.image.registry import get_img_labels, get_img_refs, get_oci_client, get_repo_tags


class ClassEncoding(str, Enum):
    """Types of class encodings"""

    ONE_HOT = "one_hot"
    CATEGORICAL = "categorical"
    PROBABILITIES = "probabilities"


C = TypeVar("C", bound="ClassData")


@dataclass
class ClassData(Data):
    """Multi-class data"""

    data: NDArray
    """The image data as an NDArray"""

    num_classes: int
    """Number of possible classes"""

    size: int
    """Size of the batch i.e. number of individual clasisfications"""

    encoding: ClassEncoding
    """The way the class data is encoded"""

    names: Optional[List[str]] = None
    """Names of the classes"""

    def __add__(self, s: ClassData) -> ClassData:
        if s.encoding != self.encoding:
            raise ValueError("cannot add class datas of two different encoding types")

        if self.num_classes != s.num_classes:
            raise ValueError("cannot add class datas with different number of classes")

        if self.names != s.names:
            raise ValueError("cannot add class datas of with different `names` attributes")

        return ClassData(
            np.concatenate((self.data, s.data)),
            self.num_classes,
            self.size + self.size,
            encoding=self.encoding,
            names=self.names,
        )

    @classmethod
    def short_name(self) -> str:
        """Short name for the data

        Returns:
            str: The short name
        """
        return "cls"

    def as_ndarray(self) -> NDArray:
        """Image data as an NDArray

        Returns:
            NDArray: An NDArray of image data
        """
        return self.data

    def as_one_hot(self) -> ClassData:
        """Class data as an one hot encoded NDArray

        Returns:
            ClassData: ClassData as one hot encoding
        """
        if self.encoding == ClassEncoding.ONE_HOT:
            return self
        elif self.encoding == ClassEncoding.CATEGORICAL:
            x = np.zeros((self.data.size, self.num_classes))
            x[np.arange(self.data.size), self.data] = 1
            return ClassData(x, self.num_classes, self.size, ClassEncoding.ONE_HOT, names=self.names)
        else:
            raise ValueError(f"enoding type not supported {self.encoding}")

    def as_categorical(self) -> ClassData:
        """Class data as an one hot encoded NDArray

        Returns:
            ClassData: A one hot encoded NDArray
        """
        if self.encoding == ClassEncoding.CATEGORICAL:
            return self
        x = self.data.argmax(1)
        return ClassData(x, self.num_classes, self.size, ClassEncoding.CATEGORICAL, names=self.names)

    def repr_json(self) -> Dict[str, Any]:
        """Convert object to a JSON serializable dict

        Returns:
            Dict[str, Any]: A JSON serializable dict
        """
        d = self.__dict__
        d["data"] = self.data.tolist()
        return d

    @classmethod
    def load_dict(cls: Type[ClassData], data: Dict[str, Any]) -> ClassData:
        """Load object from JSON

        Args:
            cls (Type[ClassData]): the ClassData class
            data (Dict[str, Any]): the dict to create from

        Returns:
            ClassData: A ClassData object
        """
        data["data"] = np.asarray(data["data"])
        return cls(**data)

    @classmethod
    def score_cls(cls: Type[ClassData]) -> Type["ClassDataScore"]:
        return ClassDataScore


@dataclass
class ClassDataReport(EvalReport):
    """A report for Class Data"""

    model_uri: str
    job_uri: str

    num_classes: int
    confusion: NDArray
    fp: List[int]
    fn: List[int]
    tp: List[int]
    tn: List[int]
    f1: List[float]
    accuracy: List[float]
    recall: List[float]
    spcificity: List[float]
    precision: List[float]
    support: List[int]
    total_accuracy: float
    total_precision: float
    total_recall: float
    total_f1: float
    class_names: Optional[List[str]] = None
    timestamp: int = int(round(datetime.now().timestamp()))

    def __str__(self):
        names = self.class_names

        # handle this sometimes being a list
        if isinstance(self.confusion, list):
            confusion = np.array(self.confusion)
        else:
            confusion = self.confusion

        confuse_split = str(confusion).splitlines()

        # table = []
        # for i in range(len(confuse_split)):
        #     print("i: ", i)
        #     name = str(i)
        #     if names is not None:
        #         name = names[i]

        #     # hack printing of the confusion matrix
        #     confuse_row = confuse_split[i]
        #     if i == 0:
        #         confuse_row = confuse_row[1:]
        #     if i == len(confuse_split) - 1:
        #         confuse_row = confuse_row[:-1]

        #     table.append(
        #         [
        #             name,
        #             confuse_row,
        #             round(acc[i], 3),
        #             round(precision[i], 3),
        #             round(recall[i], 3),
        #             round(f1[i], 3),
        #             support[i],
        #         ]
        #     )
        # tab = tabulate(table, headers=["class", "confusion", "acc", "precision", "recall", "f1", "support"])
        # return (
        #     "\n\n"
        #     + tab
        #     + "\n\n"
        #     + f"total accuracy: {round(acc.mean(), 5)} \n"
        #     + f"total precision: {round(precision.mean(), 5)} \n"
        #     + f"total recall: {round(recall.mean(), 5)} \n"
        #     + f"total f1: {round(f1.mean(), 5)} \n"
        #     + "\n"
        # )

        table = []
        for i in range(len(confuse_split)):
            name = str(i)
            if names is not None:
                name = names[i]

            # hack printing of the confusion matrix
            confuse_row = confuse_split[i]
            if i == 0:
                confuse_row = confuse_row[1:]
            if i == len(confuse_split) - 1:
                confuse_row = confuse_row[:-1]

            table.append(
                [
                    name,
                    confuse_row,
                    round(self.accuracy[i], 3),
                    round(self.precision[i], 3),
                    round(self.recall[i], 3),
                    round(self.f1[i], 3),
                    self.support[i],
                ]
            )
        tab = tabulate(table, headers=["class", "confusion", "acc", "precision", "recall", "f1", "support"])
        s = (
            "\n\n"
            + f"report for model {self.model_uri}"
            + "\n\n"
            + tab
            + "\n\n"
            + f"total accuracy: {round(self.total_accuracy, 5)} \n"
            + f"total precision: {round(self.total_precision, 5)} \n"
            + f"total recall: {round(self.total_recall, 5)} \n"
            + f"total f1: {round(self.total_f1, 5)} \n"
            + "\n"
        )
        return s

    def repr_json(self) -> Dict[str, Any]:
        """Convert object to a JSON serializable dict

        Returns:
            Dict[str, Any]: A JSON serializable dict
        """
        d = self.__dict__
        if isinstance(d["confusion"], list):
            return d
        d["confusion"] = self.confusion.tolist()
        return d

    @classmethod
    def load_dict(cls: Type[ClassDataReport], data: Dict[str, Any]) -> ClassDataReport:
        """Load object from JSON

        Args:
            cls (Type[ClassData]): the ClassDataReport class
            data (Dict[str, Any]): the dict to create from

        Returns:
            ClassData: A ClassData object
        """
        if isinstance(data["confusion"], np.ndarray):
            data["confusion"] = np.asarray(data["confusion"])
        return cls(**data)

    @classmethod
    def load(cls: Type[ClassDataReport], uri: str) -> ClassDataReport:
        """Load object from URI

        Args:
            cls (Type[ClassDataReport]): the ClassDataReport class
            uri (str): URI to load

        Returns:
            ClassDataReport: A report
        """
        objs_dict = blobz.pull_str(uri)
        obj_dict = jsonpickle.decode(objs_dict[list(objs_dict.keys())[0]])
        return cls.load_dict(obj_dict)

    @classmethod
    def find(
        cls: Type[ClassDataReport], artifact_uri: Optional[str] = None, repositories: Optional[List[str]] = None
    ) -> List[ClassDataReport]:
        """Find all reports for a given URI

        Args:
            cls (Type[ClassDataReport]): the ClassDataReport class
            uri (str, optional): artifact URI to find reports for, this can be a model or a job
            repositories (List[str], optional): extra repositories to check

        Returns:
            List[ClassDataReport]: A list of reports
        """
        artifact: Optional[URI] = None
        if artifact_uri is not None:
            artifact = URI.parse(artifact_uri)

        if artifact_uri is None and repositories is None:
            raise ValueError("must provide one of artifact_uri or repositories")

        if repositories is None:
            if artifact is not None:
                repositories = [artifact.repo]

        else:
            exists = False
            for repo in repositories:
                if artifact is not None and repo == artifact.repo:
                    exists = True
            if not exists:
                if artifact is not None:
                    repositories.append(artifact.repo)

        if repositories is None:
            # TODO: use current repository
            raise ValueError("must provide repositories to search")

        ret = []
        for repo_uri in repositories:
            tags = get_repo_tags(repo_uri)

            for tag in tags:
                if "report" in tag:
                    if artifact is not None:
                        refs = get_img_refs(f"{repo_uri}:{tag}")
                        if artifact.artifact_type == "model" and MODEL_REF_LABEL in refs:
                            if refs[MODEL_REF_LABEL] == str(artifact):
                                ret.append(cls.load(f"{repo_uri}:{tag}"))
                        if artifact.artifact_type == "job" and JOB_REF_LABEL in refs:
                            if refs[JOB_REF_LABEL] == str(artifact):
                                ret.append(cls.load(f"{repo_uri}:{tag}"))
                    else:
                        ret.append(cls.load(f"{repo_uri}:{tag}"))
        return ret

    def store(self, repository: Optional[str] = None) -> None:
        """Store the report as an artifact

        Args:
            repository (Optional[str], optional): An optional reporitory to store the report. Defaults to the Config value.
        """

        if repository is None:
            repository = Config().image_repository
        artifact = URI.parse(self.model_uri)
        name = f"report-{artifact.name}-{self.timestamp}"
        uri = f"{repository}:{name}"

        # TODO: support multiple storage backends
        logging.info(f"storing report to uri {uri}")
        blobz.push(
            uri,
            obj=self.repr_json(),
            labels={OBJECT_TYPE_LABEL: type(self).__name__},
            refs={MODEL_REF_LABEL: self.model_uri, JOB_REF_LABEL: self.job_uri},
        )


class ClassDataScore(SupervisedScore[ClassData]):
    """A score for class data"""

    # https://stackoverflow.com/questions/50666091/true-positive-rate-and-false-positive-rate-tpr-fpr-for-multi-class-data-in-py
    # https://kawahara.ca/how-to-compute-truefalse-positives-and-truefalse-negatives-in-python-for-binary-classification-problems/

    # y_true: ClassData
    # y_pred: ClassData

    def __init__(self, y_true: ClassData, y_pred: ClassData):
        super().__init__(y_true, y_pred)

        if self.y_pred.encoding != self.y_true.encoding:
            raise ValueError("cannot score class datas of different encodings")
        if self.y_pred.size != self.y_true.size:
            raise ValueError("cannot score class datas of different sizes")
        if self.y_pred.num_classes != self.y_true.num_classes:
            raise ValueError("cannot score class datas with different number of classes")

    def confusion(self) -> NDArray:
        """Confusion matrix

        Returns:
            np.ndarray: Confusion matrix
        """
        return confusion_matrix(self.y_true.as_ndarray(), self.y_pred.as_ndarray())

    def fp(self) -> NDArray:
        """False positives

        Returns:
            int: Number of false positives
        """

        return self.confusion().sum(axis=0) - np.diag(self.confusion())

    def fn(self) -> NDArray:
        """False negatives

        Returns:
            int: Number of false negatives
        """

        return self.confusion().sum(axis=1) - np.diag(self.confusion())

    def tp(self) -> NDArray:
        """True positives

        Returns:
            int: Number of true positives
        """
        return np.diag(self.confusion())

    def tn(self) -> NDArray:
        """True negatives

        Returns:
            int: Number of true negatives
        """

        return self.confusion().sum() - (self.fp() + self.fn() + self.tp())

    def accuracy(self) -> NDArray:
        """Accuracy score (TP+TN)/(TP+FP+FN+TN)

        Returns:
            float: Accuracy score
        """

        acc = (self.tp() + self.tn()) / (self.tp() + self.fp() + self.fn() + self.tn())
        return acc

    def f1(self) -> NDArray:
        """F1 score TP / (TP + 1/2(FP + FN))

        Returns:
            float: F1 score
        """

        return self.tp() / (self.tp() + (1 / 2 * (self.fp() + self.fn())))

    def recall(self) -> NDArray:
        """Recall score TP/(TP+FN)

        Returns:
            float: Recall score
        """

        return self.tp() / (self.tp() + self.fn())

    def specificity(self) -> NDArray:
        """Specificity score TN/(TN+FP)

        Returns:
            float: Specificity score
        """

        return self.tn() / (self.tn() + self.fp())

    # TODO: LRU cache? or cache on init?
    def precision(self) -> NDArray:
        """Precision score TP/(TP+FP)

        Returns:
            float: Precision score
        """

        return self.tp() / (self.tp() + self.fp())

    def support(self) -> NDArray:
        """Support for each class

        Returns:
            NDArray: An NDArray of support by class
        """
        return self.confusion().sum(axis=1)

    def render(self) -> str:
        """Render the score

        Returns:
            str: HTML
        """
        raise NotImplementedError()

    def __str__(self):
        names = self.y_true.names
        acc = self.accuracy()
        precision = self.precision()
        recall = self.recall()
        f1 = self.f1()
        support = self.support()
        confusion = self.confusion()

        confuse_split = str(confusion).splitlines()

        table = []
        for i in range(len(confuse_split)):
            name = str(i)
            if names is not None:
                name = names[i]

            # hack printing of the confusion matrix
            confuse_row = confuse_split[i]
            if i == 0:
                confuse_row = confuse_row[1:]
            if i == len(confuse_split) - 1:
                confuse_row = confuse_row[:-1]

            table.append(
                [
                    name,
                    confuse_row,
                    round(acc[i], 3),
                    round(precision[i], 3),
                    round(recall[i], 3),
                    round(f1[i], 3),
                    support[i],
                ]
            )
        tab = tabulate(table, headers=["class", "confusion", "acc", "precision", "recall", "f1", "support"])
        return (
            "\n\n"
            + tab
            + "\n\n"
            + f"total accuracy: {round(acc.mean(), 5)} \n"
            + f"total precision: {round(precision.mean(), 5)} \n"
            + f"total recall: {round(recall.mean(), 5)} \n"
            + f"total f1: {round(f1.mean(), 5)} \n"
            + "\n"
        )

    def __add__(self, s: Optional["ClassDataScore"] = None) -> "ClassDataScore":
        if s is None:
            return self

        score = self.__class__(
            self.y_true + s.y_true,
            self.y_pred + s.y_pred,
        )
        return score

    @classmethod
    def report_cls(cls) -> Type[ClassDataReport]:
        return ClassDataReport

    def report(self, model_uri: str, job_uri: str) -> ClassDataReport:
        """Generate a report based on the score

        Returns:
            ClassDataReport: A ClassData Report
        """
        return ClassDataReport(
            model_uri=model_uri,
            job_uri=job_uri,
            num_classes=self.y_true.num_classes,
            confusion=self.confusion(),
            fp=self.fp().tolist(),
            fn=self.fn().tolist(),
            tp=self.tp().tolist(),
            tn=self.tn().tolist(),
            f1=self.f1().tolist(),
            accuracy=self.accuracy().tolist(),
            recall=self.recall().tolist(),
            spcificity=self.specificity().tolist(),
            precision=self.precision().tolist(),
            support=self.support().tolist(),
            total_accuracy=self.accuracy().mean(),
            total_precision=self.precision().mean(),
            total_recall=self.recall().mean(),
            total_f1=self.f1().mean(),
            class_names=self.y_true.names,
        )

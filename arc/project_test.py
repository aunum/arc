from arc.scm import SCM, obj_module_path
from arc.data.job import Job
from numpy import ndarray


def test_obj_module():
    assert obj_module_path(Job) == "arc.data.job"
    print(obj_module_path(ndarray))

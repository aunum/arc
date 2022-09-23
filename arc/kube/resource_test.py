from typing import Optional, ClassVar
import time
import logging
from dataclasses import dataclass
import pytest

from kubernetes.dynamic import DynamicClient

from arc.kube.resource import Resource, ObjectMeta, SchemaMixin
from arc.kube.client import default_dynamic_client


@dataclass
class FooSpec(SchemaMixin):
    """Spec of the Foo"""

    bar: str
    baz: int


@dataclass
class FooStatus(SchemaMixin):
    """Status of the Foo"""

    qux: Optional[bool] = None
    corge: Optional[float] = None


class Foo(Resource):
    """A Foo"""

    api_version: ClassVar[str] = "bar.baz/v1alpha1"
    meta: ObjectMeta
    spec: FooSpec
    status: FooStatus


def get_tmp_namespace(client: DynamicClient = None) -> str:
    """get a temporary namespace in the current cluster"""

    name = f"tmp-{int(time.time())}"
    logging.info(f"creating tmp namespace {name}")

    if client is None:
        client = default_dynamic_client()

    api = client.resources.get(api_version="v1", kind="Namespace")

    ns_manifest = {
        "kind": "Namespace",
        "apiVersion": "v1",
        "metadata": {
            "name": name,
        },
    }
    api.create(body=ns_manifest)
    logging.info(f"created namespace: {name}")

    return name


def del_namespace(name=str, client: DynamicClient = None):
    """delete a temporary namespace"""

    if client is None:
        client = default_dynamic_client()

    api = client.resources.get(api_version="v1", kind="Namespace")

    api.delete(name=name)
    logging.info(f"deleted namespace: {name}")


namespace = ""


@pytest.fixture(autouse=True)
def setup_test():
    global namespace
    namespace = get_tmp_namespace()

    yield

    del_namespace(namespace)


def test_resource():
    """test the Resource type"""

    # install Foo resource definition into the cluster
    Foo.ensure()

    # create Foos
    foo1 = Foo(meta=ObjectMeta(name="test1", namespace=namespace), spec=FooSpec("a", 1), status=FooStatus())
    foo2 = Foo(meta=ObjectMeta(name="test2", namespace=namespace), spec=FooSpec("b", 2), status=FooStatus())

    list_ = Foo.list(namespace=namespace)
    assert len(list_) == 0

    foo1.create(namespace=namespace)
    list_ = Foo.list(namespace=namespace)
    assert len(list_) == 1

    foo2.apply()
    list_ = Foo.list(namespace=namespace)
    assert len(list_) == 2

    # get the first Foo
    foo_got1 = Foo.get("test1", namespace)
    assert foo_got1.meta.name == foo1.meta.name
    assert foo_got1.spec == foo1.spec

    # get the second Foo
    foo_got2 = Foo.get("test2", namespace)
    assert foo_got2.meta.name == foo2.meta.name
    assert foo_got2.spec == foo2.spec

    # update a foo
    new_status = FooStatus(True, 0.1)
    foo_got1.status = new_status
    foo_got1.apply()
    foo_got1.load()

    assert foo_got1.status == new_status

    # delete Foos
    Foo.delete("test1", namespace)
    foo_got2.delete_(namespace=namespace)

    foo_list = Foo.list(namespace)
    assert len(foo_list) == 0

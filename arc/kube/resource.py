"""Simple CRDs from python classes"""

from typing import Dict, Any, Optional, List, Type, ClassVar, TypeVar
from dataclasses import dataclass
import logging
import time
import os
import json
from xml.dom import NotFoundErr

from kubernetes.dynamic import DynamicClient
from kubernetes.dynamic.resource import Resource as KubernetesResourceAPI
from kubernetes.client.rest import ApiException
from kubernetes.dynamic.exceptions import ResourceNotFoundError
import inflection
from dataclasses_jsonschema import JsonSchemaMixin
from dataclasses_jsonschema.type_defs import JsonDict, SchemaType
from dacite import from_dict


from arc.kube.client import default_dynamic_client


@dataclass
class GVK:
    """Group Version Kind"""

    group: str
    """API group e.g. foo.bar.com"""

    version: str
    """API version e.g. v1alpha1"""

    kind: str
    """Kind of resource"""

    def group_version(self) -> str:
        """group/version from the gvk e.g. foo.bar.com/v1alpha1

        Returns:
            str: A Kubernetes formatted group/version
        """
        return os.path.join(self.group, self.version)

    @classmethod
    def from_group_version(cls, gv: str, kind: str):
        """Create a GVK from a groupversion string and a kind

        Args:
            gv (str): A groupversion string
            kind (str): Kind of the Resource

        Returns:
            GVK: A GVK
        """
        group, version = cls.parse_group_version(gv)
        return cls(group=group, version=version, kind=kind)

    @classmethod
    def from_resource(cls, resource: Dict[str, Any]):
        """create a GVK from an existing resource

        Args:
            resource (Dict[str, Any]): a Kubernetes resource
        """
        group_version = resource["apiVersion"]
        group, version = cls.parse_group_version(group_version)
        return cls(group=group, version=version, kind=resource["kind"])

    @classmethod
    def parse_group_version(cls, gv: str) -> List[str]:
        """parse a groupversion string into a group and version

        Args:
            gv (str): A groupversion string

        Returns:
            List[str]: A group and a version
        """
        return gv.split("/")


# TODO: use kubernetes stubs?
@dataclass
class ObjectMeta:
    """Kubernetes object metadata"""

    name: str
    """Name of the resource"""

    namespace: Optional[str] = None
    """Namespace of the resource"""

    labels: Optional[Dict[str, str]] = None
    """labels for the resource"""

    annotations: Optional[Dict[str, str]] = None
    """annotations of the resource"""

    _generation: Optional[str] = None
    """generation of the resource"""


@dataclass
class AttrType:
    """A container for a mapping of attribute name to type"""

    attr_name: str
    """name of the class attribute"""

    type_: Type
    """type of the attribute"""


class ResourceMetaClass(type):
    """ResourceMetaClass checks that the standard fields are implemented for a Resource"""

    def __init__(cls, name, bases, attrs):
        required = [
            AttrType("api_version", ClassVar[str]),
            AttrType("meta", ObjectMeta),
            AttrType("spec", JsonSchemaMixin),
            AttrType("status", JsonSchemaMixin),
        ]
        missing_attrs = [
            attr_type
            for attr_type in required
            if attr_type.attr_name not in cls.__annotations__  # and not isinstance(cls, attr_type.type_)
        ]
        if missing_attrs:
            raise AttributeError(f"class {cls.__name__} requires attributes {missing_attrs}")


class SchemaMixin(JsonSchemaMixin):
    """SchemaMixin provides json schema functionality to classes"""

    @classmethod
    def schema(cls) -> JsonDict:
        """Generate schema for the given class in a Kubernetes complaint manner

        Returns:
            JsonDict: A dictionary of the schema
        """
        schema = cls.json_schema(schema_type=SchemaType.DRAFT_06)
        del schema["$schema"]
        return schema


T = TypeVar("T", bound="Resource")


@dataclass
class Resource(metaclass=ResourceMetaClass):
    """A Kubernetes resource"""

    api_version: ClassVar[str]
    """API version of the resource e.g. foo.bar/v1alpha1"""

    meta: ObjectMeta
    """Object metadata"""

    spec: SchemaMixin
    """spec of the resource"""

    status: SchemaMixin
    """status of the resource"""

    @classmethod
    def gvk(cls) -> GVK:
        """Group Version Kind for the resource

        Returns:
            GVK: Group Version Kind for the resource
        """

        return GVK.from_group_version(cls.api_version, cls.__name__)

    @classmethod
    def ensure(cls, client: DynamicClient = None) -> None:
        """Ensure the resource exists in the Kubernetes cluster

        Args:
            client (DynamicClient, optional): client to use. Defaults to None.
        """

        if client is None:
            client = default_dynamic_client()

        _crd_api = client.resources.get(
            api_version="apiextensions.k8s.io/v1",
            kind="CustomResourceDefinition",
        )
        _crd_api.get()
        manifest = cls.manifest()
        body = json.dumps(manifest)

        crd_creation_response = _crd_api.server_side_apply(
            body=body, name=manifest["metadata"]["name"], field_manager="klassy"
        )
        logging.info(f"crd creation response: {crd_creation_response}")

        cls.get_api(client)

    @classmethod
    def get_api(cls, client: DynamicClient) -> KubernetesResourceAPI:
        """Get the API for this resource

        Args:
            client (DynamicClient): client to use

        Returns:
            KubernetesResourceAPI: An API for the resource
        """

        try:
            client.resources.get(api_version=cls.gvk().group_version(), kind=cls.gvk().kind)
        except ResourceNotFoundError:
            logging.info("still waiting for resource to come online...")
            time.sleep(2)

        cr_api = client.resources.get(api_version=cls.gvk().group_version(), kind=cls.gvk().kind)
        return cr_api

    @classmethod
    def manifest(cls) -> Dict[str, Any]:
        """Generate the CRD manifest for this Resource

        Returns:
            Dict[str, Any]: The CRD manifest as a Kubernetes object
        """

        plural = inflection.pluralize(cls.__name__).lower()

        _manifest = {
            "apiVersion": "apiextensions.k8s.io/v1",
            "kind": "CustomResourceDefinition",
            "metadata": {
                "name": f"{plural}.{cls.gvk().group}",
            },
            "spec": {
                "group": f"{cls.gvk().group}",
                "versions": [
                    {
                        "name": f"{cls.gvk().version}",
                        "schema": {
                            "openAPIV3Schema": {
                                "properties": {
                                    "spec": cls.__annotations__["spec"].schema(),
                                    "status": cls.__annotations__["status"].schema(),
                                },
                                "type": "object",
                            }
                        },
                        "served": True,
                        "storage": True,
                    }
                ],
                "scope": "Namespaced",  # TODO
                "names": {
                    "plural": plural,
                    "listKind": f"{cls.__name__}List",
                    "singular": cls.__name__.lower(),
                    "kind": cls.__name__,
                },
            },
        }
        return _manifest

    @classmethod
    def from_resource(cls, resource: Dict[str, Any]):
        """Create a Resource object from a Kubernetes Resource

        Args:
            resource (Dict[str, Any]): a Kubernetes resource

        Returns:
            [type]: A Resource object
        """
        ret = cls(
            meta=ObjectMeta(
                name=resource["metadata"]["name"],
                namespace=resource["metadata"]["namespace"],
                labels=resource["metadata"]["labels"],
                annotations=resource["metadata"]["annotations"],
                _generation=resource["metadata"]["generation"],
            ),
            spec=from_dict(data_class=cls.__annotations__["spec"], data=resource["spec"]),
            status=cls.__annotations__["status"](),
        )
        if "status" in resource:
            cls.status = from_dict(data_class=cls.__annotations__["status"], data=resource["status"])
        return ret

    def resource(self) -> Dict[str, Any]:
        """API resource definition for current object

        Returns:
            Dict[str, Any]: A dictionary representation of the Kubernetes object
        """

        _resource = {
            "apiVersion": self.gvk().group_version(),
            "kind": self.gvk().kind,
            "metadata": {"name": self.meta.name, "namespace": self.meta.namespace},
            "spec": self.spec.to_dict(),
        }
        return _resource

    @classmethod
    def get(
        cls: Type[T],
        name: str,
        namespace: Optional[str] = None,
        client: DynamicClient = None,
    ) -> T:
        """Get a resource

        Args:
            name (str): Name to get
            namespace (Optional[str], optional): namespace to use. Defaults to None.
            client (DynamicClient, optional): client to use. Defaults to None.

        Raises:
            NotFoundErr: [description]

        Returns:
            T: [description]
        """

        if client is None:
            client = default_dynamic_client()

        api = cls.get_api(client)

        _list = api.get(name=name, namespace=namespace)

        if _list is None:
            raise NotFoundErr(f"resource not found: {cls.gvk().group_version()}/{namespace}/{name}")
        return cls.from_resource(_list.__dict__["attributes"])

    @classmethod
    def list(
        cls: Type[T],
        namespace: Optional[str] = None,
        client: DynamicClient = None,
    ) -> List[T]:
        """list resources

        Args:
            namespace (Optional[str], optional): namespace to list in. Defaults to None.
            client (DynamicClient, optional): client to use. Defaults to None.

        Returns:
            List[T]: [description]
        """

        if client is None:
            client = default_dynamic_client()

        api = cls.get_api(client)
        _list = api.get(namespace=namespace)

        ret: List[T] = []
        if _list is None:
            return ret

        if not hasattr(_list, "items"):
            ret.append(cls.from_resource(_list.__dict__["attributes"]))
            return ret

        for item in _list.items:
            ret.append(cls.from_resource(item))
        return ret

    def create(
        self,
        namespace: Optional[str] = None,
        client: DynamicClient = None,
    ) -> None:
        """create resource

        Args:
            namespace (Optional[str], optional): namespace to create in. Defaults to None.
            client (DynamicClient, optional): client to use. Defaults to None.
        """
        if client is None:
            client = default_dynamic_client()

        if namespace is not None:
            self.meta.namespace = namespace

        api = self.get_api(client)
        resource = self.resource()

        api.create(body=resource, namespace=self.meta.namespace)
        return

    def apply(
        self,
        namespace: Optional[str] = None,
        client: DynamicClient = None,
    ) -> None:
        """Apply resource

        Args:
            namespace (Optional[str], optional): namespace to apply to. Defaults to None.
            client (DynamicClient, optional): client to use. Defaults to None.
        """

        if client is None:
            client = default_dynamic_client()

        if namespace is not None:
            self.meta.namespace = namespace

        api = self.get_api(client)
        resource = self.resource()

        exists = False

        try:
            api.get(name=self.meta.name, namespace=self.meta.namespace)
            exists = True
        except ApiException:
            exists = False

        if not exists:
            api.create(body=resource, namespace=self.meta.namespace)
            return

        api.patch(
            body=resource,
            name=self.meta.name,
            namespace=self.meta.namespace,
            content_type="application/merge-patch+json",
        )
        return

    @classmethod
    def delete(cls: Type[T], name: str, namespace: str, client: DynamicClient = None) -> None:
        """delete a resource

        Args:
            name (str): name of the resource
            namespace (str): namespace of the resource
            client (dynamic.DynamicClient, optional): client to use. Defaults to None.
        """

        if client is None:
            client = default_dynamic_client()

        api = cls.get_api(client)

        api.delete(name=name, namespace=namespace)
        return

    def delete_(self, namespace: Optional[str], client: DynamicClient = None) -> None:
        """delete the current object

        Args:
            namespace (Optional[str]): namespace of the object; if not present in object
            client (DynamicClient, optional): client to use. Defaults to None.

        Raises:
            ValueError: if no namespace is given and isn't present in object
        """

        if namespace is None:
            namespace = self.meta.namespace
        if namespace is None:
            raise ValueError("no namespace parameter was given and objectmeta namespace is empty")

        return self.delete(self.meta.name, namespace, client)

    def load(self, namespace: Optional[str] = None, client: DynamicClient = None) -> None:
        """get the remote state of the current object and update the local one

        Args:
            namespace (Optional[str]): namespace of the object; if not present in object
            client (DynamicClient, optional): client to use. Defaults to None.
        """

        if namespace is None:
            namespace = self.meta.namespace
        resource = self.get(self.meta.name, self.meta.namespace, client)
        self = resource
        return

    def unique_id(self) -> str:
        """Unique id of the object (namespace + name + generation)

        Returns:
            str: uniqued id of the object (namespace + name + generation)
        """
        return f"{self.meta.namespace}={self.meta.name}={self.meta._generation}"

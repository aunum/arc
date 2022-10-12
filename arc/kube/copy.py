from typing import Optional
import uuid

from kubernetes import config
from kubernetes.client.models import (
    V1Pod,
    V1PodSpec,
)
from kubernetes.client import CoreV1Api, V1ObjectMeta

from arc.kube.env import is_k8s_proc


def copy_pod(name: str, namespace: str, core_v1_api: Optional[CoreV1Api] = None) -> V1Pod:
    """Create a copy of an existing pod

    Args:
        name (str): Name of the pod
        namespace (str): Namespace of the pod
        core_v1_api (Optional[CoreV1Api], optional): Optional CoreV1Api to use. Defaults to None.

    Returns:
        V1Pod: A copy of the pod
    """
    if core_v1_api is None:
        if is_k8s_proc():
            config.load_incluster_config()
        else:
            config.load_kube_config()

        core_v1_api = CoreV1Api()

    pod: V1Pod = core_v1_api.read_namespaced_pod(name, namespace)

    pod_name_split = str(pod.metadata.name).split("-")
    n = pod_name_split[:-1]

    uid = str(uuid.uuid4())
    n.append(uid[:5])
    pod_name = "-".join(n)

    spec: V1PodSpec = pod.spec
    spec.ephemeral_containers = None

    return V1Pod(
        metadata=V1ObjectMeta(
            annotations=pod.metadata.annotations,
            labels=pod.metadata.labels,
            name=pod_name,
            namespace=pod.metadata.namespace,
        ),
        spec=pod.spec,
    )

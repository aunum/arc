from kubernetes import config
from kubernetes.dynamic import DynamicClient
from kubernetes.client import api_client


def default_dynamic_client() -> DynamicClient:
    """default DynamicClient"""

    config.load_kube_config()
    client = DynamicClient(api_client.ApiClient(configuration=config.load_kube_config()))
    return client

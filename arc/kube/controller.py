from dataclasses import dataclass
from typing import TypeVar, Callable, Dict, Generic, Type
import logging
import time

from arc.kube.resource import Resource


@dataclass
class ControllerOpts:
    """Options for controllers"""

    namespace: str
    """namespace of the controller"""

    sleep: int = 1
    """time to sleep between reconciliation"""


Resource_contra = TypeVar("Resource_contra", bound=Resource)


class Controller(Generic[Resource_contra]):
    """A very rudimentary implementation of a Kubernetes controller"""

    opts: ControllerOpts
    """Options for the controller"""

    _resource_type: Type[Resource_contra]
    _cache: Dict[str, str] = {}

    def __init__(self, opts: ControllerOpts) -> None:
        """A very rudimentary Kubernetes controller

        Args:
            opts (ControllerOpts): options for the controller
        """
        self.opts = opts

    def run(self, reconcile: Callable[[Resource_contra], None]) -> None:
        """Run the reconciler

        Args:
            reconcile (Callable[[Resource], None]): reconciler function
        """
        while True:
            _list = self._resource_type.list(self.opts.namespace)
            for _resource in _list:
                if _resource.unique_id() not in self._cache:
                    try:
                        logging.info(f"reconciling resource: {_resource}")
                        reconcile(_resource)
                    except Exception as e:
                        logging.error(f"trouble reconciling: {e}")
                        continue
                    self._cache[_resource.unique_id()] = ""
            time.sleep(self.opts.sleep)

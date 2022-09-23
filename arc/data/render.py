from abc import ABC, abstractmethod


HTML = str


# Should this use python WASM, or a python micro-frontend?
class Renderable(ABC):
    """A renderable mixin"""

    @abstractmethod
    def render(self) -> HTML:
        pass

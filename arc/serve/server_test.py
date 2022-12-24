from __future__ import barry_as_FLUFL
from typing import Iterator, List, Type
from urllib import request
import json
import logging
import importlib

from starlette.responses import JSONResponse
from starlette.routing import Route

from arc.serve.server import Client, Server

logging.basicConfig(level=logging.INFO)


class Foo(Server):
    """A Foo"""

    pass


class Bar(Server):
    """A Bar"""

    a: str
    b: int

    def __init__(self, a: str, b: int) -> None:
        self.a = a
        self.b = b

    # @classmethod
    # def client_cls(cls) -> Type[Client]:
    #     """Class of the client for the server

    #     Returns:
    #         Type[Client]: A client class for the server
    #     """
    #     return BarClient

    # def routes(self) -> List[Route]:
    #     """Routes to add to the server

    #     Returns:
    #         List[Route]: List of routes to add to the server
    #     """
    #     base_routes = super().routes()
    #     base_routes.extend(
    #         [
    #             Route("/echo", endpoint=self._echo_req),
    #         ]
    #     )
    #     return base_routes

    # async def _echo_req(self, request):
    #     jdict = await request.json()
    #     return JSONResponse({"message": self.echo(jdict["txt"])})

    def echo(self, txt: str) -> str:
        """Echo a string back

        Args:
            txt (str): String to echo

        Returns:
            str: String echoed with a hello
        """
        return txt + " -- hello! " + "a: " + self.a + "b: " + str(self.b)

    def add(self, x: int, y: int) -> int:
        """Add x to y

        Args:
            x (int): Number
            y (int): Number

        Returns:
            int: Sum
        """
        return x + y

    def set(self, a: str, b: int) -> None:
        """Set the params

        Args:
            a (str): A string
            b (int): An int
        """
        self.a = a
        self.b = b

    def stream(self, a: str, num: int) -> Iterator[str]:
        """Stream back the string for the given number of times

        Args:
            a (str): String to stream
            num (int): Number of times to return

        Yields:
            Iterator[str]: An iterator
        """
        for i in range(num):
            yield f"{i}: {a}"

    def __dir__(self):
        return super().__dir__() + [str(k) for k in self.keys()]


class BarClient(Client):
    """A Bar client"""

    # def echo(self, txt: str) -> str:
    #     """Echo the message

    #     Args:
    #         txt (str): Message to echo

    #     Returns:
    #         str: Echoed message with a hello
    #     """
    #     params = json.dumps({"txt": txt}).encode("utf8")
    #     req = request.Request(f"{self.server_addr}/echo", data=params, headers={"content-type": "application/json"})
    #     resp = request.urlopen(req)
    #     data = resp.read().decode("utf-8")
    #     dict = json.loads(data)
    #     return dict["message"]


if __name__ == "__main__":
    foo = Foo()

    foo_cli = foo.develop(clean=False)

    print("foo info: ", foo_cli.info())
    print("foo labels: ", foo_cli.labels())
    print("foo health: ", foo_cli.health())

    foo2 = Foo()

    bar = Bar(a="ipsum", b=5)

    bar_cli = bar.develop(clean=False)

    print("bar info: ", bar_cli.info())
    print("bar echo: ", bar_cli.echo("yellow"))

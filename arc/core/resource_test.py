from typing import Iterator
import logging

from arc.core.resource import Resource

logging.basicConfig(level=logging.INFO)


class Foo(Resource):
    """A Foo"""

    def test(self) -> None:
        """A test function"""
        print("hello")


class Bar(Resource):
    """A Bar"""

    a: str
    b: int

    def __init__(self, a: str, b: int) -> None:
        """A Bar resource

        Args:
            a (str): A string
            b (int): An int
        """
        self.a = a
        self.b = b

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


def test_foo_object():
    FooClient = Foo.client(hot=True, dev_dependencies=True)

    # Create a remote instance
    print("creating foo")
    foo = FooClient()

    print("foo info: ", foo.info())
    print("foo labels: ", foo.labels())
    print("foo health: ", foo.health())
    print("foo test: ", foo.test())

    print("creating foo 2")
    foo2 = FooClient()

    print("foo2 info: ", foo2.info())
    print("foo2 labels: ", foo2.labels())

    print("deleting foo")
    foo.delete()

    print("foo2 health: ", foo2.health())
    print("foo2 test: ", foo2.test())

    print("delete foo2")
    foo2.delete()


def test_bar_object():
    # Create a Bar client class with the given options
    print("creating bar")
    BarClient = Bar.client(hot=False, dev_dependencies=True, clean=False)

    # Create a remote Bar instance with the given parameters
    bar_client = BarClient("baz", 1)

    print("bar info: ", bar_client.info())
    assert bar_client.echo("yellow") == "yellow" + " -- hello! " + "a: " + "baz" + "b: " + str(1)
    assert bar_client.add(1, 3) == 4
    bar_client.set("qoz", 5)
    assert bar_client.echo("yellow") == "yellow" + " -- hello! " + "a: " + "qoz" + "b: " + str(5)
    bar_client.delete()

    print("creating bar2")
    bar_client2 = Bar.client(dev_dependencies=True)("qux", 2)

    print("bar2 info: ", bar_client2.info())
    print("bar2 echo blue: ", bar_client2.echo("blue"))
    assert bar_client2.echo("blue") == "blue" + " -- hello! " + "a: " + "qux" + "b: " + str(2)
    bar_client2.delete()


def test_stream():
    BarClient = Bar.client(dev_dependencies=True, clean=False)

    with BarClient("zoop", 6) as bar:
        for i, s in enumerate(bar.stream("test", 10)):
            assert s == f"{i}: test"


if __name__ == "__main__":
    print("testing foo")
    test_foo_object()

    print("testing bar")
    test_bar_object()

    print("testing stream")
    test_stream()

from typing import Iterator, Union, Dict, Any, List, Optional
import logging

from arc.core.resource import Resource
from arc.scm import SCM
from arc.core.test.bar import Baz, Spam

logging.basicConfig(level=logging.INFO)


class Ham:
    a: str
    b: int

    def __init__(self, a: str, b: int) -> None:
        """A Ham resource

        Args:
            a (str): A string
            b (int): An int
        """
        self.a = a
        self.b = b


class Foo(Resource):
    """A simple Foo"""

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
        return txt + " -- hello! " + "a: " + self.a + " b: " + str(self.b)

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

    def bake_hams(self, ham_by_name: Dict[str, Ham]) -> Dict[str, Ham]:
        """Bake the given hams

        Args:
            ham_by_name (Dict[str, Ham]): A map of Ham to name

        Returns:
            Dict[str, bool]: Whether the Hams were baked
        """
        ret: Dict[str, Ham] = {}
        for name, ham in ham_by_name.items():
            ret[name] = ham

        return ret


def test_simple_create():
    scm = SCM()

    FooClient = Foo.client(hot=True, dev_dependencies=True)

    # Create a remote instance
    print("creating foo")
    foo = FooClient()

    info = foo.info()
    print("foo info: ", info)
    assert info["name"] == "Foo"
    assert info["version"] == scm.sha()
    assert info["env-sha"] == scm.env_sha()

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


def test_basic_ops():
    # Create a Bar client class with the given options
    print("creating bar")
    BarClient = Bar.client(hot=False, dev_dependencies=True, clean=False)

    # Create a remote Bar instance with the given parameters
    bar_client = BarClient("baz", 1)

    print("bar info: ", bar_client.info())
    assert bar_client.echo("yellow") == "yellow" + " -- hello! " + "a: " + "baz" + " b: " + str(1)
    assert bar_client.add(1, 3) == 4
    bar_client.set("qoz", 5)
    assert bar_client.echo("yellow") == "yellow" + " -- hello! " + "a: " + "qoz" + " b: " + str(5)
    hams = bar_client.bake_hams({"charles": Ham("baz", 1), "yanni": Ham("foo", 2)})
    assert hams["charles"].__dict__ == Ham("baz", 1).__dict__
    assert hams["yanni"].__dict__ == Ham("foo", 2).__dict__
    bar_client.delete()

    print("creating bar2")
    bar_client2 = Bar.client(dev_dependencies=True)("qux", 2)

    print("bar2 info: ", bar_client2.info())
    print("bar2 echo blue: ", bar_client2.echo("blue"))
    assert bar_client2.echo("blue") == "blue" + " -- hello! " + "a: " + "qux" + " b: " + str(2)
    bar_client2.delete()


def test_stream():
    BarClient = Bar.client(dev_dependencies=True, clean=False)

    with BarClient("zoop", 6) as bar:
        for i, s in enumerate(bar.stream("test", 10)):
            assert s == f"{i}: test"


def test_save():
    BarClient = Bar.client(dev_dependencies=True, clean=False)

    print("creating and storing client")
    bar = BarClient("zoop", 6)
    bar.set("spam", 4)
    uri = bar.store()
    bar.delete()

    print("loading saved object from uri: ", uri)
    bar2 = Bar.from_uri(uri)
    msg = bar2.echo("eggs")
    print("echo msg: ", msg)
    assert msg == "eggs" + " -- hello! " + "a: " + "spam" + " b: " + str(4)
    bar2.delete()


def test_lock():
    BarClient = Bar.client(dev_dependencies=True, clean=False)

    print("creating and storing client")
    bar = BarClient("zoop", 6)
    bar.set("spam", 4)
    proc_uri = bar.process_uri
    info = bar.info()
    print("bar info: ", info)

    assert info["locked"] is False
    print("locking bar")
    bar.lock()
    info = bar.info()
    print("new bar info: ", info)
    assert info["locked"] is True
    assert bar.set("eggs", 3) is None

    print("Trying to connect to locked process: ", proc_uri)
    BarClient2 = Bar.client(uri=proc_uri)
    bar2 = BarClient2("ham", 6)
    assert bar2.health() == {"health": "ok"}
    info = bar2.info()
    print("bar2 info: ", info)
    assert info["locked"] is True

    try:
        bar.set("spam", 11)
        assert False
    except Exception:
        assert True

    bar.delete()
    bar2.delete()


def test_copy():
    BarClient = Bar.client(dev_dependencies=True, clean=False)

    print("creating client")
    bar = BarClient("ham", 6)
    bar.set("spam", 4)

    bar2 = bar.copy()
    msg = bar2.echo("eggs")
    print("copied msg: ", msg)
    assert msg == "eggs" + " -- hello! " + "a: " + "spam" + " b: " + str(4)

    bar.delete()
    bar2.delete()


def test_nested():
    scm = SCM()

    BazClient = Baz.client(dev_dependencies=True, clean=False)
    # Create a remote instance
    print("creating baz")
    baz = BazClient()

    info = baz.info()
    print("baz info: ", info)
    assert info["name"] == "Baz"
    assert info["version"] == scm.sha()
    assert info["env-sha"] == scm.env_sha()

    assert baz.ret("echoing back!", Spam("this", 2)) == "echoing back!"

    baz.delete()


class LotsOfUnions(Resource):
    """A Resource with lots of unions"""

    a: str
    b: List[str]
    c: bool

    def __init__(self, a: Union[str, int], b: Union[Dict[str, Any], List[str]], c: Optional[bool] = None) -> None:
        """A LotsOfUnions resource

        Args:
            a (Union[str, int]): An a
            b (Union[Dict[str, Any], List[str]]): A b
            c (Optional[bool], optional): A c. Defaults to None.
        """
        self.a = str(a)

        if isinstance(b, dict):
            b = list(b.keys())
        self.b = b

        if c is None:
            c = False
        self.c = c

    def echo(self, txt: Optional[str] = None) -> str:
        """Echo a string back

        Args:
            txt (str): String to echo

        Returns:
            str: String echoed with a hello
        """
        if txt is None:
            txt = "klaus"

        return txt + " -- hello! " + "a: " + self.a + " c: " + str(self.c)

    def returns_optional(self, a: Union[str, int]) -> Optional[str]:
        """Optionally returns the given string or returns None if int

        Args:
            a (Union[str, int]): A string or int

        Returns:
            Optional[str]: An optional string
        """
        if isinstance(a, int):
            return None
        else:
            return a

    def optional_obj(
        self, h: Union[Ham, Dict[str, Any]], return_dict: Optional[bool] = None
    ) -> Union[Ham, Dict[str, Any]]:
        """Receives either a Ham or a dictionary and optionally returns a ham

        Args:
            h (Union[Ham, Dict[str, Any]]): A Ham or a dictionary of Ham

        Returns:
            Union[Ham, Dict[str, Any]]: A Ham or nothing
        """
        if isinstance(h, dict):
            h = Ham(h["a"], h["b"])

        if return_dict:
            print("returning dictionary")
            ret = h.__dict__
            ret["c"] = True
            return ret

        print("not returning dictionary")
        return h

    def optional_lists(
        self, y: Union[List[Ham], Dict[str, Ham]], as_dict: bool = True
    ) -> Union[List[Ham], Dict[str, Ham]]:
        """Recieves lists and dictionaries of Ham

        Args:
            y (Union[List[Ham], Dict[str, Ham]]): A list or dictionary of Ham
            as_dict (bool, optional): Return as a dicdtionary. Defaults to True.

        Returns:
            Union[List[Ham], Dict[str, Ham]]: A list or a dictionary of Ham
        """
        if as_dict and type(y) == list:
            ret: Dict[str, Ham] = {}
            for i, v in enumerate(y):
                ret[str(i)] = v

            return ret
        return y


def test_union():
    LouClient = LotsOfUnions.client(dev_dependencies=True, clean=False)

    print("=== testing echo")
    lou = LouClient(1, {"this": "that", "then": "there"}, True)
    msg = lou.echo("spam")
    print("msg1: ", msg)
    assert msg == "spam" + " -- hello! " + "a: " + "1" + " c: " + "True"

    msg = lou.echo()
    print("msg2: ", msg)
    assert msg == "klaus" + " -- hello! " + "a: " + "1" + " c: " + "True"

    assert lou.returns_optional("eggs") == "eggs"
    assert lou.returns_optional(1) is None

    print("=== testing optional object")
    a = lou.optional_obj(Ham("foo", 4))
    print("a: ", a.__dict__)
    assert a.__dict__ == Ham("foo", 4).__dict__

    b = lou.optional_obj(Ham("bar", 5), True)
    print("b: ", b)
    assert b == {"a": "bar", "b": 5, "c": True}

    c = lou.optional_obj({"a": "baz", "b": 6})
    print("c: ", c.__dict__)
    assert c.__dict__ == Ham("baz", 6)

    print("=== testing optional lists")
    d = lou.optional_lists([Ham("a", 1), Ham("b", 2)], False)
    print("d: ", d)
    assert type(d) == list
    assert d[0].__dict__ == Ham("a", 1).__dict__
    assert d[1].__dict__ == Ham("b", 2).__dict__

    e = lou.optional_lists({"ham1": Ham("c", 3), "ham2": Ham("d", 4)})
    print("e: ", e)
    assert type(e) == dict
    assert e["ham1"].__dict__ == Ham("c", 3).__dict__
    assert e["ham2"].__dict__ == Ham("d", 4).__dict__

    f = lou.optional_lists([Ham("a", 1), Ham("b", 2)])
    print("f: ", f)
    assert type(f) == dict
    assert f["0"].__dict__ == Ham("a", 1).__dict__
    assert f["1"].__dict__ == Ham("b", 2).__dict__

    lou.delete()


def test_tuple():
    pass


def test_dataclass():
    pass


def test_enum():
    pass


def test_find():
    pass


def test_logs():
    pass


def test_resources():
    pass


def test_notebook():
    pass


def test_numpy():
    pass


def test_pandas():
    pass


def test_arrow():
    pass


def test_tf():
    pass


def test_torch():
    pass


def test_source():
    pass


def test_diff():
    pass


def test_merge():
    pass


def test_sync():
    pass


def test_schema():
    pass


def test_generic():
    pass


def test_ui():
    pass


if __name__ == "__main__":
    # print("\n=====\ntesting simple create\n")
    # test_simple_create()

    print("\n=====\ntesting basic ops\n")
    test_basic_ops()

    # print("\n=====\ntesting stream\n")
    # test_stream()

    # print("\n=====\ntesting save\n")
    # test_save()

    # print("\n=====\ntesting lock\n")
    # test_lock()

    # print("\n=====\ntesting copy\n")
    # test_copy()

    # print("\n=====\ntesting nested\n")
    # test_nested()

    # print("\n=====\ntesting union\n")
    # test_union()

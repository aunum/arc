import sys
import typing


def get_orig_class(obj, default_to__class__=False):
    """Robust way to access `obj.__orig_class__`. Compared to a direct access this has the
    following advantages:
    1) It works around https://github.com/python/typing/issues/658.
    2) It prevents infinite recursion when wrapping a method (`obj` is `self` or `cls`) and either
       - the object's class defines `__getattribute__`
       or
       - the object has no `__orig_class__` attribute and the object's class defines `__getattr__`.
       See discussion at https://github.com/Stewori/pytypes/pull/53.
    If `default_to__class__` is `True` it returns `obj.__class__` as final fallback.
    Otherwise, `AttributeError` is raised  in failure case (default behavior).
    """
    # See https://github.com/Stewori/pytypes/pull/53:
    # Returns  `obj.__orig_class__` protecting from infinite recursion in `__getattr[ibute]__`
    # wrapped in a `checker_tp`.
    # (See `checker_tp` in `typechecker._typeinspect_func for context)
    # Necessary if:
    # - we're wrapping a method (`obj` is `self`/`cls`) and either
    #     - the object's class defines __getattribute__
    # or
    #     - the object doesn't have an `__orig_class__` attribute
    #       and the object's class defines __getattr__.
    # In such a situation, `parent_class = obj.__orig_class__`
    # would call `__getattr[ibute]__`. But that method is wrapped in a `checker_tp` too,
    # so then we'd go into the wrapped `__getattr[ibute]__` and do
    # `parent_class = obj.__orig_class__`, which would call `__getattr[ibute]__`
    # again, and so on. So to bypass `__getattr[ibute]__` we do this:
    return object.__getattribute__(obj, "__orig_class__")

from typing import Any
from pathlib import Path
import inspect
import rootpath
import os


def obj_module_path(obj: Any) -> str:
    """Get a module path for any given object"""

    # I need to check if the file is in the current project
    fp = Path(inspect.getfile(obj))
    rp = Path(rootpath.detect())

    local_path = str(fp.relative_to(rp))

    clean_path = os.path.splitext(local_path)[0]
    module_path = clean_path.replace("/", ".")
    return module_path

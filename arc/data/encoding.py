# import numpy as np
import json

# from arc.data.types import Data


# class JsonCustomEncoder(json.JSONEncoder):
#     """Special json encoder for numpy types"""

#     def default(self, obj):
#         if isinstance(obj, (np.ndarray, np.number)):
#             return obj.tolist()
#         elif isinstance(obj, (complex, np.complex)):
#             return [obj.real, obj.imag]
#         elif isinstance(obj, set):
#             return list(obj)
#         elif isinstance(obj, bytes):  # pragma: py3
#             return obj.decode()
#         elif isinstance(obj, Data):
#             return obj.__dict__
#         return json.JSONEncoder.default(self, obj)


class ShapeEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "repr_json"):
            return obj.repr_json()
        else:
            return json.JSONEncoder.default(self, obj)

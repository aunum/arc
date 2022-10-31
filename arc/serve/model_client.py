from urllib import request
import json
import logging

from arc.serve.server import Client
from typing import List
from typing import Any
from typing import Dict


class ModelClient(Client):
    def fit(self, x: List[int], y: List[int], opts: Dict[str, Any]) -> float:
        params = json.dumps({"x": x, "y": y, "opts": opts}).encode("utf8")
        req = request.Request(f"{self.server_addr}/fit", data=params, headers={"content-type": "application/json"})
        resp = request.urlopen(req)
        data = resp.read().decode("utf-8")
        jdict = json.loads(data)
        ret = jdict["response"]
        return ret

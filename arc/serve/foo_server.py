
import logging
import os

import uvicorn

from server_test import Foo
from server_test import *  # noqa: F403, F401

log_level = os.getenv("LOG_LEVEL")
if log_level is None:
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=log_level)

logging.info("creating object")
srv = Foo.create_from_env()

logging.info("creating app")
app = srv.server_app()

if __name__ == "__main__":
    pkgs = srv._reload_dirs()
    logging.info(f"starting server version '{srv.scm.sha()}' on port: 8080")
    uvicorn.run(
        "__main__:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        workers=1,
        reload=True,
        reload_dirs=pkgs.keys(),
    )

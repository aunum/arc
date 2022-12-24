# this file was generated by arc
FROM python:3.10.1
ENV PYTHONUNBUFFERED="1"
ENV PYTHONDONTWRITEBYTECODE="1"
ENV PIP_NO_CACHE_DIR="off"
ENV PIP_DISABLE_PIP_VERSION_CHECK="on"
ENV POETRY_NO_INTERACTION="1"
ENV PYTHONPATH="${PYTHONPATH}:/app:/app/"
RUN apt update && apt install -y watchdog
RUN pip install poetry==1.2.0 && poetry --version
WORKDIR /app/
COPY ./poetry.lock ./pyproject.toml /app/
RUN poetry install --no-ansi --no-root
COPY .git /app/.git/
EXPOSE 8000
COPY ["arc/core/bar_client.py", "arc/core/bar_server.py", "arc/core/client_builder.py", "arc/core/client_builder_test.py", "arc/core/foo.ipynb", "arc/core/foo_client.py", "arc/core/foo_server.py", "arc/core/resource.py", "arc/core/resource_test.py", "/app/arc/core/"]
COPY [".gitignore", ".pylintrc", ".python-version", "Dockerfile", "Dockerfile.arc", "LICENSE", "Makefile", "README.md", "poetry.lock", "pyproject.toml", "/app/"]
COPY ["arc/client.py", "arc/config.py", "arc/generic.py", "arc/kind.py", "arc/opts.py", "arc/project.py", "arc/project_test.py", "arc/scm.py", "arc/scm_test.py", "/app/arc/"]
COPY ["arc/cmd/root.py", "arc/cmd/run.py", "/app/arc/cmd/"]
COPY ["arc/data/cache.py", "arc/data/cache_test.py", "arc/data/classifydigitsjob_server.py", "arc/data/encoding.py", "arc/data/job.py", "arc/data/job_new.py", "arc/data/job_test.py", "arc/data/oci.py", "arc/data/oci_test.py", "arc/data/refs.py", "arc/data/render.py", "arc/data/types.py", "arc/data/util.py", "/app/arc/data/"]
COPY ["arc/data/shapes/classes.py", "arc/data/shapes/classes_test.py", "arc/data/shapes/image.py", "arc/data/shapes/labels.py", "arc/data/shapes/table.py", "arc/data/shapes/text.py", "arc/data/shapes/timeseries.py", "arc/data/shapes/video.py", "/app/arc/data/shapes/"]
COPY ["arc/image/build.py", "arc/image/build_test.py", "arc/image/client.py", "arc/image/file.py", "arc/image/file_test.py", "arc/image/id.py", "arc/image/registry.py", "/app/arc/image/"]
COPY ["arc/kube/apply.py", "arc/kube/auth_util.py", "arc/kube/client.py", "arc/kube/controller.py", "arc/kube/copy.py", "arc/kube/entrypoint.py", "arc/kube/env.py", "arc/kube/pod_util.py", "arc/kube/resource.py", "arc/kube/resource_test.py", "arc/kube/run.py", "arc/kube/run_test.py", "arc/kube/sync.py", "arc/kube/uri.py", "/app/arc/kube/"]
COPY ["arc/model/metrics.py", "arc/model/opts.py", "arc/model/predictor.py", "arc/model/router.py", "arc/model/trainer.py", "arc/model/trainer_server.py", "arc/model/trainer_test.py", "arc/model/types.ipynb", "arc/model/types.py", "arc/model/util.py", "/app/arc/model/"]
COPY ["arc/runtime/k8s.py", "/app/arc/runtime/"]
COPY ["arc/serve/bar_server.py", "arc/serve/foo_server.py", "arc/serve/model_client.py", "arc/serve/server.ipynb", "arc/serve/server.py", "arc/serve/server_test.py", "/app/arc/serve/"]
COPY ["arc/tune/tunable.py", "/app/arc/tune/"]
COPY ["arc/util/rootpath.py", "/app/arc/util/"]
COPY ["docs/artifacts.md", "docs/finder.md", "docs/functions.md", "docs/io.md", "docs/jobs.md", "docs/models.md", "docs/predictor.md", "docs/router.md", "docs/trainer.md", "/app/docs/"]
COPY ["examples/imdb/hf/README.md", "examples/imdb/hf/environment.yml", "/app/examples/imdb/hf/"]
COPY ["examples/mnist/job/.python-version", "examples/mnist/job/README.md", "examples/mnist/job/job.py", "examples/mnist/job/pyproject.toml", "/app/examples/mnist/job/"]
COPY ["examples/mnist/models/keras/.python-version", "examples/mnist/models/keras/README.md", "examples/mnist/models/keras/arc.yaml", "examples/mnist/models/keras/classifier.py", "examples/mnist/models/keras/convimgclassifier_server.py", "examples/mnist/models/keras/requirements.txt", "examples/mnist/models/keras/test.ipynb", "examples/mnist/models/keras/test.py", "/app/examples/mnist/models/keras/"]
COPY ["examples/mnist/models/torch/.env", "examples/mnist/models/torch/.python-version", "examples/mnist/models/torch/README.md", "examples/mnist/models/torch/classifier.py", "examples/mnist/models/torch/environment.yml", "/app/examples/mnist/models/torch/"]
COPY ["static/logo.png", "/app/static/"]
COPY .git /app/.git
CMD ["poetry", "run", "python", "/app/arc/core/bar_server.py"]
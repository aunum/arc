FROM python:3.10
ENV PYTHONUNBUFFERED="1"
ENV PYTHONDONTWRITEBYTECODE="1"
ENV PIP_NO_CACHE_DIR="off"
ENV PIP_DISABLE_PIP_VERSION_CHECK="on"
ENV POETRY_NO_INTERACTION="1"
ENV POETRY_VIRTUALENVS_CREATE="false"
RUN pip install poetry
RUN poetry --version
WORKDIR /app
COPY poetry.lock pyproject.toml /app/
RUN poetry install --no-ansi --no-dev
COPY . /app
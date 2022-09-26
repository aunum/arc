# Artifacts

Arc stores all ML artifacts as [OCI Artifacts](https://github.com/opencontainers/artifacts), this enables a user to only have to provide an image registry for their storage, and allows for simple sharing of artifacts.

Artifacts are stored with the following convention:

```
<registry>/<namespace>:<type>-<name>-<version>
```

A convolutional model at version v1:

```
aunum/arc:model-covnet-v1
```

The classify digits job at v1:

```
aunum/arc:job-classifydigits-v1
```

The repository Arc uses for its artifacts must be configured using:
* `$ARC_IMAGE_REPO` env var
* `tool.arc.image_repo` in pyproject.toml
* `image_repo` in arc.yaml
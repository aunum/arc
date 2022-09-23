class Artifact:
    @classmethod
    def load(self, uri: str) -> "Artifact":
        pass

    def store(self):
        pass

    def cp(self, a: str, b: str):
        pass


class RepositoryArtifact:
    pass


class ModelArtifact:
    pass


class DataArtifact:
    pass


# build an image from oci/s3/gs
# This needs to go a step further, we need to build an image that can be executable in certain ways
# Maybe we create a base class that does this? The annotation already basically does this, but how do we reference a
# method without taking on its dependencies?
# every class should have client/server, does this work with a supervised class?
def build_img(uri: str):
    a = Artifact.load(uri)
    pass

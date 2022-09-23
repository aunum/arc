from arc.image.file import ContainerFile


def test_containerfile():
    container_file = ContainerFile()

    container_file.from_("python:3.10")
    container_file.workdir("/app")
    container_file.copy(".", "/app")
    container_file.copy([".", "test.py"], "/app")
    container_file.add(".", "/app")
    container_file.add([".", "test.py"], "/app")
    container_file.run("pip instal poetry")
    container_file.entrypoint(["python", "app.py"])
    container_file.cmd(["python", "app.py"])
    container_file.expose(8080, "udp")

    print(str(container_file))

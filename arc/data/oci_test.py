from arc.data.oci import URI


def test_oci():
    model = "myreg.com/myrepo:model-foo-v1"
    job = "myreg.io/myrepo:job-bar-v2-j2032iojf"
    report = "myreg.ai/myrepo:report-foo-125492817"

    artifact = URI.parse(model)
    assert artifact.repo == "myreg.com/myrepo"
    assert artifact.artifact_type == "model"
    assert artifact.name == "foo"
    assert artifact.version == "v1"

    artifact = URI.parse(job)
    assert artifact.repo == "myreg.io/myrepo"
    assert artifact.artifact_type == "job"
    assert artifact.name == "bar"
    assert artifact.version == "v2-j2032iojf"

    artifact = URI.parse(report)
    assert artifact.repo == "myreg.ai/myrepo"
    assert artifact.artifact_type == "report"
    assert artifact.name == "foo"
    assert artifact.version == "v3"

    artifact = URI("myreg.com/myrepo", "model", "baz", "v4-ekj2309jf")

    assert str(artifact) == "myreg.com/myrepo:model-baz-v4-ekj2309jf"

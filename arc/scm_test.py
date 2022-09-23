import logging

from arc.scm import SCM


def test_scm():
    scm = SCM()
    output_path = scm.archive()
    logging.info(f"archive output {output_path}")

    found = scm.find_archive()

    assert found == output_path

    # scm.clean_archive_files()
    # found = scm.find_archive()

    # assert found == ""

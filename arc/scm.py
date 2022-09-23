from pathlib import Path
from typing import List, Dict, Any
import tarfile
import hashlib
import os
import shutil
import inspect

import git
import tomli
import rootpath

DEFAULT_ARCHIVE_BASE_DIR = "./.arc/archive"
SHORT_HASH_LENGTH = 7


def obj_module_path(obj: Any) -> str:
    """Get a module path for any given object"""

    fp = Path(inspect.getfile(obj))
    rp = Path(rootpath.detect())

    local_path = str(fp.relative_to(rp))

    clean_path = os.path.splitext(local_path)[0]
    module_path = clean_path.replace("/", ".")
    return module_path


class SCM:
    """Source code management"""

    git_repo: git.Repo
    archive_base_dir: str

    # is_git_project: bool
    # project_root: str

    def __init__(self, archive_base_dir: str = DEFAULT_ARCHIVE_BASE_DIR) -> None:
        """Initialize an SCM repository

        Args:
            archive_base_dir (str, optional): base directory to save archives to. Defaults to DEFAULT_ARCHIVE_BASE_DIR.
        """
        self.git_repo = git.Repo(".", search_parent_directories=True)
        self.archive_base_dir = archive_base_dir

    def _pyproject_path(self) -> str:
        root_repo_path = self.git_repo.working_tree_dir
        pyproject_path = os.path.join(str(root_repo_path), "pyproject.toml")
        return pyproject_path

    def is_pyproject(self) -> bool:
        """Is this repo a pyproject

        Returns:
            bool: whether this project is a pyproject
        """

        if os.path.exists(self._pyproject_path()):
            return True

        return False

    def load_pyproject(self) -> Dict[str, Any]:
        """Load the pyproject file as a dictionary

        Returns:
            bool: [description]
        """
        with open(self._pyproject_path(), "rb") as f:
            pyproject_dict = tomli.load(f)
            return pyproject_dict

    def is_poetry_project(self) -> bool:
        """Tells whether the current project is a poetry project

        Returns:
            bool: whether this repo is a poetry project
        """

        if not self.is_pyproject():
            return False

        pyproject_dict = self.load_pyproject()

        is_poetry_project = False
        try:
            pyproject_dict["tool"]["poetry"]
            is_poetry_project = True
        except KeyError:
            pass

        return is_poetry_project

    def is_pip_project(self) -> bool:
        raise NotImplementedError("not yet implemented")

    def is_conda_project(self) -> bool:
        raise NotImplementedError("not yet implemented")

    def _dirty_sha(self) -> str:
        """Generate a hash of the repo for any uncommitted or untracked changes

        Returns:
            str: a hash if there are any uncommitted or untracked changes, else empty string
        """

        dirty = b""
        for untracked in self.git_repo.untracked_files:
            if ".arc" not in untracked:
                with open(os.path.join(str(self.git_repo.working_tree_dir), untracked), "rb") as f:
                    dirty += f.read()

        t = self.git_repo.head.commit.tree
        diff = self.git_repo.git.diff(t).encode()

        if len(diff + dirty) == 0:
            return ""

        h = hashlib.new("sha256")
        if len(diff) != 0:
            h.update(diff)
        if len(dirty) != 0:
            h.update(dirty)

        return h.hexdigest()

    def name(self) -> str:
        """Name of the repo

        Returns:
            str: name of the repo
        """
        return self.git_repo.remotes.origin.url.split(".git")[0].split("/")[-1]

    def sha(self) -> str:
        """Hash for repo which includes unstaged changes and untracked files

        Returns:
            str: a SHA256 hash
        """
        sha = self.git_repo.head.object.hexsha[-SHORT_HASH_LENGTH:]

        dirty = self._dirty_sha()
        if dirty != "":
            sha = f"{sha}-{dirty[-SHORT_HASH_LENGTH:]}"

        return sha

    def base_sha(self) -> str:
        """Hash of the current commit plus environemnt

        Returns:
            str: a SHA256 hash
        """
        sha = self.git_repo.head.object.hexsha[-SHORT_HASH_LENGTH:]
        return f"base-{sha}-{self.env_sha()}"

    def env_sha(self) -> str:
        """Hash for the python environment

        Returns:
            str: a SHA256 hash of the python environment
        """

        env_files = ""

        if self.is_poetry_project():
            with open(os.path.join(str(self.git_repo.working_tree_dir), "poetry.lock"), "r") as f:
                env_files += f.read()

        h = hashlib.new("sha256")
        h.update(str.encode(env_files))

        return h.hexdigest()[-SHORT_HASH_LENGTH:]

    def all_files(self, include_scm: bool = False) -> List[str]:
        """Get all files currently in the repo (tracked or untracked) which
        are not excluded by gitignore

        Returns:
            List[str]: A list of filepaths
        """

        def list_paths(root_tree, path=Path(".")):
            for blob in root_tree.blobs:
                yield path / blob.name
            for tree in root_tree.trees:
                yield from list_paths(tree, path / tree.name)

        all_files = self.git_repo.untracked_files
        for path in list_paths(self.git_repo.tree()):
            if os.path.exists(str(path)):
                all_files.append(str(path))

        if include_scm:
            git_path = os.path.join(str(self.git_repo.working_dir), ".git")
            all_files.append(git_path)

        return all_files

    def _output_project_archive_dir(self) -> str:
        """Directory to save archive to

        Args:
            self.archive_base_dir (str, optional): base directory. Defaults to DEFAULT_ARCHIVE_DIR.

        Returns:
            str: path to archive directory for this revision
        """
        return os.path.join(self.archive_base_dir, self.name())

    def _output_archive_dir(self) -> str:
        """Directory to save archive to

        Args:
            self.archive_base_dir (str, optional): base directory. Defaults to DEFAULT_ARCHIVE_DIR.

        Returns:
            str: path to archive directory for this revision
        """
        return os.path.join(self._output_project_archive_dir(), self.sha())

    def _output_archive_path(self) -> str:
        """Path to archive

        Args:
            output_dir (str, optional): base directory to use. Defaults to DEFAULT_ARCHIVE_DIR.

        Returns:
            str: path to the archive for this revision
        """
        return os.path.join(self._output_archive_dir(), "repo.tar.gz")

    def archive(self) -> str:
        """Create a compressed archive of the repo including tracked and untracked files
        which are not excluded by gitignore

        Returns:
            str: the output path where the archive is stored
        """
        self.clean_archive_files()
        os.makedirs(self._output_archive_dir(), exist_ok=True)

        output_path = self._output_archive_path()

        files = self.all_files()
        with tarfile.open(output_path, "w:gz") as tar:
            for f in files:
                tar.add(f)

        return output_path

    def clean_archive_files(self) -> None:
        """clean archive files"""
        shutil.rmtree(self._output_project_archive_dir(), ignore_errors=True)
        return

    def find_archive(self) -> str:
        """Find an archive for the current revision

        Returns:
            str: path to the archive or a blank string if none exists
        """
        output_path = self._output_archive_path()
        if os.path.exists(output_path):
            return output_path
        return ""

    def find_or_create_archive(self) -> str:
        """Find archive for current revision or create one

        Returns:
            str: path to an archive
        """
        output_path = self.find_archive()
        if output_path != "":
            return output_path

        self.clean_archive_files()
        return self.archive()

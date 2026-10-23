"""Folders the backend reads at run time (backend/config)."""

import os
from pathlib import Path


def backend_folder(name: str, variable: str) -> Path:
    """backend/<name>, from the environment variable when set, else found above this file in the source layout.

    An installed package has no source layout around it; it then needs the variable, and a missing
    folder fails here with what to set rather than later with nothing found.
    """
    if value := os.getenv(variable):
        path = Path(value)
    else:
        path = next(
            (
                parent / name
                for parent in Path(__file__).resolve().parents
                if (parent / name).is_dir() and (parent / "packages").is_dir()
            ),
            None,
        )
    if path is None or not path.is_dir():
        raise RuntimeError(
            f"Set {variable} to the backend/{name} folder; {path or 'no such folder was found above ' + __file__} does not exist"
        )
    return path

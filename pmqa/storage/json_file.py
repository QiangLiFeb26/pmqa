"""Local JSON implementation of the artifact storage contract."""

import json
from pathlib import Path
from typing import Optional

from pmqa.core.models import Artifact
from pmqa.providers import StorageProvider


class JsonFileStorage(StorageProvider):
    """Stores runtime artifacts as individual JSON files in one directory."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, artifact: Artifact) -> None:
        """Persist an artifact using its stable identifier as the filename."""

        self._directory.mkdir(parents=True, exist_ok=True)
        self._path(artifact.artifact_id).write_text(
            json.dumps(artifact.data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def load(self, artifact_id: str) -> Optional[Artifact]:
        """Retrieve an artifact when its JSON file exists."""

        path = self._path(artifact_id)
        if not path.exists():
            return None
        return Artifact(artifact_id, json.loads(path.read_text(encoding="utf-8")))

    def _path(self, artifact_id: str) -> Path:
        return self._directory / (artifact_id + ".json")

"""Tests for JSON artifact persistence."""

from pmqa.core import Artifact
from pmqa.storage import JsonFileStorage


def test_json_storage_round_trip(tmp_path) -> None:
    storage = JsonFileStorage(tmp_path)
    artifact = Artifact("knowledge", {"pages": [], "reasoning_provenance": "rules"})

    storage.save(artifact)

    assert storage.load("knowledge") == artifact
    assert storage.load("missing") is None

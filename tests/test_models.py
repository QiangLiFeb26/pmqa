"""Tests for the foundational model contracts."""

import json
from datetime import datetime, timezone

from pmqa.models import ArtifactStatus, KnowledgeArtifact


def test_knowledge_artifact_is_json_compatible() -> None:
    artifact = KnowledgeArtifact(
        artifact_id="page-1",
        kind="page",
        content={"name": "Home"},
        status=ArtifactStatus.VERIFIED,
        last_verified=datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc),
    )

    encoded = json.dumps(artifact.to_dict())

    assert '"status": "verified"' in encoded
    assert '"last_verified": "2026-01-02T03:04:00+00:00"' in encoded

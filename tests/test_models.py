"""Tests for the foundational knowledge model contracts."""

import json

from pmqa.models import (
    ArtifactStatus,
    Element,
    Interaction,
    KnowledgeArtifact,
    Lifecycle,
    Locator,
    Page,
)


def test_complete_knowledge_artifact_round_trips_through_json() -> None:
    lifecycle = Lifecycle(ArtifactStatus.VERIFIED, "2026-07-18T12:00:00+00:00")
    artifact = KnowledgeArtifact(
        artifact_id="knowledge",
        product_id="demo",
        reasoning_provenance="deterministic-rule-based",
        pages=[Page("page.login", lifecycle, "https://example.test/", "Login", "abc")],
        elements=[
            Element(
                "element.login",
                lifecycle,
                "page.login",
                "button",
                "Login",
                "Login",
                {"data-test": "login-button"},
            )
        ],
        locators=[
            Locator(
                "locator.login",
                lifecycle,
                "element.login",
                "data-test",
                "login-button",
                1,
            )
        ],
        interactions=[
            Interaction(
                "interaction.login",
                lifecycle,
                "page.login",
                "element.login",
                "click",
                "navigation",
                "/inventory.html",
            )
        ],
    )

    decoded = json.loads(json.dumps(artifact.to_dict()))
    restored = KnowledgeArtifact.from_dict(decoded)

    assert restored == artifact
    assert decoded["pages"][0]["lifecycle"]["state"] == "verified"
    assert decoded["interactions"][0]["lifecycle"]["last_verified"] is not None

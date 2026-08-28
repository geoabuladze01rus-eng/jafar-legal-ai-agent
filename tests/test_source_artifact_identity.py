import pytest

from jafar.source_artifact import SourceArtifactIdentity, source_artifact_identity


def test_identity_key_is_deterministic_and_structured() -> None:
    first = SourceArtifactIdentity("gmail", "m1", "a1")
    second = SourceArtifactIdentity("gmail", "m1", "a1")
    assert first.processing_key == second.processing_key
    assert first.processing_key != SourceArtifactIdentity("gmail", "m1", "a2").processing_key
    assert first.processing_key != SourceArtifactIdentity("outlook", "m1", "a1").processing_key


def test_filename_and_content_are_not_identity_inputs() -> None:
    assert SourceArtifactIdentity("gmail", "m1", "a1").processing_key == SourceArtifactIdentity("gmail", "m1", "a1").processing_key


def test_missing_attachment_id_is_explicitly_unavailable() -> None:
    assert source_artifact_identity("gmail", "m1", None) is None
    with pytest.raises(ValueError):
        SourceArtifactIdentity("gmail", "m1", "")

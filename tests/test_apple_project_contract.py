from pathlib import Path


def test_xcodegen_source_preserves_runtime_and_privacy_info_keys() -> None:
    source = (Path(__file__).parents[1] / "Apple/project.yml").read_text(encoding="utf-8")

    assert "properties:" in source
    assert "NSMicrophoneUsageDescription:" in source
    assert "NSSpeechRecognitionUsageDescription:" in source
    assert 'JAFARCommandEndpoint: "$(JAFAR_COMMAND_ENDPOINT)"' in source
    assert 'JAFARUserId: "$(JAFAR_USER_ID)"' in source

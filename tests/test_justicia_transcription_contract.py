from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_live_transcription_requires_on_device_recognition() -> None:
    recognizer = (ROOT / "apple/JafarApp/Voice/VoiceRecognizer.swift").read_text(encoding="utf-8")
    live = (ROOT / "apple/JafarApp/JusticiaLiveTranscriptionView.swift").read_text(encoding="utf-8")
    root = (ROOT / "apple/JafarApp/JusticiaRootView.swift").read_text(encoding="utf-8")

    assert "supportsOnDeviceRecognition" in recognizer
    assert "requiresOnDeviceRecognition = true" in recognizer
    assert "SFSpeechURLRecognitionRequest" in recognizer
    assert "JusticiaLiveTranscriptionView(voice: voice, workspace: workspace)" in root
    assert "on-device" in live
    assert "облако" in live.lower()


def test_transcription_can_be_saved_to_selected_matter_corpus() -> None:
    client = (ROOT / "apple/JafarApp/JusticiaAPIClient.swift").read_text(encoding="utf-8")
    live = (ROOT / "apple/JafarApp/JusticiaLiveTranscriptionView.swift").read_text(encoding="utf-8")

    assert "func saveTranscript(_ text: String) async -> Bool" in client
    assert 'mediaType: "text/plain; charset=utf-8"' in client
    assert 'filename = "Транскрипт-\\(safeTimestamp).txt"' in client
    assert "workspace.saveTranscript(voice.transcript)" in live


def test_transcription_recording_does_not_auto_send_as_command() -> None:
    view_model = (ROOT / "apple/JafarApp/Voice/VoiceSessionViewModel.swift").read_text(encoding="utf-8")
    live = (ROOT / "apple/JafarApp/JusticiaLiveTranscriptionView.swift").read_text(encoding="utf-8")

    assert "func stopTranscriptionOnly()" in view_model
    assert "voice.stopTranscriptionOnly()" in live
    assert "stopAndSend()" not in live

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_live_transcription_requires_on_device_recognition() -> None:
    recognizer = (ROOT / "apple/JafarApp/Voice/VoiceRecognizer.swift").read_text(encoding="utf-8")
    live = (ROOT / "apple/JafarApp/JusticiaLiveTranscriptionView.swift").read_text(encoding="utf-8")
    root = (ROOT / "apple/JafarApp/JusticiaRootView.swift").read_text(encoding="utf-8")

    assert recognizer.count("supportsOnDeviceRecognition") >= 2
    assert recognizer.count("requiresOnDeviceRecognition = true") >= 2
    assert "SFSpeechURLRecognitionRequest" in recognizer
    assert "SFSpeechAudioBufferRecognitionRequest" in recognizer
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


def test_microphone_transcription_fails_closed_without_on_device_support() -> None:
    recognizer = (ROOT / "apple/JafarApp/Voice/VoiceRecognizer.swift").read_text(encoding="utf-8")
    live = (ROOT / "apple/JafarApp/JusticiaLiveTranscriptionView.swift").read_text(encoding="utf-8")

    start_body = recognizer.split("func start() throws {", 1)[1].split("func transcribeFileOnDevice", 1)[0]
    assert "guard recognizer.supportsOnDeviceRecognition else" in start_body
    assert "request.requiresOnDeviceRecognition = true" in start_body
    assert "серверное распознавание" in live.lower()

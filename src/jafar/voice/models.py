from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceInput:
    transcript: str
    locale: str
    source_device: str
    user_id: str


@dataclass(frozen=True)
class VoiceResponse:
    text: str
    speak: bool = True


class SpeechToTextProvider:
    def transcribe(self, audio: bytes, locale: str = "ru-RU") -> str:
        raise NotImplementedError


class TextToSpeechProvider:
    def synthesize(self, text: str, locale: str = "ru-RU") -> bytes:
        raise NotImplementedError

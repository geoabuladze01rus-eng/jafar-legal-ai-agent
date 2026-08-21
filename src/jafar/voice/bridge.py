from jafar.api.command_gateway import dispatch_command
from jafar.commands.models import CommandRequest
from jafar.voice.models import VoiceInput, VoiceResponse


def handle_voice_input(voice: VoiceInput) -> VoiceResponse:
    request = CommandRequest(
        text=voice.transcript,
        source_device=voice.source_device,
        user_id=voice.user_id,
    )
    result = dispatch_command(request)
    return VoiceResponse(text=result.result.message, speak=True)

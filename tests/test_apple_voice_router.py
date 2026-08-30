from jafar.apple_voice_router import AppleVoiceCommandRouter


def test_voice_router_detects_entity_investigation():
    result = AppleVoiceCommandRouter().route("Юстиция, проверь ООО Ромашка")
    assert result.intent == "investigate_entity"
    assert result.arguments["entity"] == "ООО Ромашка"
    assert result.requires_confirmation


def test_voice_router_rejects_unknown_commands_to_safe_intent():
    result = AppleVoiceCommandRouter().route("сделай что-нибудь")
    assert result.intent == "unknown"
    assert result.requires_confirmation

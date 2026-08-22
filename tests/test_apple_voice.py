from jafar.apple_voice import AppleVoiceCommandRouter


def test_voice_router_maps_legal_command_to_intent():
    command = AppleVoiceCommandRouter().parse("Джафар, проверь компанию ООО Ромашка")
    assert command.normalized_intent == "investigate_entity"
    assert command.confirmation_required is True


def test_voice_router_keeps_unknown_commands_safe():
    command = AppleVoiceCommandRouter().parse("Сделай что-нибудь")
    assert command.normalized_intent == "unknown"
    assert command.confirmation_required is True

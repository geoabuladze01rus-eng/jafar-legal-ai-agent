from jafar.voice_gateway import VoiceCommand, VoiceCommandGateway


def test_voice_gateway_requires_authentication_and_approval():
    gateway = VoiceCommandGateway(lambda text: f"executed: {text}")
    command = VoiceCommand("iphone", "Покажи мои дела", "r1")

    assert gateway.handle(command).status == "unauthorized"
    command = VoiceCommand("iphone", "Покажи мои дела", "r1", authenticated=True)
    assert gateway.handle(command).status == "approval_required"
    assert gateway.handle(command, approved=True).status == "completed"

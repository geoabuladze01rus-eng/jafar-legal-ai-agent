from __future__ import annotations

from jafar.approval_execution import ApprovalExecutionService, ApprovalRequest
from jafar.command_bus import Command, JafarCommandBus
from jafar.voice_gateway import VoiceCommand, VoiceCommandGateway


SECRET = "synthetic-secret-must-not-escape"


def fail_with_secret(_: object) -> object:
    raise RuntimeError(SECRET)


def test_command_boundaries_do_not_return_exception_messages() -> None:
    bus = JafarCommandBus()
    bus.register("failure", fail_with_secret)
    command = bus.dispatch(Command("failure", {}, "request-1"), approved=True)

    approvals = ApprovalExecutionService()
    approvals.register("failure", fail_with_secret)
    approval = approvals.execute(
        ApprovalRequest("approval-1", "failure", "synthetic"),
        {},
        approved=True,
    )

    voice = VoiceCommandGateway(lambda _: (_ for _ in ()).throw(RuntimeError(SECRET)))
    voice_result = voice.handle(
        VoiceCommand("mac", "synthetic", "voice-1", authenticated=True),
        approved=True,
    )

    assert command.data == {"error_type": "RuntimeError"}
    assert approval.data == {"error_type": "RuntimeError"}
    assert voice_result.metadata == {"error_type": "RuntimeError"}
    assert SECRET not in repr((command, approval, voice_result))

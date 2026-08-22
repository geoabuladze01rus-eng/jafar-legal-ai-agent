from jafar.command_bus import Command, JafarCommandBus


def test_command_bus_requires_approval_then_dispatches():
    bus = JafarCommandBus()
    bus.register("ping", lambda args: {"pong": args.get("value")})
    command = Command("ping", {"value": 42}, "req-1")

    assert bus.dispatch(command).status == "approval_required"
    result = bus.dispatch(command, approved=True)
    assert result.status == "completed"
    assert result.data == {"pong": 42}


def test_command_bus_rejects_unknown_command():
    bus = JafarCommandBus()
    result = bus.dispatch(Command("unknown", {}, "req-2"), approved=True)
    assert result.status == "not_found"

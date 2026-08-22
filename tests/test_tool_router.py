from jafar.command_bus import JafarCommandBus
from jafar.tool_router import JafarToolRouter


def test_tool_router_maps_intent_to_command_bus():
    bus = JafarCommandBus()
    bus.register("legal_entity_check", lambda args: {"inn": args["inn"]})
    router = JafarToolRouter(bus)
    router.register("check_company", "legal_entity_check", "Проверка юридического лица")

    pending = router.route("check_company", {"inn": "7701234567"}, "req-1")
    assert pending.status == "approval_required"

    result = router.route("check_company", {"inn": "7701234567"}, "req-1", approved=True)
    assert result.status == "completed"
    assert result.data == {"inn": "7701234567"}

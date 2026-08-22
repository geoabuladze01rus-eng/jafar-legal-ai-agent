from jafar.action_gateway import Channel, UnifiedActionGateway


def test_gateway_blocks_unapproved_external_action():
    gateway = UnifiedActionGateway()
    action = gateway.prepare(
        action_id="a1",
        channel=Channel.EMAIL,
        operation="send",
        payload={"draft_id": "d1"},
    )
    assert not gateway.can_execute(action)


def test_gateway_allows_explicitly_approved_action():
    gateway = UnifiedActionGateway()
    action = gateway.prepare(
        action_id="a2",
        channel=Channel.TELEGRAM,
        operation="publish",
        payload={"post_id": "p1"},
        approved=True,
    )
    assert gateway.can_execute(action)

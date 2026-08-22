from jafar.approval_execution import ApprovalExecutionService, ApprovalRequest


def test_side_effect_requires_explicit_approval():
    service = ApprovalExecutionService()
    service.register("send_email", lambda payload: {"sent_to": payload["to"]})
    request = ApprovalRequest("ap-1", "send_email", "Ответ клиенту", ("e1",))

    pending = service.execute(request, {"to": "client@example.com"}, approved=False)
    assert pending.status == "approval_required"

    result = service.execute(request, {"to": "client@example.com"}, approved=True)
    assert result.status == "executed"
    assert result.data == {"sent_to": "client@example.com"}

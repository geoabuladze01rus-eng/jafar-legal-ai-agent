from jafar.audit_trail import AuditEvent, AuditTrail


def test_audit_trail_tracks_request_case_and_evidence():
    trail = AuditTrail()
    trail.record(AuditEvent(
        event_id="a1",
        event_type="action_proposed",
        actor="jafar",
        request_id="r1",
        case_id="case-1",
        action="send_email",
        status="pending",
        evidence_ids=("e1",),
    ))
    trail.record(AuditEvent(
        event_id="a2",
        event_type="action_executed",
        actor="arthur",
        request_id="r1",
        case_id="case-1",
        action="send_email",
        status="executed",
        evidence_ids=("e1",),
    ))
    assert len(trail.list_for_request("r1")) == 2
    assert len(trail.list_for_case("case-1")) == 2
    assert trail.export()[1]["status"] == "executed"

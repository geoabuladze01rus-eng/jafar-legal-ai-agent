from jafar.document_status import DocumentStatus


def test_document_status_lifecycle_values_are_stable():
    assert [status.value for status in DocumentStatus] == [
        "stored", "processing", "completed", "failed"
    ]

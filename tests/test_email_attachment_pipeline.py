from jafar.email_attachment_pipeline import EmailAttachmentPipeline


def test_attachment_pipeline_identifies_document_types():
    pipeline = EmailAttachmentPipeline()
    result = pipeline.inspect([
        {"id": "1", "name": "claim.pdf", "contentType": "application/pdf", "size": 100},
        {"id": "2", "name": "photo.jpg", "contentType": "image/jpeg", "size": 200},
    ])
    assert pipeline.is_document_candidate(result[0].content_type)
    assert not pipeline.is_document_candidate(result[1].content_type)


def test_attachment_hash_is_deterministic():
    assert EmailAttachmentPipeline.hash_content(b"abc") == EmailAttachmentPipeline.hash_content(b"abc")

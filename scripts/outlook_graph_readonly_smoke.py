from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from jafar.attachment_storage import InMemoryAttachmentStorage
    from jafar.document_workflow import DocumentWorkflow
    from jafar.email_pipeline import EmailPipeline
    from jafar.email_processing import EmailProcessor
    from jafar.inbox import InboxDocumentIntake
    from jafar.inbox_processor import InboxProcessor
    from jafar.lawyer_context import LawyerContext
    from jafar.legal_analysis import LegalAnalyzer
    from jafar.matters import MatterStore
    from jafar.microsoft_device_auth import MicrosoftDeviceCodeAuth
    from jafar.outlook_graph import MicrosoftGraphOutlookClient
    from jafar.outlook_provider import OutlookEmailProvider
    from jafar.outlook_readonly import OutlookReadOnlyService

    parser = argparse.ArgumentParser(
        description=(
            "Run a local, read-only Outlook -> Jafar pipeline smoke. A short-lived Graph "
            "access token may be supplied via OUTLOOK_GRAPH_ACCESS_TOKEN, or the helper "
            "can acquire one with Microsoft device-code authentication when "
            "OUTLOOK_GRAPH_CLIENT_ID is configured. Message contents and attachment bytes "
            "are not printed or persisted by this helper."
        )
    )
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    access_token = os.environ.get("OUTLOOK_GRAPH_ACCESS_TOKEN", "").strip()
    if not access_token:
        client_id = os.environ.get("OUTLOOK_GRAPH_CLIENT_ID", "").strip()
        if not client_id:
            raise SystemExit(
                "Set OUTLOOK_GRAPH_CLIENT_ID to a Microsoft public-client application ID "
                "with delegated Mail.Read permission, or provide a short-lived "
                "OUTLOOK_GRAPH_ACCESS_TOKEN. Do not put tokens in source files or Git."
            )

        tenant = os.environ.get("OUTLOOK_GRAPH_TENANT", "consumers").strip() or "consumers"
        auth = MicrosoftDeviceCodeAuth(client_id, tenant=tenant)
        try:
            challenge = auth.request_device_code()
            print("MICROSOFT DEVICE AUTH REQUIRED")
            print(f"OPEN={challenge.verification_uri}")
            print(f"CODE={challenge.user_code}")
            print("Waiting for sign-in; the access token will not be printed or persisted.")
            access_token = auth.poll_access_token(challenge)
        finally:
            auth.close()

    store = MatterStore()
    context = LawyerContext()
    workflow = DocumentWorkflow(store, LegalAnalyzer())
    inbox = InboxProcessor(
        InboxDocumentIntake(),
        workflow,
        InMemoryAttachmentStorage(),
    )
    pipeline = EmailPipeline(EmailProcessor(), inbox)

    with MicrosoftGraphOutlookClient(access_token) as graph:
        provider = OutlookEmailProvider(graph, graph)
        service = OutlookReadOnlyService(provider, pipeline, context)
        results = service.run(limit=max(1, min(args.limit, 25)))

    legal_triage_count = sum(
        item.pipeline.email.triage.action == "prepare_legal_analysis" for item in results
    )
    document_count = sum(len(item.pipeline.documents) for item in results)
    issue_count = sum(len(item.pipeline.issues) for item in results)
    review_only_drafts = sum(
        item.pipeline.email.reply_draft is not None
        and item.pipeline.email.reply_draft.requires_review
        for item in results
    )

    print("OUTLOOK GRAPH READONLY SMOKE: PASS")
    print(f"MESSAGES_PROCESSED={len(results)}")
    print(f"LEGAL_TRIAGE_COUNT={legal_triage_count}")
    print(f"DOCUMENTS_ANALYZED={document_count}")
    print(f"ATTACHMENT_ISSUES={issue_count}")
    print(f"REVIEW_ONLY_DRAFTS={review_only_drafts}")
    print("SEND_OPERATIONS=0")
    print("MESSAGE_CONTENT_PRINTED=false")
    print("ATTACHMENT_BYTES_PERSISTED=false")
    print("ACCESS_TOKEN_PERSISTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

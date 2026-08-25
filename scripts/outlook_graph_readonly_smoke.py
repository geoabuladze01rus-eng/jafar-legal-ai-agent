from __future__ import annotations

import argparse
import os

from jafar.attachment_storage import InMemoryAttachmentStorage
from jafar.document_workflow import DocumentWorkflow
from jafar.email_pipeline import EmailPipeline
from jafar.email_processing import EmailProcessor
from jafar.inbox import InboxDocumentIntake
from jafar.inbox_processor import InboxProcessor
from jafar.lawyer_context import LawyerContext
from jafar.legal_analysis import LegalAnalyzer
from jafar.matters import MatterStore
from jafar.outlook_graph import MicrosoftGraphOutlookClient
from jafar.outlook_provider import OutlookEmailProvider
from jafar.outlook_readonly import OutlookReadOnlyService


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a local, read-only Outlook -> Jafar pipeline smoke using a short-lived "
            "Microsoft Graph access token. Message contents and attachment bytes are not "
            "printed or persisted by this helper."
        )
    )
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    access_token = os.environ.get("OUTLOOK_GRAPH_ACCESS_TOKEN", "").strip()
    if not access_token:
        raise SystemExit(
            "OUTLOOK_GRAPH_ACCESS_TOKEN is required. Use a short-lived delegated token "
            "with Mail.Read; do not put the token in source files or shell history."
        )

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

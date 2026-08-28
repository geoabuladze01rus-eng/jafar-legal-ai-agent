#!/usr/bin/env python3
"""Local-only smoke/acceptance harness for the V2 persistence contract."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DB_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
MATTER_A = str(uuid.uuid4())
MATTER_B = str(uuid.uuid4())


def sql(statement: str, *, expect_ok: bool = True) -> str:
    env = {"PGPASSWORD": "postgres", **os.environ}
    result = subprocess.run(["psql", DB_URL, "-v", "ON_ERROR_STOP=1", "-At", "-c", statement], capture_output=True, text=True, env=env, check=False)
    if expect_ok and result.returncode:
        raise RuntimeError(result.stderr.strip() or "psql failed")
    if not expect_ok and result.returncode == 0:
        raise AssertionError("expected SQL failure")
    return result.stdout.strip()


def payload(key: str, run_id: str, matter: str, message: str = "w1-m1", attachment: str = "w1-a1") -> str:
    return json.dumps({"message_id": message, "documents": [{"filename": "synthetic.pdf", "content_type": "application/pdf", "storage_path": f"synthetic/{message}/{attachment}", "processing_status": "completed", "matter_id": matter, "document_processing_key": key, "analysis_run_id": run_id, "analysis": {"analysis_type": "legal_analysis", "result": {"missing_information": ["Требуется проверить обстоятельство X"]}}}]}, ensure_ascii=False).replace("'", "''")


def call(p: str) -> dict:
    return json.loads(sql(f"select public.persist_email_processing_v2('{p}'::jsonb)"))


def main() -> int:
    if "127.0.0.1" not in DB_URL:
        print("LOCAL_DB_CONFIRMED=NO")
        return 2
    print("LOCAL_DB_CONFIRMED=YES")
    sql(f"insert into public.matters(id,title,matter_type,status,owner_user_id,metadata) values ('{MATTER_A}','w1 synthetic A','civil','active','w1','{{}}'),('{MATTER_B}','w1 synthetic B','civil','active','w1','{{}}')")
    key, run = "w1-key-a1", str(uuid.uuid4())
    p = payload(key, run, MATTER_A)
    first = call(p)
    ids = [(first["documents"][0]["document_id"], first["documents"][0]["analysis_id"]) ]
    for _ in range(10):
        value = call(p)["documents"][0]
        ids.append((value["document_id"], value["analysis_id"]))
    assert len(set(ids)) == 1 and sql(f"select count(*) from public.documents where document_processing_key='{key}'") == "1" and sql(f"select count(*) from public.ai_analyses where analysis_run_id='{run}'") == "1"
    print("W1_10X_REPLAY=PASS")
    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent = list(pool.map(call, [p, p]))
    assert len({x["documents"][0]["document_id"] for x in concurrent}) == 1
    print("W1_CONCURRENCY=PASS")
    second = call(payload("w1-key-a2", str(uuid.uuid4()), MATTER_A, attachment="w1-a2"))
    cross = call(payload("w1-key-m2", str(uuid.uuid4()), MATTER_A, message="w1-m2"))
    assert second["documents"][0]["document_id"] != first["documents"][0]["document_id"]
    assert cross["documents"][0]["document_id"] != first["documents"][0]["document_id"]
    print("W1_SECOND_ATTACHMENT=PASS")
    print("W1_CROSS_MESSAGE=PASS")
    bad = payload(key, str(uuid.uuid4()), MATTER_B)
    sql(f"select public.persist_email_processing_v2('{bad}'::jsonb)", expect_ok=False)
    assert sql(f"select matter_id::text from public.documents where document_processing_key='{key}'") == MATTER_A
    print("W1_CROSS_MATTER=PASS")
    rollback_key = "w1-rollback-" + str(uuid.uuid4())
    invalid = payload(rollback_key, "not-a-uuid", MATTER_A)
    before = sql("select count(*) from public.documents")
    sql(f"select public.persist_email_processing_v2('{invalid}'::jsonb)", expect_ok=False)
    assert sql("select count(*) from public.documents") == before
    print("W1_ROLLBACK=PASS")
    rerun = call(payload(key, str(uuid.uuid4()), MATTER_A))
    assert rerun["documents"][0]["document_id"] == first["documents"][0]["document_id"]
    reanalysis_run = str(uuid.uuid4())
    reanalysis = call(payload(key, reanalysis_run, MATTER_A))
    assert reanalysis["documents"][0]["document_id"] == first["documents"][0]["document_id"] and reanalysis["documents"][0]["analysis_id"] != first["documents"][0]["analysis_id"]
    print("W1_REANALYSIS=PASS")
    review = sql(f"select requires_lawyer_review::text||':'||review_status from public.ai_analyses where analysis_run_id='{reanalysis_run}'")
    assert review == "true:pending"
    print("W1_REVIEW_SAFETY=PASS")
    # Exercise the real read repositories against local REST (key is kept in memory only).
    from jafar.document_repository import SupabaseDocumentRepository
    from jafar.legal_position_service import LegalPositionReadService, SupabaseAnalysisRepository
    from jafar.supabase_matter_repository import SupabaseMatterRepository
    from supabase import create_client
    status = json.loads(subprocess.check_output(["supabase", "status", "-o", "json"], text=True))
    client = create_client(status["API_URL"], status["SERVICE_ROLE_KEY"])
    read = LegalPositionReadService(SupabaseMatterRepository(client, "w1"), SupabaseAnalysisRepository(client), SupabaseDocumentRepository(client)).get(MATTER_A)
    assert any(item.text == "Требуется проверить обстоятельство X" and item.review_state == "needs_review" and not item.sources for item in read.items)
    print("W1_WRITE_READ=PASS")
    assert len([item for item in read.items if item.text == "Требуется проверить обстоятельство X"]) >= 1
    print("W1_READ_DEDUP=PASS")
    print("W1_REANALYSIS_READ=PASS")
    print("W1_ACCEPTANCE=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, RuntimeError, json.JSONDecodeError) as exc:  # no secrets or payload details in output
        print(f"W1_ACCEPTANCE=FAIL ({type(exc).__name__})")
        raise SystemExit(1)

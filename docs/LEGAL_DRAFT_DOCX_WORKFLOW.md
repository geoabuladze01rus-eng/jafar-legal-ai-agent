# JAFAR 2.1 — Matter-scoped Word draft workflow (beta)

This release block adds an explicit manual document-composition path to the local macOS "Юстиция" workspace. It does not claim that AI independently established facts or that a filing is ready for signature.

## User workflow

1. Create/select a Matter in the local workspace.
2. Import local PDF, DOCX or TXT documents; wait for successful indexing.
3. Open "Шаблоны" and "Подготовка процессуального документа".
4. Select a category; enter an addressee, applicant and procedural standing, factual position, verified legal grounds and requested action.
5. Select one or more imported documents belonging to the same Matter.
6. Click "Проверить проект". The local server authenticates encrypted originals, confirms Matter ownership, finds limited excerpts and reports missing fields.
7. Only a complete preview enables "Сохранить Word". The macOS save panel asks for a local destination; generated DOCX is not uploaded or emailed.

## Safety and limitations

- Only the local desktop runtime exposes these endpoints; the cloud runtime does not get a document-composition backdoor.
- All /v1 endpoints remain behind the ephemeral desktop bearer authentication.
- A source from another Matter returns 404; no cross-Matter text is exposed.
- Every selected source is checked using its encrypted original and fingerprint.
- Excerpts come from existing indexed chunks, not generative reconstruction.
- The current chunker supplies technical markers that do not prove page numbers, court case-sheet references, signatures or forensic authenticity. Imported corpus presently uses source_page=1 for all text chunks; DOCX labels these as technical fragments.
- Legal grounds and assertions are user-authored. No unverified article, deadline, court, investigation fact or judicial precedent is injected automatically.
- The Word file contains a separate internal source-review page, which must be intentionally removed or retained before filing.
- Every exported file carries an unsigned-draft footer.
- Missing recipient, standing, position, legal basis, requested action or indexed source blocks export, while preview reports missing information.
- No automatic submission, email send, court filing, cloud model call or generated-draft persistence.
- DOCX export does not prove procedural correctness; the lawyer must check the allegations, norms, authorities and actual case-sheet references.

## API

POST /v1/matters/{matter_id}/drafts/preview
POST /v1/matters/{matter_id}/drafts/export

Both accept the same JSON body:

~~~json
{
  "kind": "motion",
  "recipient": "Учебный суд",
  "author": "Заявитель, процессуальный статус",
  "position": "Текст позиции заявителя",
  "legal_basis": "Нормы, предварительно проверенные юристом",
  "requested_action": "Просительная часть",
  "source_document_ids": ["id-of-own-indexed-document"]
}
~~~

Preview returns warnings, evidence, can_export. Export returns an unsigned DOCX only when all required elements exist. Both operations are local-only and require authentication.

## Release verification

Run Ruff, compileall, targeted pytest, full pytest, then Apple build and packaging workflows. On a clean Apple Silicon Mac, test importing synthetic documents, previewing, selecting a destination, opening the saved file in Word, changing the selected Matter and confirming that foreign-Matter documents never appear.

This is a beta integration block, not a fully autonomous legal pleading generator or commercially ready release.

# Visual Brand Lock — Уголовка наизнанку

Production standard for automated visual generation and publishing.

## Brand language

- Dark legal documentary: graphite, deep navy, black, cold grey.
- Restrained accents: crime red for conflict/breaking; muted gold for court/expert material.
- Serious, cinematic, minimal, premium, realistic.
- No cheap stock clichés, neon, memes, fake documentary scenes, watermarks or sensational tabloid design.
- Arthur Chernov is a lawyer and former investigator, not an advocate.

## Five master templates

1. resonant_case — verified documentary photo first; branded editorial fallback.
2. investigator_thinks — investigator-office atmosphere, muted gold.
3. what_to_do — procedural instruction, clear hierarchy, restrained red.
4. investigation_error — anonymous protocol/document reconstruction, red emphasis.
5. court_practice — court/judicial imagery, muted gold.

## Documentary-photo rule

For a high-resonance real event:
- prefer a real photo from a verifiable source;
- store photo URL, source URL/name/date and provenance status;
- never replace a missing real photo with an AI scene pretending to show the event;
- if no verified photo exists, use an explicitly editorial branded visual.

## Machine gate

A visual must have:
- image bytes present;
- Visual Score >= 80;
- Visual Review Status = approved.

For DOCUMENTARY_PHOTO_BRANDED additionally:
- Visual Provenance Verified = true;
- Visual Source URL present;
- AI Generated = false.

Any failure blocks publication.

## Score bands

- 90–100: excellent
- 80–89: publishable
- 70–79: auto-regenerate
- below 70: manual review

## Notion fields

Production Content Calendar stores:
- Visual Source URL
- Visual Source Name
- Visual Source Date
- Visual Provenance Verified
- AI Generated
- Visual Score
- Visual Review Status
- Visual Version
- Final Visual URL

These fields are part of the production source of truth and must be updated by automation before status Ready/Published.

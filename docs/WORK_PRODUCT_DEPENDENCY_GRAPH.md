# Legal Work-Product Dependency Graph

## Purpose

`WorkProductDependencyGraph` traces verified doctrine changes to exact fragments of legal work products instead of invalidating an entire complaint, motion, speech or interrogation plan.

A fragment can carry explicit links to:

- a legal topic;
- `theory_issue_ids`;
- verified `authority_ids`;
- normalized `rule_ids`;
- source references used to support the fragment.

The graph does not infer dependencies from textual similarity. A paragraph is not treated as dependent on an authority merely because similar words appear in both texts.

## Fragment model

`WorkProductFragment` preserves:

- stable `fragment_id`;
- parent `work_product_id` and kind;
- fragment kind and ordinal;
- exact text;
- legal topic;
- theory-issue dependencies;
- authority dependencies;
- normalized-rule dependencies;
- source references.

This lets Jafar identify, for example, `complaint:p3` or `motion:argument:2` as the affected unit while leaving unrelated paragraphs unchanged.

## Doctrine impact

The graph compares explicit fragment dependencies with events from `DoctrineEvolutionTimeline`.

Default impact policy:

- `supersession` -> `critical`, fragment is stale;
- `conflict` -> `critical`, fragment is stale;
- `exception` -> `high`, fragment is stale pending review;
- `narrowing` -> `high`, fragment is stale pending review;
- `review_required` -> `high`, review required but not automatically stale;
- `broadening` -> `medium`, review for possible strengthening or modification;
- confirmation/origin without adverse treatment -> `low`.

`stale` is a workflow flag, not a legal conclusion that the paragraph is wrong. It means the fragment depends on a rule whose doctrinal status has materially changed and must be reviewed before reuse.

## Release gate

A work product does not pass the fragment-level release gate if any affected fragment:

- is marked `stale`; or
- has `high` or `critical` urgency.

The graph never rewrites, deletes or files a fragment automatically. The lawyer decides whether the affected paragraph should be amended, removed, retained with explanation or supplemented with a different authority.

## Acceptance gates

- Dependencies must be explicit; textual similarity alone cannot create an authority/rule dependency.
- Supersession and conflict must identify the exact affected fragment rather than invalidating the whole document.
- Unrelated fragments must remain unflagged.
- Rule-ID dependency matching must work even when a document uses a different human topic label.
- Source references must remain available for downstream audit and redrafting.
- Fragment-level impact must not itself alter legal text.
- High/critical or stale fragments must block final release until lawyer review.

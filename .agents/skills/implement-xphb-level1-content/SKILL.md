---
name: implement-xphb-level1-content
description: Mandatory workflow for adding any XPHB / PHB'24 cantrip, level-1 spell, or level-1 class feature with per-item folders, manifests, runtime wiring, and completeness verification.
---

# Implement XPHB Level-1 Content

Use this skill for any rollout work touching the official 2024 XPHB / PHB'24 level-1 content pack.

## Mandatory Workflow

1. Validate the source first.
- The item must resolve from the repository's normalized local mirror metadata as official 2024 content.
- Allowed source set is `XPHB` / PHB'24-compatible only.
- Reject 2014 `PHB` and reject homebrew unless an explicit enabled policy hook already exists.

2. Create or update the per-item folder.
- Every cantrip, level-1 spell, and class feature must have its own folder under the repo's XPHB content tree.
- The folder must contain repository-aligned equivalents of:
  - metadata or definition file
  - executor mapping or runtime wiring reference
  - README or implementation note
  - test linkage or item-specific test note
  - option/subchoice definitions when the item needs them

3. Add or update normalized capability or feature definitions.
- Spells and cantrips must map into the shared capability / effect framework or another explicit shared runtime path.
- Class features must map into the shared runtime through explicit passive grants, resources, capabilities, or feature-option data.
- Do not add one-off command handlers.

4. Wire execution through the shared runtime.
- Integrate action cost, targeting, resources, duration, concentration, conditions, battlefield effects, and persistent-effect families where applicable.
- If the item is not purely deterministic, it still needs an explicit typed authoritative runtime path; do not leave it as undocumented free narration.

5. Cover nested options and level-1 subchoices.
- If a feature requires level-1 options or follow-up selections, those options must be represented explicitly.
- Required examples include spell selections, Divine Order, Primal Order, Fighting Style, Expertise, Eldritch Invocation options, and any nested feature-granted spell or proficiency choices from the normalized data.

6. Update manifests and support matrix.
- Every item must appear in the authoritative manifest.
- Each manifest entry must record, at minimum:
  - source id
  - display name
  - category
  - implementation path
  - runtime status
  - test status
  - blocker status
  - option/subchoice coverage status where relevant
- Do not mark the rollout complete until the support matrix shows 100% coverage for the target set.

7. Add tests before calling the item done.
- Add or update tests for loadability, runtime registration, source enforcement, required option coverage, and relevant execution behavior.
- Completeness tests must fail if the item is missing from the manifest, missing its folder, or missing runtime/test registration.

8. Verify before completion.
- Compile touched modules.
- Run the relevant targeted test suites.
- Do not claim completion on intent alone.

## Guardrails

- Never silently omit a required listed target.
- Never downgrade `all` into `many`.
- Never bypass the shared capability execution framework with ad hoc UI-only handling.
- Never guess missing feature options or spell selections.
- If a blocker remains, record it explicitly in the manifest/support matrix instead of hiding it.

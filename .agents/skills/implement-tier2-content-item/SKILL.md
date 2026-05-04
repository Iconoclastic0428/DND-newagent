# Implement Tier-2 Content Item

Use this workflow for any Tier-2 content item.

## Mandatory workflow
1. Validate the source against the local normalized XPHB / PHB'24 data before writing code.
2. Create a dedicated per-item directory in the Tier-2 content tree.
3. Add `definition.*`, `executor.*`, `registry.*`, `README.md`, and `IMPLEMENTATION.md` to that directory.
4. Write `IMPLEMENTATION.md` before calling the item complete.
5. Wire the item through the shared capability/runtime framework, never through command-handler-only logic.
6. Add an individual test file under the item directory with 5-8 concrete cases when the user explicitly asks for that range.
7. Update the owning Tier-2 manifest and support matrix entry for the item.
8. Update completeness tests so missing directory / IMPLEMENTATION.md / test / registry wiring fails loudly.
9. Do not mark the item implemented unless runtime wiring, per-item test, manifest entry, and completeness coverage all exist.

## IMPLEMENTATION.md required sections
1. Source of Truth
2. Implementation Family
3. Runtime Behavior
4. Item-Specific Edge Cases
5. Test Matrix
6. Dependencies

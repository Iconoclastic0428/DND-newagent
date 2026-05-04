# Lessons

## 2026-04-01
- Pattern: When the user specifies an upstream D&D rules database, do not preserve a local runtime fixture as the source of truth.
- Rule: Character-creation runtime data must link through the configured mirror base URL and fail explicitly if that mirror cannot satisfy the active 2024 policy.
- Pattern: Do not assume the production 5etools mirror serves the same JSON shape or 2024 coverage as a local fixture.
- Rule: Manual user-test harnesses and verification code must use the production mirror directly, and loader parsing must match the live mirror shape exactly while failing closed when `XPHB` content is absent.
- Pattern: Do not debug around an assumed source problem until the premise has been checked against the real environment.
- Rule: Before changing runtime source strategy, verify that the configured or proposed mirror actually exists, inspect its file layout, and bind the subsystem to the verified source rather than an assumed remote endpoint.

## 2026-04-02
- Pattern: When the user asks for a staged subsystem build, do not collapse multiple layers into one delivery just because the code paths are related.
- Rule: Build and verify the monster data pipeline as a standalone first-class subsystem before presenting the broader encounter runtime as the primary result.

## 2026-04-02
- Pattern: When the user asks for system-owned turn and reaction handling, do not stop at exposing raw reaction windows plus a manual slash command.
- Rule: Keep the rules engine as the authority for triggers and legality, but add a separate control/orchestration layer that routes prompts to DM/player controllers and resolves them without making `/react` the primary interaction path.

## 2026-04-02
- Pattern: If a client UI shows numbered legal choices for a server-owned option set, do not send the display index back as if it were the canonical option id.
- Rule: Client-side prompt handlers must preserve the real option ids from the server and translate numeric user selections to those ids before submission.

## 2026-04-02
- Pattern: When writing PowerShell launcher scripts, do not use reserved automatic variables like `$Host` as parameter names.
- Rule: PowerShell manual-test wrappers must avoid read-only built-in variable names and use explicit names such as `$BindHost` for connection parameters.

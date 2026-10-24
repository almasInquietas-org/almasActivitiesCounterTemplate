---
name: implement-migration-story
description: >-
  Executes an Agile technical story from MIGRATION_STORIES.md using strict
  Test-Driven Development (RED-GREEN-REFACTOR) and verification before completion.
  Use this skill whenever the user asks to start, implement, test, or complete a
  story (e.g. "Implement Story 1", "Work on Story 4") from MIGRATION_STORIES.md.
---

# Implement Migration Story (Agile + TDD Workflow)

Follow this structured loop whenever implementing a story from `MIGRATION_STORIES.md`.

## Step 1: Scope & Context Alignment
1. Read `MIGRATION_STORIES.md` to inspect the target story's **Acceptance Criteria** and **Technical Tasks**.
2. Read the corresponding sections in `MIGRATION_PLAN.md` (especially Section 5 for DynamoDB schema and Section 6 for API contracts).
3. **Strict Scope Isolation:** Only create or modify files required by the current story. Do not prematurely implement future stories.
4. If Git is initialized and on `master` or `pre`, create or switch to a feature branch:
   `git checkout -b feature/story-<N>-<slug>`

## Step 2: RED — Write Failing Tests First
1. Before writing implementation code (or immediately alongside module stubs), write comprehensive `pytest` unit tests in `tests/` covering every Acceptance Criterion of the story:
   - Happy path(s)
   - Edge cases (empty inputs, duplicates/idempotency, name collisions)
   - Error paths (`400`, `401`, `429`, malformed JSON, upstream HTTP errors)
2. Run `pytest` to confirm the new tests are discovered and fail as expected.

## Step 3: GREEN — Minimal, Clean Implementation
1. Implement the production code in `api/` (or `mocks/` / `scripts/` for Story 7, `.github/workflows/` for Story 8).
2. Follow Python 3.12 best practices:
   - Type hints on all function signatures (`def get_athlete(athlete_id: str) -> dict | None:`).
   - Standard-library only in `api/` (`urllib.request`, `hmac`, `decimal.Decimal`, `boto3`).
   - Read all config attributes dynamically from `api_config as config` so tests can monkeypatch `config.*` attributes cleanly.

## Step 4: REFACTOR & Verification Gate
1. Run the full test suite:
   `pytest tests/ -v`
2. If any test fails, diagnose the root cause and fix it before proceeding.
3. Update the story checkboxes (`- [x]`) in `MIGRATION_STORIES.md` once all acceptance criteria and tests pass.
4. Present a concise summary of files created/modified and test results.

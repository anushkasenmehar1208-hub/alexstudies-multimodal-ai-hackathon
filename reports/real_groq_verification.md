# Real Groq Verification

Date: 2026-10-13
Environment: isolated local workspace and local PostgreSQL only
Model: `openai/gpt-oss-20b` through Groq's OpenAI-compatible API

No credential value is stored in this report.

## Supported question

- Fixture: a synthetic one-page PDF describing cellular respiration.
- Question: `Where does glycolysis occur?`
- Result: PASS.
- Returned answer: `Glycolysis occurs in the cytoplasm.`
- Relevance: the answer matches the known source statement.
- Citation: PASS. The returned citation referenced the retrieved source unit for the PDF and page 1.
- Citation validation: the cited unit existed, belonged to the authenticated owner, matched the persisted asset and page locator, and appeared in `retrieved_unit_ids`.
- Invented citation IDs: none.

## Unsupported question

- Question: `Who painted the Mona Lisa?`
- Result: PASS.
- `supported`: false.
- Citations: empty.
- Retrieved units: empty.
- Provider call: skipped because retrieval found no supporting unit.

## Authenticated browser workflow

- Local sign-in request: HTTP 200.
- `/track-d` loaded under the temporary authenticated account.
- The uploaded PDF appeared in the processed-source list.
- The supported answer and page-1 citation rendered in the browser.
- The unsupported question rendered the refusal with no citation.
- Result: PASS.

## Scope

This was a two-question smoke test. It verifies the real provider connection, one grounded answer, citation integrity, refusal behavior, and the authenticated browser path. It does not establish broad answer quality across subjects or source formats.

The temporary account, source record, fixture file, and local sessions were removed after verification. Local services and the isolated PostgreSQL process were stopped.

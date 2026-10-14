# Alex Studies — Source-Grounded Adaptive Learning

Alex Studies is a university learning platform extended for the **Multimodal AI Hackathon 2026, Track D: Personalized Tutoring & Adaptive Learning**. The Track D prototype turns a student's lecture videos, PDF textbooks, and PowerPoint slides into an owner-isolated knowledge base. Students can ask questions, inspect exact citations, complete cited assessments, and see topic mastery change from their answers.

The hackathon interface is available at `/track-d` after local sign-in.

## Project overview

The prototype adds a dedicated, source-grounded learning path to the existing Alex Studies application. Its scope is intentionally narrow: ingest a student's own learning material, preserve exact source locations, retrieve evidence within that student's account, answer with validated citations, and turn the same evidence into adaptive practice. The Track D pipeline runs locally with a dedicated PostgreSQL database and keeps provider credentials on the backend.

## Track D problem and solution

Students often study from several disconnected sources. A general chatbot can answer fluently while losing the connection to the lecture, page, or slide the student is expected to learn.

The Track D prototype addresses that problem with a bounded pipeline:

1. Ingest a PDF, PPTX, or captioned YouTube lecture without flattening its location boundaries.
2. Normalize each page, slide, or transcript segment into a source unit.
3. Retrieve only the signed-in student's units with PostgreSQL full-text search.
4. Give Groq only the retrieved units and require structured source-unit citations.
5. Validate every citation against the retrieved set before returning an answer.
6. Refuse questions that the uploaded sources do not support.
7. Generate cited MCQ, short-answer, and numerical practice and update transparent per-topic mastery scores.

## Architecture

```mermaid
flowchart LR
    UI[Next.js /track-d UI] -->|authenticated requests| API[Reflex / Starlette API]
    API --> INGEST[Format-specific ingestion]
    INGEST --> KB[(Local PostgreSQL)]
    PDF[PDF pages and figures] --> INGEST
    PPTX[PPTX slides, tables, notes, images] --> INGEST
    YT[YouTube transcript segments] --> INGEST
    UI -->|question| RETRIEVE[Owner-scoped full-text retrieval]
    RETRIEVE --> KB
    RETRIEVE --> GROQ[Groq grounded completion]
    GROQ --> VALIDATE[Server-side citation validation]
    VALIDATE --> UI
    KB --> ASSESS[Cited assessment and mastery engine]
    ASSESS --> UI
```

The Next.js frontend proxies Track D requests to the existing Reflex/Starlette backend. Authentication reuses Alex Studies account sessions. Every source, retrieval query, assessment, and mastery record is scoped by `owner_id` in the database query itself.

## Supported inputs

| Input | Preserved source location | Extracted content |
| --- | --- | --- |
| PDF | Page number and page dimensions | Page text and embedded figures associated with their source page |
| PPTX | Slide number | Slide text, tables, speaker notes, embedded images |
| YouTube | Video ID, original URL, start and end seconds | Individual caption segments |

Uploads are limited to 25 MB. PPTX archives also have a 150 MB expanded-size limit. Duplicate content is rejected per owner using content hashes.

Extracted images retain page or slide relationships. A provider-neutral visual-analysis interface supports local OCR through macOS Vision or an installed Tesseract binary. OCR records recognized text only; it does not invent diagram meaning. Missing engines and unreadable images are marked unavailable.

PDF handling uses the BSD-3-Clause-licensed `pypdf` library for text and embedded-image extraction. The existing scanned-page OCR fallback uses `pypdfium2`, distributed under Apache-2.0 or BSD-3-Clause terms with its bundled PDFium third-party notices. The replacement preserves page citations, dimensions, image-to-page relationships, and OCR input. Embedded-image placement bounding boxes are not available through this extraction path.

## Grounded tutoring and citations

`SourceRetriever` uses PostgreSQL `to_tsvector`, `websearch_to_tsquery`, ranking, and highlighted excerpts. It applies the owner filter before results leave the database.

The tutor sends retrieved unit IDs and text to Groq using the existing OpenAI-compatible provider layer. The response must be structured JSON. The server accepts a citation only when its ID appears in the retrieved set, then constructs the final locator itself:

- YouTube: original video URL with `t=<seconds>`
- PDF: exact page number
- PPTX: exact slide number

No matching source units means an immediate refusal without calling the model. Invalid citations and provider failures return safe errors rather than uncited answers.

## Adaptive assessment and mastery

The assessment engine creates three question types from source statements:

- multiple choice;
- short answer;
- numerical.

Each question stores a source-unit citation, topic tag, difficulty, diagnostic flag, and fingerprint. The fingerprint prevents repeated generation for the same owner. Answers receive cited feedback.

Topic mastery is intentionally transparent:

```text
new mastery = (previous mastery × previous attempts + current score × 100)
              / total attempts
```

Topics below 70% are marked weak and receive a recommendation to review their cited material.

## What existed before the hackathon

Alex Studies existed before Multimodal AI Hackathon 2026. It already included the main Reflex learning workspace, university curriculum views, authentication, chat and voice tutoring, YouTube learning tools, PDF-related utilities, notes, quizzes, onboarding, and a Next.js frontend/proxy.

The following functionality was developed separately in the isolated hackathon workspace for Track D:

- the unified `SourceAsset`, `SourceUnit`, and `SourceVisual` schema;
- timestamp-preserving YouTube ingestion;
- page-preserving PDF and slide-preserving PPTX ingestion;
- image extraction and the provider-neutral local OCR foundation;
- owner-scoped PostgreSQL full-text retrieval;
- the strict grounded-tutor endpoint and server-validated citations;
- deterministic cited assessments, duplicate prevention, and mastery tracking;
- the `/track-d` interface, migrations, evaluation fixtures, and Track D tests.

AI coding assistants were used during implementation for code drafting, debugging, test design, and documentation. All reported behavior was checked through local tests or explicit real-provider/browser verification; no generated result is presented as measured evidence without a corresponding run.

## Local installation

### Prerequisites

- Python 3.12 or newer
- Node.js 20.9 or newer
- PostgreSQL 15 or newer
- A separate Groq development key for a real tutoring response

### 1. Create the environment

```bash
git clone https://github.com/anushkasenmehar1208-hub/alexstudies-multimodal-ai-hackathon.git
cd alexstudies-multimodal-ai-hackathon

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cd next-app
npm ci
cd ..
```

### 2. Start an isolated PostgreSQL database

One reproducible option is a local Docker container:

```bash
docker run --name alexstudies-track-d-postgres \
  -e POSTGRES_USER=alexstudies \
  -e POSTGRES_PASSWORD=change-me \
  -e POSTGRES_DB=alexstudies_hackathon \
  -p 55432:5432 \
  -d postgres:16
```

Copy the template and replace local placeholders. Never reuse production credentials.

```bash
cp .env.example .env
```

The required database setting is:

```dotenv
DATABASE_URL=postgresql://alexstudies:change-me@127.0.0.1:55432/alexstudies_hackathon
```

Tests contain a safety gate and refuse any database that is not `alexstudies_hackathon` on localhost port `55432`.

### 3. Apply migrations

```bash
set -a
source .env
set +a
alembic upgrade head
alembic current
```

The expected head revision is `20261013_03`.

### 4. Start the backend and frontend

In terminal one:

```bash
source .venv/bin/activate
set -a; source .env; set +a
reflex run --backend-only --env dev
```

In terminal two:

```bash
cd next-app
set -a; source ../.env; set +a
npm run dev
```

Open `http://localhost:3000/track-d`, create or use a local-only account, and sign in.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Yes | Dedicated local PostgreSQL connection |
| `SESSION_SECRET` | Yes | Local session and signing secret |
| `APP_BASE_URL` | Yes | Local Next.js origin |
| `REFLEX_BACKEND_URL` | Yes | Backend origin used by the Next.js proxy |
| `ENFORCE_HTTPS` | Local: `false` | Allows localhost HTTP during development |
| `ALEX_DEMO_FREE_MODE` | Yes | Blocks paid-provider fallbacks in the demo path |
| `ALEX_TEXT_PROVIDER` | Yes | Set to `groq` for Track D tutoring |
| `GROQ_API_KEY` | Real AI only | Server-side Groq development credential |
| `GROQ_BASE_URL` | Yes | Groq OpenAI-compatible API base URL |
| `GROQ_TEXT_MODEL` | Yes | Grounded tutoring model |
| `GROQ_STT_MODEL` | Voice only | Existing voice transcription model |
| `SUPADATA_API_KEY` | Optional | Cloud transcript source when direct YouTube captions are unavailable |
| `ALEX_VISION_OCR_BIN` | Optional | Precompiled local OCR executable override |

Provider keys are server-only. Never prefix them with `NEXT_PUBLIC_`.

## Evaluation

The reproducible deterministic evaluation is run with:

```bash
set -a; source .env; set +a
python tools/evaluate_track_d.py
```

The current report at [`reports/track_d_evaluation.json`](reports/track_d_evaluation.json) contains:

| Metric | Result | Dataset |
| --- | ---: | --- |
| Retrieval hit rate | 1.00 | 9 queries across 3 synthetic sources |
| Mean reciprocal rank | 1.00 | 9 queries |
| Context precision@3 | 1.00 | 9 queries |
| Context recall@3 | 1.00 | 9 queries |
| Citation validity | 1.00 | 7 generated assessment questions |
| Question repetition rate | 0.00 | 7 questions |
| Unsupported-question refusal | Passed | 1 deterministic refusal case |
| Mastery after one correct and one wrong answer | 50% | 2 simulated attempts |

A separate real-provider verification used `openai/gpt-oss-20b` through Groq. One supported PDF question returned a relevant answer with a valid page-1 source-unit citation, and one unsupported question was refused with no citations. The same flow passed through an authenticated browser session. This is a two-question smoke test, not a broad model-quality benchmark. See [`reports/real_groq_verification.md`](reports/real_groq_verification.md).

## Testing

```bash
set -a; source .env; set +a
python -m unittest discover -s tests -p 'test_*.py'
node --test next-app/tests/regressions.cjs tests/test_voice_auth.cjs tests/test_browser_tts.cjs

cd next-app
npm run lint
npx tsc --noEmit
npm run build
```

## Known limitations

- PostgreSQL lexical retrieval does not provide semantic matching for paraphrases with no shared searchable terms.
- The real Groq validation contains one supported and one unsupported question; larger human-reviewed evaluation is still needed.
- Local OCR recognizes text but does not interpret diagrams, charts, or equations semantically.
- macOS Vision OCR is platform-specific; other systems need a local Tesseract executable.
- YouTube ingestion requires available captions and may be affected by upstream access restrictions. Supadata is optional and may have its own limits.
- Assessment generation is deterministic and source-grounded, but question quality varies with extracted text quality.
- PDF citation links identify exact pages but do not yet open a built-in page-highlight viewer.
- PPTX citations identify exact slides but do not render slide previews inside the application.

## Submission materials

- [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) — a timed 3–5 minute recording script
- [`docs/DEVPOST_SUBMISSION.md`](docs/DEVPOST_SUBMISSION.md) — prepared Devpost description
- [`reports/track_d_evaluation.json`](reports/track_d_evaluation.json) — reproducible deterministic metrics
- [`reports/real_groq_verification.md`](reports/real_groq_verification.md) — bounded real-provider verification record

No production database, production credential, deployment, or Devpost submission is required to run or review the isolated Track D prototype.

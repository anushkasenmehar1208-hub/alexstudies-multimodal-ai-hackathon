# Devpost Submission Draft

## Project name

**Alex Studies — Source-Grounded Adaptive Learning**

## Tagline

Turn lectures, textbooks, and slides into a private tutor that answers with exact citations and adapts practice to each learner.

## Inspiration

University students rarely learn from one clean source. A single topic may be split across a lecture recording, textbook pages, and slide decks. General-purpose AI can explain the topic, but it may answer beyond the assigned material or provide citations that do not lead back to the student's source.

We wanted Alex to behave more like a careful personal tutor: first find the student's evidence, then answer, prove where the answer came from, and use assessment results to decide what the student should review next.

## What it does

Alex Studies accepts three learning formats in one Track D workspace:

- PDF textbooks, preserved page by page with embedded figures;
- PowerPoint decks, preserved slide by slide with text, tables, notes, and images;
- captioned YouTube lectures, preserved as timestamped transcript segments.

Students can search all uploaded material and ask a question. PostgreSQL retrieves relevant source units belonging only to the signed-in student. Groq generates a response from those units, and the backend validates every returned citation ID before displaying the answer. PDF citations identify the exact page, PPTX citations identify the slide, and YouTube citations open the original video at the supporting timestamp.

If the sources do not support a question, Alex refuses without calling the model.

The same knowledge base powers adaptive diagnostic and practice questions in MCQ, short-answer, and numerical formats. Every question includes a verified source citation. Fingerprints prevent duplicate questions, and a transparent running-average calculation updates per-topic mastery. Topics below 70% are marked weak and linked back to the material the student should review.

## How we built it

The frontend is Next.js and the existing Alex Studies learning application uses Python/Reflex with a Starlette API. We added a separate Track D pipeline backed by PostgreSQL and Alembic migrations.

`pypdf` extracts PDF pages and embedded images, while `pypdfium2` renders scanned pages for the existing OCR fallback. `python-pptx` extracts slides, tables, notes, and embedded images. Existing YouTube transcript strategies were extended to preserve segment timestamps. A provider-neutral visual interface runs local OCR with macOS Vision or Tesseract when available and explicitly reports unavailable analysis instead of inventing diagram descriptions.

PostgreSQL full-text search performs owner-scoped retrieval. Groq is accessed through its OpenAI-compatible API using `openai/gpt-oss-20b`. The model receives retrieved source-unit IDs and content and must return structured JSON. The server checks every citation against the retrieved units and constructs the final source link from stored metadata.

## Challenges

The hardest part was preserving evidence boundaries across very different formats. Flattening a transcript or document would make exact citations impossible, so the shared model treats each page, slide, and timestamped segment as a first-class source unit.

We also had to keep model output subordinate to stored evidence. Citation IDs are never trusted directly, unsupported questions bypass the provider, and ownership is enforced in the retrieval query itself.

## Accomplishments

- One normalized, owner-isolated knowledge base for PDF, PPTX, and YouTube.
- Exact page, slide, and timestamp citations validated server-side.
- A real Groq grounded answer verified through the authenticated browser workflow.
- Safe unsupported-question refusal with no paid fallback.
- Cited MCQ, short-answer, and numerical assessments.
- Duplicate prevention, per-topic mastery, and weak-topic recommendations.
- Local OCR that reports its limits instead of claiming unsupported visual understanding.

## Evaluation

Our reproducible fixture contains nine retrieval queries across three synthetic sources. The current run measured:

- retrieval hit rate: 1.00;
- mean reciprocal rank: 1.00;
- context precision@3: 1.00;
- context recall@3: 1.00;
- citation validity: 1.00 across seven generated assessment questions;
- question repetition rate: 0.00;
- unsupported-question refusal: passed;
- mastery after one correct and one incorrect attempt: 50%.

We separately ran a real Groq smoke test with one supported PDF question and one unsupported question. The supported answer was relevant, cited the correct source unit and page, and contained no invented citation ID. The unsupported question was refused without citations. Both behaviors were confirmed through an authenticated local browser session. We report this as a bounded smoke test rather than a general model-quality score.

## What we learned

Source-grounded learning depends as much on data modeling and validation as on the language model. Exact locators, owner filters, deterministic refusal, and transparent scoring make the experience easier to trust and evaluate.

## What's next

- add a larger human-reviewed evaluation set;
- add semantic retrieval while retaining PostgreSQL owner filters;
- add in-app PDF page highlighting and PPTX slide previews;
- improve equation and diagram interpretation with a separately evaluated visual model;
- use mastery and prerequisites to sequence the next lesson rather than only recommend review.

## Prior work and AI assistance disclosure

Alex Studies existed before this hackathon. Pre-existing features included the main university learning workspace, authentication, curriculum views, chat and voice tutoring, YouTube learning tools, notes, quizzes, onboarding, and the Next.js proxy/frontend.

The unified source schema, location-preserving PDF/PPTX/YouTube ingestion, visual extraction foundation, owner-scoped retrieval, grounded Track D tutor, verified citation system, adaptive assessments, mastery tracking, `/track-d` interface, migrations, evaluation fixtures, and Track D tests were developed separately in an isolated workspace for Multimodal AI Hackathon 2026.

AI coding assistants were used for implementation support, debugging, test design, and documentation. Reported results come from executed local tests and explicit provider/browser verification.

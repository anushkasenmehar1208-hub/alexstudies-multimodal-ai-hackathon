# Alex Studies Track D — Three-Minute Demo Script

## Before recording

- Use only the isolated PostgreSQL database on `127.0.0.1:55432/alexstudies_hackathon`.
- Confirm `alembic current` reports `20261013_03` and use a disposable local account.
- Run `python tools/create_track_d_demo_fixtures.py`. This creates a two-page
  photosynthesis PDF and two-slide momentum deck under ignored `.local-data`.
- Prepare the captioned Khan Academy lecture
  `https://www.youtube.com/watch?v=PSGKRd7Bbl0`. Recheck caption availability
  from the demo network before recording; do not claim ingestion if YouTube blocks it.
- Load the separate development Groq key server-side. Keep terminals and environment files out of the recording.

## 0:00–0:20 — Problem and promise

**Show:** `/track-d`.

> Students learn from lectures, textbooks, and slides, but ordinary chatbots can lose the connection to those sources. Alex Studies creates one private knowledge base and shows the exact page, slide, or video timestamp behind every supported answer and question.

## 0:20–0:55 — Three source formats

1. Upload `.local-data/demo-fixtures/photosynthesis-textbook.pdf` and point out its two page units.
2. Upload `.local-data/demo-fixtures/momentum-slides.pptx` and point out its two slide units.
3. Add `https://www.youtube.com/watch?v=PSGKRd7Bbl0` and show that transcript timestamps are retained.

> The sources use one normalized structure without flattening page, slide, or timestamp boundaries.

## 0:55–1:25 — Grounded tutoring

1. Ask **What do chloroplast membranes perform, and what do those reactions produce?**
2. Expand the citation and show its excerpt and exact page.
3. Open a YouTube citation to show its timestamp link, or show the exact PPTX slide reference.

> Groq receives only retrieved source units. The server accepts only citation IDs from that retrieved set and builds the final locator from stored source data.

## 1:25–1:40 — Unsupported-question refusal

Ask a clearly unrelated question, such as **Who painted the Mona Lisa?** Show the refusal and absence of citations.

> With no supporting source unit, Alex refuses before calling the model.

## 1:40–2:45 — Visible adaptive learning cycle

1. Click **Run diagnostic**.
2. Expand a question citation, deliberately answer it incorrectly, and show the source-backed explanation.
3. Point to the mastery score below 70% and the automatically selected **Next adaptive step**.
4. Show that the panel names the weakest topic, current mastery, and selected difficulty.
5. Answer the cited follow-up correctly.
6. Show the updated mastery score and the next cited question. Explain the bands: below 40% is easy, 40–69% is medium, and 70% or higher is hard.

> The next step is selected from the student's lowest mastery topic. Each answer updates a transparent running score, changes the difficulty band, and produces another question grounded in that student's uploaded material.

## 2:45–3:00 — Evidence and scope

Show the evaluation summary in the README.

> Retrieval, citation validity, refusal, ownership isolation, and the adaptive cycle are covered by reproducible tests. The real Groq result is a bounded smoke test. Alex Studies existed before this hackathon; the Track D source pipeline, grounded tutor, and adaptive interface were built separately and the repository discloses AI-assistant use.

End on the Track D screen with source cards, a citation, mastery, and the adaptive follow-up visible.

## Recording guardrails

- Never show `.env`, browser storage, tokens, database credentials, or provider dashboards.
- Do not claim measured learning improvement; show deterministic product behavior only.
- Do not claim semantic diagram understanding; the visual path extracts images and performs local OCR.
- Describe the real Groq run as a smoke test, not a broad quality benchmark.
- If captions are unavailable, state the upstream limitation and continue with PDF/PPTX rather than fabricating success.

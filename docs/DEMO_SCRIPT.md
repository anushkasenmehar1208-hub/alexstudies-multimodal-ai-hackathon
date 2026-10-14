# Alex Studies Track D — 3–5 Minute Demo Script

## Before recording

- Use only the isolated local PostgreSQL database on `127.0.0.1:55432/alexstudies_hackathon`.
- Confirm `alembic current` reports `20261013_03`.
- Use a fresh local demo account and three small, permission-safe sources:
  - a PDF with a clear fact on a known page;
  - a PPTX with a fact on a known slide;
  - a captioned YouTube lecture with a memorable timestamp.
- Confirm the separate development Groq key is loaded server-side. Keep terminals and environment files out of the recording.
- Preload the files in Finder but do not pre-ingest them.

## 0:00–0:25 — Problem and promise

**Show:** `/track-d` landing state.

**Say:**

> Students learn from lectures, textbooks, and slides, but ordinary chatbots can lose the connection to those sources. Alex Studies turns all three into one private knowledge base, answers only from retrieved evidence, and shows the exact page, slide, or video timestamp behind the answer.

## 0:25–1:20 — Multimodal ingestion

**PDF**

1. Upload the prepared PDF.
2. Point out the processed source card and its page/source-unit count.
3. Explain that text is stored page by page and figures keep their page relationship.

**PPTX**

1. Upload the prepared deck.
2. Point out its slide/source-unit and visual counts.
3. Explain that slide text, tables, speaker notes, and embedded images are extracted without losing the slide number.

**YouTube**

1. Paste the prepared captioned lecture URL.
2. Click **Add lecture** and wait for the processed source card.
3. Explain that transcript segments retain start and end timestamps rather than becoming one untraceable string.

## 1:20–2:15 — Real grounded tutoring and verified citations

1. Ask the prepared PDF-supported question.
2. Read the concise Groq response.
3. Expand its citation and show the source excerpt and exact PDF page.
4. Ask one PPTX- or YouTube-supported question.
5. Open the YouTube citation to demonstrate the timestamp link, or point to the exact slide reference.

**Say:**

> Groq receives only the retrieved source units. It returns structured citation IDs, and the server rejects any ID that was not retrieved. The final page, slide, and timestamp links are built from the stored source locations, not invented by the model.

## 2:15–2:40 — Unsupported-question refusal

1. Ask a clearly unrelated question, such as **Who painted the Mona Lisa?**
2. Show: **I can’t answer that from your uploaded sources.**
3. Point out that there are no citations.

**Say:**

> When retrieval finds no supporting unit, Alex refuses before calling the model. This keeps the tutor bounded to the student's material.

## 2:40–3:40 — Adaptive assessment and mastery

1. Click **Run diagnostic**.
2. Show the MCQ, short-answer, and numerical formats.
3. Expand one question's citation.
4. Submit one correct answer and show cited feedback plus 100% mastery.
5. Submit an incorrect answer for the same topic and show mastery update to 50% and the weak-topic recommendation.

**Say:**

> Every question is tied to a source unit. Duplicate fingerprints prevent repeated questions. Mastery is a transparent running average of scored attempts, and topics below 70% receive a source-backed review recommendation.

## 3:40–4:10 — Privacy, evaluation, and close

**Show:** the evaluation table in the README.

**Say:**

> All retrieval and progress queries are owner-scoped. On nine deterministic retrieval cases across PDF, PPTX, and YouTube, the current fixture achieved a 100% hit rate, mean reciprocal rank, context precision at three, context recall at three, and citation validity. A separate real Groq browser smoke test passed one supported question with a verified page citation and refused one unsupported question. Alex Studies existed before the hackathon; this unified source pipeline, grounded tutor, and adaptive Track D interface were developed separately for this submission with AI coding assistants disclosed in the repository.

End on the `/track-d` screen with the three source cards, a cited answer, and mastery visible.

## Recording guardrails

- Do not show `.env`, browser storage, tokens, database URLs containing passwords, or provider dashboards.
- Do not claim semantic diagram understanding; the current visual path extracts images and performs local OCR only.
- Describe the two-question real Groq check as a smoke test, not a broad quality benchmark.
- If YouTube captions are temporarily unavailable, explain the upstream caption dependency and continue with the already verified PDF/PPTX flow rather than fabricating success.

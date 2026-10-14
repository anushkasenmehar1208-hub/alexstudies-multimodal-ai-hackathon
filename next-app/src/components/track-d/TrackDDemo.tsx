"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { readBrowserToken } from "@/lib/browser-storage";

type Source = { id: number; title: string; source_type: string; extraction_status: string; unit_count: number; visual_count: number; ocr_complete_count: number };
type Citation = { source_unit_id: number; source_type: string; source_title: string; label: string; link?: string | null; excerpt: string; locator: Record<string, unknown> };
type Question = { id: number; question_type: "mcq" | "short_answer" | "numerical"; prompt: string; options: string[]; topic_tag: string; difficulty: string; citation: Citation; diagnostic: boolean };
type Mastery = { topic_tag: string; mastery_score: number; attempt_count: number; weak: boolean; recommendation: string };

async function api<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "X-Auth-Token": token, ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...init?.headers },
  });
  const payload = await response.json().catch(() => ({})) as T & { error?: string };
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function CitationView({ citation }: { citation: Citation }) {
  const content = <><strong>{citation.label}</strong><span>{citation.source_title}</span></>;
  return (
    <details className="rounded-lg border border-cyan-400/25 bg-cyan-400/5 p-3 text-sm">
      <summary className="flex cursor-pointer items-center justify-between gap-3 text-cyan-100">
        {citation.link ? <a href={citation.link} target="_blank" rel="noreferrer" className="flex flex-col hover:underline" onClick={(event) => event.stopPropagation()}>{content}</a> : <span className="flex flex-col">{content}</span>}
        <span className="text-xs uppercase text-cyan-300">{citation.source_type}</span>
      </summary>
      <p className="mt-2 leading-6 text-slate-300">{citation.excerpt}</p>
    </details>
  );
}

export function TrackDDemo() {
  const [token, setToken] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [mastery, setMastery] = useState<Mastery[]>([]);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [responses, setResponses] = useState<Record<number, string>>({});
  const [feedback, setFeedback] = useState<Record<number, string>>({});
  const [status, setStatus] = useState("Ready");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async (authToken: string) => {
    const [sourceData, questionData, masteryData] = await Promise.all([
      api<{ sources: Source[] }>("/api/track-d/sources", authToken),
      api<{ questions: Question[] }>("/api/track-d/assessments", authToken),
      api<{ mastery: Mastery[] }>("/api/track-d/mastery", authToken),
    ]);
    setSources(sourceData.sources); setQuestions(questionData.questions); setMastery(masteryData.mastery);
  }, []);

  useEffect(() => {
    const authToken = readBrowserToken("_auth_token");
    setToken(authToken);
    if (authToken) refresh(authToken).catch((error: Error) => setStatus(error.message));
  }, [refresh]);

  async function upload(kind: "pdf" | "pptx", file?: File) {
    if (!file || !token) return;
    const form = new FormData(); form.append("file", file);
    setBusy(true); setStatus(`Processing ${file.name}…`);
    try { await api(`/api/track-d/sources/${kind}`, token, { method: "POST", body: form }); await refresh(token); setStatus(`${file.name} processed with exact source locations.`); }
    catch (error) { setStatus(error instanceof Error ? error.message : "Upload failed."); }
    finally { setBusy(false); }
  }

  async function addYoutube(event: FormEvent) {
    event.preventDefault(); if (!youtubeUrl.trim() || !token) return;
    setBusy(true); setStatus("Loading timestamped transcript…");
    try { await api("/api/track-d/sources/youtube", token, { method: "POST", body: JSON.stringify({ url: youtubeUrl }) }); setYoutubeUrl(""); await refresh(token); setStatus("Lecture transcript processed."); }
    catch (error) { setStatus(error instanceof Error ? error.message : "Video processing failed."); }
    finally { setBusy(false); }
  }

  async function ask(event: FormEvent) {
    event.preventDefault(); if (!question.trim() || !token) return;
    setBusy(true); setStatus("Retrieving source evidence…"); setAnswer(""); setCitations([]);
    try { const result = await api<{ answer: string; citations: Citation[] }>("/api/track-d/tutor", token, { method: "POST", body: JSON.stringify({ question }) }); setAnswer(result.answer); setCitations(result.citations); setStatus("Answer checked against retrieved source units."); }
    catch (error) { setStatus(error instanceof Error ? error.message : "Tutor unavailable."); }
    finally { setBusy(false); }
  }

  async function generate(diagnostic: boolean) {
    if (!token) return; setBusy(true); setStatus(diagnostic ? "Building diagnostic…" : "Building cited practice…");
    try { const data = await api<{ questions: Question[] }>("/api/track-d/assessments", token, { method: "POST", body: JSON.stringify({ limit: 9, diagnostic }) }); setQuestions(data.questions); setStatus("Assessment ready. Every question includes source evidence."); }
    catch (error) { setStatus(error instanceof Error ? error.message : "Assessment unavailable."); }
    finally { setBusy(false); }
  }

  async function submit(questionId: number) {
    const submitted = responses[questionId]?.trim(); if (!submitted || !token) return;
    try { const result = await api<{ feedback: string }>(`/api/track-d/assessments/${questionId}/answer`, token, { method: "POST", body: JSON.stringify({ answer: submitted }) }); setFeedback((value) => ({ ...value, [questionId]: result.feedback })); await refresh(token); }
    catch (error) { setFeedback((value) => ({ ...value, [questionId]: error instanceof Error ? error.message : "Answer could not be checked." })); }
  }

  if (!token) return <main className="min-h-screen bg-slate-950 px-6 py-20 text-white"><div className="mx-auto max-w-xl rounded-2xl border border-white/10 bg-white/5 p-8"><h1 className="text-3xl font-semibold">Track D Learning Lab</h1><p className="mt-4 text-slate-300">Sign in to keep uploaded material and progress isolated to your account.</p><a href="/login" className="mt-6 inline-block rounded-lg bg-cyan-400 px-5 py-3 font-semibold text-slate-950">Sign in</a></div></main>;

  return <main className="min-h-screen bg-slate-950 px-4 py-10 text-white sm:px-8">
    <div className="mx-auto max-w-7xl space-y-8">
      <header><p className="text-sm font-semibold uppercase tracking-[.25em] text-cyan-300">Track D demonstration</p><h1 className="mt-2 text-4xl font-semibold">Source-grounded learning lab</h1><p className="mt-3 max-w-3xl text-slate-300">Bring a lecture, textbook, or slide deck. Alex retrieves exact source units before answering or assessing you.</p></header>
      <div role="status" className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">{busy ? "Working · " : ""}{status}</div>
      <section className="grid gap-4 lg:grid-cols-3">
        {(["pdf", "pptx"] as const).map((kind) => <label key={kind} className="cursor-pointer rounded-2xl border border-white/10 bg-white/5 p-5 hover:border-cyan-300/50"><span className="font-semibold">Upload {kind.toUpperCase()}</span><span className="mt-2 block text-sm text-slate-400">Preserves {kind === "pdf" ? "pages and figures" : "slides, tables, notes, and images"}.</span><input disabled={busy} className="mt-4 block w-full text-sm" type="file" accept={kind === "pdf" ? ".pdf,application/pdf" : ".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"} onChange={(event) => upload(kind, event.target.files?.[0])} /></label>)}
        <form onSubmit={addYoutube} className="rounded-2xl border border-white/10 bg-white/5 p-5"><label className="font-semibold" htmlFor="youtube-url">YouTube lecture</label><p className="mt-2 text-sm text-slate-400">Preserves transcript timestamps.</p><input id="youtube-url" value={youtubeUrl} onChange={(event) => setYoutubeUrl(event.target.value)} className="mt-4 w-full rounded-lg border border-white/10 bg-slate-900 px-3 py-2" placeholder="https://youtube.com/watch?v=…" /><button disabled={busy} className="mt-3 rounded-lg bg-cyan-400 px-4 py-2 font-semibold text-slate-950">Add lecture</button></form>
      </section>
      <section><h2 className="text-xl font-semibold">Processed sources</h2><div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{sources.length ? sources.map((source) => <article key={source.id} className="rounded-xl border border-white/10 bg-white/5 p-4"><div className="flex justify-between"><strong>{source.title}</strong><span className="text-xs uppercase text-cyan-300">{source.source_type}</span></div><p className="mt-2 text-sm text-slate-400">{source.unit_count} source units · {source.visual_count} visuals · {source.extraction_status}</p></article>) : <p className="text-slate-400">No material uploaded yet.</p>}</div></section>
      <section className="grid gap-6 lg:grid-cols-[1.3fr_.7fr]"><div className="rounded-2xl border border-white/10 bg-white/5 p-5"><h2 className="text-xl font-semibold">Ask your material</h2><form onSubmit={ask} className="mt-4 flex gap-2"><input value={question} onChange={(event) => setQuestion(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-white/10 bg-slate-900 px-3 py-2" placeholder="What does the lecture say about…?" /><button disabled={busy} className="rounded-lg bg-cyan-400 px-4 py-2 font-semibold text-slate-950">Ask</button></form>{answer && <div className="mt-5"><p className="leading-7 text-slate-100">{answer}</p><div className="mt-4 space-y-2">{citations.map((citation) => <CitationView key={citation.source_unit_id} citation={citation} />)}</div></div>}</div>
        <div className="rounded-2xl border border-white/10 bg-white/5 p-5"><h2 className="text-xl font-semibold">Topic mastery</h2><div className="mt-4 space-y-4">{mastery.length ? mastery.map((item) => <div key={item.topic_tag}><div className="flex justify-between text-sm"><span>{item.topic_tag}</span><span>{item.mastery_score.toFixed(0)}%</span></div><div className="mt-1 h-2 rounded bg-slate-800"><div className="h-2 rounded bg-cyan-400" style={{ width: `${item.mastery_score}%` }} /></div><p className="mt-1 text-xs text-slate-400">{item.recommendation}</p></div>) : <p className="text-sm text-slate-400">Answer cited questions to begin tracking mastery.</p>}</div></div></section>
      <section><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">Adaptive assessment</h2><div className="flex gap-2"><button onClick={() => generate(false)} disabled={busy} className="rounded-lg border border-cyan-300/40 px-4 py-2">Generate practice</button><button onClick={() => generate(true)} disabled={busy} className="rounded-lg bg-cyan-400 px-4 py-2 font-semibold text-slate-950">Run diagnostic</button></div></div><div className="mt-4 grid gap-4 lg:grid-cols-2">{questions.map((item) => <article key={item.id} className="rounded-2xl border border-white/10 bg-white/5 p-5"><div className="flex gap-2 text-xs uppercase text-cyan-300"><span>{item.question_type.replace("_", " ")}</span><span>·</span><span>{item.difficulty}</span><span>·</span><span>{item.topic_tag}</span></div><p className="mt-3 font-medium">{item.prompt}</p>{item.question_type === "mcq" ? <div className="mt-3 space-y-2">{item.options.map((option) => <label key={option} className="flex gap-2 text-sm"><input type="radio" name={`q-${item.id}`} checked={responses[item.id] === option} onChange={() => setResponses((value) => ({ ...value, [item.id]: option }))} />{option}</label>)}</div> : <input value={responses[item.id] || ""} onChange={(event) => setResponses((value) => ({ ...value, [item.id]: event.target.value }))} className="mt-3 w-full rounded-lg border border-white/10 bg-slate-900 px-3 py-2" placeholder={item.question_type === "numerical" ? "Enter the value" : "Write a concise source-based answer"} />}<button onClick={() => submit(item.id)} className="mt-3 rounded-lg bg-white px-3 py-2 text-sm font-semibold text-slate-950">Check answer</button>{feedback[item.id] && <p className="mt-3 text-sm text-amber-100">{feedback[item.id]}</p>}<div className="mt-4"><CitationView citation={item.citation} /></div></article>)}</div></section>
    </div>
  </main>;
}

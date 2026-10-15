"use client";

import { FormEvent, ReactNode, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  BrainCircuit,
  CircleGauge,
  FileText,
  GraduationCap,
  Home,
  Library,
  Menu,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
  Presentation,
  Search,
  Sparkles,
  UploadCloud,
  UserRound,
  X,
  Youtube,
} from "lucide-react";
import { readBrowserToken } from "@/lib/browser-storage";

type Source = { id: number; title: string; source_type: string; extraction_status: string; unit_count: number; visual_count: number; ocr_complete_count: number };
type Citation = { source_unit_id: number; source_type: string; source_title: string; label: string; link?: string | null; excerpt: string; locator: Record<string, unknown> };
type Question = { id: number; question_type: "mcq" | "short_answer" | "numerical"; prompt: string; options: string[]; topic_tag: string; difficulty: string; citation: Citation; diagnostic: boolean; adaptive: boolean };
type Mastery = { topic_tag: string; mastery_score: number; attempt_count: number; weak: boolean; recommendation: string };
type AdaptiveStep = { question: Question; selected_topic: string; mastery_score: number; difficulty: string; weak: boolean; rationale: string };
type SessionResponse = { authenticated: boolean; user?: { username: string } };

async function api<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (token) headers.set("X-Auth-Token", token);
  if (!(init?.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers, credentials: "same-origin" });
  const payload = await response.json().catch(() => ({})) as T & { error?: string };
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function CitationView({ citation }: { citation: Citation }) {
  const content = <><strong className="text-white/90">{citation.label}</strong><span className="text-white/45">{citation.source_title}</span></>;
  return (
    <details className="group rounded-xl border border-emerald-300/15 bg-emerald-300/[0.045] p-3 text-sm transition hover:border-emerald-300/30">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-emerald-100">
        {citation.link ? <a href={citation.link} target="_blank" rel="noreferrer" className="flex flex-col hover:text-white" onClick={(event) => event.stopPropagation()}>{content}</a> : <span className="flex flex-col">{content}</span>}
        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-emerald-200">{citation.source_type}</span>
      </summary>
      <p className="mt-3 border-t border-white/[0.06] pt-3 leading-6 text-white/60">{citation.excerpt}</p>
    </details>
  );
}

function SidebarItem({ icon, label, href, active = false, expanded, onClick }: { icon: ReactNode; label: string; href: string; active?: boolean; expanded: boolean; onClick?: () => void }) {
  return (
    <a href={href} onClick={onClick} title={!expanded ? label : undefined} aria-label={label} className={`group flex h-11 items-center rounded-xl border transition ${expanded ? "gap-3 px-3" : "justify-center px-0"} ${active ? "border-emerald-300/20 bg-emerald-300/[0.09] text-emerald-100 shadow-[inset_0_1px_0_rgba(255,255,255,.04)]" : "border-transparent text-white/45 hover:border-white/[0.06] hover:bg-white/[0.045] hover:text-white/80"}`}>
      <span className="shrink-0">{icon}</span>{expanded && <span className="truncate text-sm font-medium">{label}</span>}
    </a>
  );
}

function SourceIcon({ type }: { type: string }) {
  if (type === "pdf") return <FileText size={18} />;
  if (type === "pptx") return <Presentation size={18} />;
  return <Youtube size={18} />;
}

export function TrackDDemo() {
  const [token, setToken] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [authReady, setAuthReady] = useState(false);
  const [username, setUsername] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [sources, setSources] = useState<Source[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [mastery, setMastery] = useState<Mastery[]>([]);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [responses, setResponses] = useState<Record<number, string>>({});
  const [feedback, setFeedback] = useState<Record<number, string>>({});
  const [adaptive, setAdaptive] = useState<AdaptiveStep | null>(null);
  const [lastAdaptiveFeedback, setLastAdaptiveFeedback] = useState("");
  const [status, setStatus] = useState("Ready for your material");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async (authToken: string) => {
    const [sourceData, questionData, masteryData] = await Promise.all([
      api<{ sources: Source[] }>("/api/track-d/sources", authToken),
      api<{ questions: Question[] }>("/api/track-d/assessments", authToken),
      api<{ mastery: Mastery[] }>("/api/track-d/mastery", authToken),
    ]);
    setSources(sourceData.sources);
    setQuestions(questionData.questions.filter((item) => !item.adaptive));
    setMastery(masteryData.mastery);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const localToken = readBrowserToken("_auth_token");
      const headers = localToken ? { "X-Auth-Token": localToken } : undefined;
      try {
        const response = await fetch("/api/auth/session", { headers, credentials: "same-origin", cache: "no-store" });
        const session = await response.json().catch(() => ({ authenticated: false })) as SessionResponse;
        if (cancelled) return;
        if (response.ok && session.authenticated) {
          setToken(localToken);
          setAuthenticated(true);
          setUsername(session.user?.username || "Student");
          await refresh(localToken);
        } else {
          setAuthenticated(false);
        }
      } catch {
        if (!cancelled) setStatus("Session check failed. Refresh and try again.");
      } finally {
        if (!cancelled) setAuthReady(true);
      }
    })();
    return () => { cancelled = true; };
  }, [refresh]);

  async function upload(kind: "pdf" | "pptx", file?: File) {
    if (!file || !authenticated) return;
    const form = new FormData(); form.append("file", file);
    setBusy(true); setStatus(`Processing ${file.name}…`);
    try { await api(`/api/track-d/sources/${kind}`, token, { method: "POST", body: form }); await refresh(token); setStatus(`${file.name} processed with exact source locations.`); }
    catch (error) { setStatus(error instanceof Error ? error.message : "Upload failed."); }
    finally { setBusy(false); }
  }

  async function addYoutube(event: FormEvent) {
    event.preventDefault(); if (!youtubeUrl.trim() || !authenticated) return;
    setBusy(true); setStatus("Loading timestamped transcript…");
    try { await api("/api/track-d/sources/youtube", token, { method: "POST", body: JSON.stringify({ url: youtubeUrl }) }); setYoutubeUrl(""); await refresh(token); setStatus("Lecture transcript processed."); }
    catch (error) { setStatus(error instanceof Error ? error.message : "Video processing failed."); }
    finally { setBusy(false); }
  }

  async function ask(event: FormEvent) {
    event.preventDefault(); if (!question.trim() || !authenticated) return;
    setBusy(true); setStatus("Retrieving source evidence…"); setAnswer(""); setCitations([]);
    try { const result = await api<{ answer: string; citations: Citation[] }>("/api/track-d/tutor", token, { method: "POST", body: JSON.stringify({ question }) }); setAnswer(result.answer); setCitations(result.citations); setStatus("Answer checked against retrieved source units."); }
    catch (error) { setStatus(error instanceof Error ? error.message : "Tutor unavailable."); }
    finally { setBusy(false); }
  }

  async function generate(diagnostic: boolean) {
    if (!authenticated) return; setBusy(true); setStatus(diagnostic ? "Building diagnostic…" : "Building cited practice…");
    try { const data = await api<{ questions: Question[] }>("/api/track-d/assessments", token, { method: "POST", body: JSON.stringify({ limit: 9, diagnostic }) }); setQuestions(data.questions); setAdaptive(null); setLastAdaptiveFeedback(""); setStatus(diagnostic ? "Diagnostic ready. Answer a question to start the adaptive cycle." : "Assessment ready. Every question includes source evidence."); }
    catch (error) { setStatus(error instanceof Error ? error.message : "Assessment unavailable."); }
    finally { setBusy(false); }
  }

  async function loadAdaptive() {
    const next = await api<AdaptiveStep>("/api/track-d/assessments/adaptive", token, { method: "POST", body: "{}" });
    setAdaptive(next); setStatus(next.rationale);
  }

  async function submit(questionId: number, isAdaptive = false) {
    const submitted = responses[questionId]?.trim(); if (!submitted || !authenticated) return;
    setBusy(true);
    try {
      const result = await api<{ feedback: string; is_correct: boolean; mastery_score: number }>(`/api/track-d/assessments/${questionId}/answer`, token, { method: "POST", body: JSON.stringify({ answer: submitted }) });
      if (isAdaptive) setLastAdaptiveFeedback(result.feedback); else setFeedback((value) => ({ ...value, [questionId]: result.feedback }));
      try { await refresh(token); await loadAdaptive(); }
      catch (nextError) { setStatus(`Answer saved. ${nextError instanceof Error ? nextError.message : "The next adaptive step is unavailable."}`); }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Answer could not be checked.";
      if (isAdaptive) setLastAdaptiveFeedback(message); else setFeedback((value) => ({ ...value, [questionId]: message }));
    } finally { setBusy(false); }
  }

  function questionCard(item: Question, isAdaptive = false) {
    const message = isAdaptive ? "" : feedback[item.id];
    return <article key={`${isAdaptive ? "adaptive" : "assessment"}-${item.id}`} className={`rounded-2xl border p-5 shadow-[inset_0_1px_0_rgba(255,255,255,.025)] ${isAdaptive ? "border-amber-300/25 bg-amber-300/[0.055]" : "border-white/[0.07] bg-white/[0.025]"}`}>
      <div className="flex flex-wrap gap-2 text-[10px] font-bold uppercase tracking-[.16em] text-emerald-300"><span>{item.question_type.replace("_", " ")}</span><span>·</span><span>{item.difficulty}</span><span>·</span><span>{item.topic_tag}</span>{isAdaptive && <><span>·</span><span className="text-amber-200">adaptive follow-up</span></>}</div>
      <p className="mt-3 font-medium leading-6 text-white/90">{item.prompt}</p>
      {item.question_type === "mcq" ? <div className="mt-4 space-y-2">{item.options.map((option) => <label key={option} className="flex cursor-pointer gap-3 rounded-xl border border-white/[0.06] bg-black/20 px-3 py-2.5 text-sm text-white/70 transition hover:border-white/15 hover:text-white"><input type="radio" name={`q-${item.id}`} checked={responses[item.id] === option} onChange={() => setResponses((value) => ({ ...value, [item.id]: option }))} className="accent-emerald-400" />{option}</label>)}</div> : <input value={responses[item.id] || ""} onChange={(event) => setResponses((value) => ({ ...value, [item.id]: event.target.value }))} className="mt-4 h-11 w-full rounded-xl border border-white/[0.08] bg-black/25 px-3 text-sm text-white outline-none transition focus:border-emerald-300/40" placeholder={item.question_type === "numerical" ? "Enter the value" : "Write a concise source-based answer"} />}
      <button disabled={busy} onClick={() => submit(item.id, isAdaptive)} className="mt-3 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-black transition hover:bg-white/90 disabled:opacity-50">Check answer</button>
      {message && <p className="mt-3 rounded-xl border border-amber-200/15 bg-amber-200/[0.05] p-3 text-sm leading-6 text-amber-100">{message}</p>}
      <div className="mt-4"><CitationView citation={item.citation} /></div>
    </article>;
  }

  const displayName = username || "Student";
  const initial = displayName.slice(0, 1).toUpperCase();
  const sidebar = (expanded: boolean, mobile = false) => <div className="flex h-full flex-col">
    <div className={`flex h-16 items-center ${expanded ? "justify-between px-4" : "justify-center"}`}>
      {expanded && <Link href="/" className="flex items-center gap-2.5"><Image src="/a_logo.png" alt="Alex" width={32} height={32} className="h-8 w-8 rounded-lg" /><div><p className="text-sm font-bold text-white">Alex Studies</p><p className="text-[9px] font-semibold uppercase tracking-[.2em] text-emerald-300/65">Learning Lab</p></div></Link>}
      <button onClick={() => mobile ? setMobileSidebarOpen(false) : setSidebarOpen((value) => !value)} className="grid h-9 w-9 place-items-center rounded-lg text-white/45 transition hover:bg-white/[0.06] hover:text-white" aria-label={mobile ? "Close sidebar" : expanded ? "Collapse sidebar" : "Open sidebar"}>{mobile ? <X size={18} /> : expanded ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}</button>
    </div>
    <nav className="space-y-1 px-2 pt-4">
      <SidebarItem icon={<GraduationCap size={18} />} label="Learning lab" href="#top" active expanded={expanded} onClick={mobile ? () => setMobileSidebarOpen(false) : undefined} />
      <SidebarItem icon={<Library size={18} />} label="Source library" href="#sources" expanded={expanded} onClick={mobile ? () => setMobileSidebarOpen(false) : undefined} />
      <SidebarItem icon={<MessageSquareText size={18} />} label="Grounded tutor" href="#tutor" expanded={expanded} onClick={mobile ? () => setMobileSidebarOpen(false) : undefined} />
      <SidebarItem icon={<BrainCircuit size={18} />} label="Adaptive assessment" href="#assessment" expanded={expanded} onClick={mobile ? () => setMobileSidebarOpen(false) : undefined} />
      <SidebarItem icon={<CircleGauge size={18} />} label="Topic mastery" href="#mastery" expanded={expanded} onClick={mobile ? () => setMobileSidebarOpen(false) : undefined} />
    </nav>
    <div className="mt-5 border-t border-white/[0.06] px-2 pt-5">
      <SidebarItem icon={<Home size={18} />} label="Alex workspace" href="/s/home" expanded={expanded} />
    </div>
    <div className="mt-auto p-2">
      <div className={`flex items-center rounded-xl border border-white/[0.07] bg-white/[0.035] ${expanded ? "gap-3 p-2.5" : "justify-center p-2"}`} title={!expanded ? displayName : undefined}>
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-emerald-300/20 bg-emerald-300/10 text-xs font-bold text-emerald-200">{initial}</span>
        {expanded && <div className="min-w-0"><p className="truncate text-sm font-semibold text-white/85">{displayName}</p><p className="text-[10px] uppercase tracking-wider text-white/35">Hackathon learner</p></div>}
      </div>
    </div>
  </div>;

  if (!authReady) return <main className="grid min-h-screen place-items-center bg-[#07080b] text-white"><div className="flex items-center gap-3 text-sm text-white/45"><span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />Restoring your Alex session…</div></main>;

  if (!authenticated) return <main className="relative min-h-screen overflow-hidden bg-[#07080b] px-6 py-20 text-white"><div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(52,211,153,.10),transparent_32%),radial-gradient(circle_at_80%_25%,rgba(217,119,87,.07),transparent_25%)]" /><div className="relative mx-auto max-w-xl rounded-[28px] border border-white/[0.09] bg-[#101216]/90 p-8 shadow-[0_30px_100px_rgba(0,0,0,.45),inset_0_1px_0_rgba(255,255,255,.04)] backdrop-blur-xl"><div className="mb-6 flex items-center gap-3"><Image src="/a_logo.png" alt="Alex" width={44} height={44} className="h-11 w-11 rounded-xl" /><div><p className="text-sm font-bold">Alex Studies</p><p className="text-xs text-white/35">Source-grounded learning</p></div></div><h1 className="text-3xl font-semibold tracking-tight">Your learning lab is ready.</h1><p className="mt-4 leading-7 text-white/55">Sign in on this hackathon site to keep uploaded material, citations, assessments, and mastery progress isolated to your account.</p><Link href="/login" className="mt-7 inline-flex h-11 items-center gap-2 rounded-xl bg-white px-5 font-semibold text-black transition hover:bg-white/90"><UserRound size={17} />Sign in</Link></div></main>;

  return <main id="top" className="min-h-screen bg-[#08090b] text-white selection:bg-emerald-300/30">
    <aside className={`fixed inset-y-0 left-0 z-40 hidden border-r border-white/[0.06] bg-[#0c0e11]/95 backdrop-blur-xl transition-[width] duration-200 md:block ${sidebarOpen ? "w-[276px]" : "w-[76px]"}`}>{sidebar(sidebarOpen)}</aside>
    {mobileSidebarOpen && <><button aria-label="Close sidebar" className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm md:hidden" onClick={() => setMobileSidebarOpen(false)} /><aside className="fixed inset-y-0 left-0 z-50 w-[286px] border-r border-white/[0.08] bg-[#0c0e11] shadow-2xl md:hidden">{sidebar(true, true)}</aside></>}

    <div className={`min-h-screen transition-[padding] duration-200 ${sidebarOpen ? "md:pl-[276px]" : "md:pl-[76px]"}`}>
      <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-white/[0.055] bg-[#08090b]/80 px-4 backdrop-blur-xl sm:px-7">
        <button className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.07] bg-white/[0.035] text-white/65 md:hidden" onClick={() => setMobileSidebarOpen(true)} aria-label="Open sidebar"><Menu size={19} /></button>
        <div className="min-w-0"><p className="truncate text-sm font-semibold text-white/90">Track D Learning Lab</p><p className="hidden text-xs text-white/35 sm:block">Grounded tutoring · adaptive mastery</p></div>
        <div className="ml-auto flex items-center gap-3"><span className="hidden rounded-full border border-emerald-300/15 bg-emerald-300/[0.06] px-3 py-1.5 text-xs font-medium text-emerald-200 sm:inline-flex">Demo ready</span><div className="flex items-center gap-2 rounded-xl border border-white/[0.07] bg-white/[0.03] py-1.5 pl-1.5 pr-3"><span className="grid h-7 w-7 place-items-center rounded-lg bg-emerald-300/10 text-[11px] font-bold text-emerald-200">{initial}</span><span className="max-w-32 truncate text-sm text-white/70">{displayName}</span></div></div>
      </header>

      <div className="mx-auto max-w-[1440px] px-4 py-8 sm:px-7 lg:px-10">
        <section className="relative overflow-hidden rounded-[30px] border border-white/[0.075] bg-[#101216] px-6 py-8 shadow-[0_24px_80px_rgba(0,0,0,.25),inset_0_1px_0_rgba(255,255,255,.035)] sm:px-9 sm:py-10">
          <div className="absolute -right-20 -top-32 h-72 w-72 rounded-full bg-emerald-400/[0.07] blur-3xl" /><div className="absolute bottom-0 right-1/4 h-36 w-36 rounded-full bg-[#d97757]/[0.05] blur-3xl" />
          <div className="relative max-w-3xl"><div className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald-300/15 bg-emerald-300/[0.055] px-3 py-1.5 text-[10px] font-bold uppercase tracking-[.2em] text-emerald-200"><Sparkles size={13} />Multimodal AI Hackathon · Track D</div><h1 className="text-3xl font-semibold tracking-[-.035em] text-white sm:text-5xl">Learn from your own material,<br className="hidden sm:block" /> with every answer grounded.</h1><p className="mt-5 max-w-2xl text-sm leading-7 text-white/50 sm:text-base">Upload lectures, textbooks, and slides. Alex retrieves exact source evidence, teaches from it, and adapts the next question to your weakest topic.</p></div>
        </section>

        <div role="status" className="mt-5 flex min-h-12 items-center gap-3 rounded-2xl border border-white/[0.065] bg-white/[0.025] px-4 text-sm text-white/55"><span className={`h-2 w-2 rounded-full ${busy ? "animate-pulse bg-amber-300" : "bg-emerald-400"}`} />{busy ? "Working · " : ""}{status}</div>

        <section id="sources" className="scroll-mt-24 pt-12"><div className="mb-5"><p className="text-xs font-bold uppercase tracking-[.18em] text-emerald-300/75">Knowledge base</p><h2 className="mt-2 text-2xl font-semibold tracking-tight">Add learning material</h2></div><div className="grid gap-4 lg:grid-cols-3">
          {(["pdf", "pptx"] as const).map((kind) => <label key={kind} className="group cursor-pointer rounded-2xl border border-white/[0.07] bg-white/[0.025] p-5 transition hover:-translate-y-0.5 hover:border-emerald-300/25 hover:bg-white/[0.04]"><span className="mb-5 grid h-10 w-10 place-items-center rounded-xl border border-white/[0.07] bg-black/20 text-emerald-200">{kind === "pdf" ? <FileText size={19} /> : <Presentation size={19} />}</span><span className="font-semibold text-white/90">Upload {kind.toUpperCase()}</span><span className="mt-2 block text-sm leading-6 text-white/40">Preserves {kind === "pdf" ? "pages, figures, and exact citations" : "slides, tables, notes, and images"}.</span><span className="mt-5 inline-flex items-center gap-2 text-xs font-semibold text-emerald-200/80"><UploadCloud size={15} />Choose file</span><input disabled={busy} className="sr-only" type="file" accept={kind === "pdf" ? ".pdf,application/pdf" : ".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"} onChange={(event) => upload(kind, event.target.files?.[0])} /></label>)}
          <form onSubmit={addYoutube} className="rounded-2xl border border-white/[0.07] bg-white/[0.025] p-5"><span className="mb-5 grid h-10 w-10 place-items-center rounded-xl border border-white/[0.07] bg-black/20 text-[#e7b69d]"><Youtube size={19} /></span><label className="font-semibold text-white/90" htmlFor="youtube-url">YouTube lecture</label><p className="mt-2 text-sm leading-6 text-white/40">Indexes the transcript while preserving timestamp links.</p><div className="mt-4 flex gap-2"><input id="youtube-url" value={youtubeUrl} onChange={(event) => setYoutubeUrl(event.target.value)} className="min-w-0 flex-1 rounded-xl border border-white/[0.08] bg-black/25 px-3 py-2.5 text-sm text-white outline-none focus:border-emerald-300/40" placeholder="youtube.com/watch?v=…" /><button disabled={busy} className="rounded-xl bg-white px-4 text-sm font-semibold text-black disabled:opacity-50">Add</button></div></form>
        </div></section>

        <section className="pt-9"><h2 className="text-lg font-semibold text-white/90">Processed sources</h2><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{sources.length ? sources.map((source) => <article key={source.id} className="rounded-2xl border border-white/[0.07] bg-[#101216] p-4"><div className="flex items-start gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white/[0.04] text-emerald-200"><SourceIcon type={source.source_type} /></span><div className="min-w-0 flex-1"><div className="flex justify-between gap-3"><strong className="truncate text-sm text-white/85">{source.title}</strong><span className="text-[9px] font-bold uppercase tracking-widest text-emerald-300">{source.source_type}</span></div><p className="mt-1 text-xs text-white/35">{source.unit_count} source units · {source.visual_count} visuals · {source.extraction_status}</p></div></div></article>) : <div className="col-span-full rounded-2xl border border-dashed border-white/[0.09] py-9 text-center text-sm text-white/35">Your indexed sources will appear here.</div>}</div></section>

        <section className="grid scroll-mt-24 gap-5 pt-12 lg:grid-cols-[1.4fr_.6fr]" id="tutor"><div className="rounded-[24px] border border-white/[0.075] bg-[#101216] p-5 sm:p-6"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-300/[0.08] text-emerald-200"><MessageSquareText size={19} /></span><div><h2 className="text-xl font-semibold">Ask your material</h2><p className="text-sm text-white/35">Answers use retrieved evidence only.</p></div></div><form onSubmit={ask} className="mt-5 flex gap-2"><div className="relative min-w-0 flex-1"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/25" /><input value={question} onChange={(event) => setQuestion(event.target.value)} className="h-12 w-full rounded-xl border border-white/[0.08] bg-black/25 pl-10 pr-3 text-sm text-white outline-none focus:border-emerald-300/40" placeholder="What does my material say about…?" /></div><button disabled={busy} className="rounded-xl bg-emerald-300 px-5 text-sm font-bold text-emerald-950 disabled:opacity-50">Ask Alex</button></form>{answer && <div className="mt-6 border-t border-white/[0.06] pt-5"><p className="leading-7 text-white/75">{answer}</p><div className="mt-4 space-y-2">{citations.map((citation) => <CitationView key={citation.source_unit_id} citation={citation} />)}</div></div>}</div>
          <div id="mastery" className="scroll-mt-24 rounded-[24px] border border-white/[0.075] bg-[#101216] p-5 sm:p-6"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-[#d97757]/10 text-[#e7b69d]"><CircleGauge size={19} /></span><div><h2 className="text-xl font-semibold">Topic mastery</h2><p className="text-sm text-white/35">Updated after every answer.</p></div></div><div className="mt-5 space-y-5">{mastery.length ? mastery.map((item) => <div key={item.topic_tag}><div className="flex justify-between text-sm"><span className="truncate text-white/65">{item.topic_tag}</span><span className="font-semibold text-white/80">{item.mastery_score.toFixed(0)}%</span></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.06]"><div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-300 transition-all" style={{ width: `${item.mastery_score}%` }} /></div><p className="mt-2 text-xs leading-5 text-white/30">{item.recommendation}</p></div>) : <p className="text-sm leading-6 text-white/35">Answer cited questions to build your mastery profile.</p>}</div></div></section>

        <section id="assessment" className="scroll-mt-24 py-12"><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[.18em] text-emerald-300/75">Adaptive learning</p><h2 className="mt-2 text-2xl font-semibold">Practice your weakest topic</h2><p className="mt-2 max-w-xl text-sm leading-6 text-white/40">The weakest measured topic controls the next cited question and its difficulty.</p></div><div className="flex gap-2"><button onClick={() => generate(false)} disabled={busy} className="rounded-xl border border-white/[0.1] bg-white/[0.035] px-4 py-2.5 text-sm font-semibold text-white/75 hover:bg-white/[0.06]">Generate practice</button><button onClick={() => generate(true)} disabled={busy} className="rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-black hover:bg-white/90">Run diagnostic</button></div></div>
          {adaptive && <div className="mt-6 rounded-[24px] border border-amber-300/20 bg-amber-300/[0.04] p-5"><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-[10px] font-bold uppercase tracking-[.2em] text-amber-200">Next adaptive step</p><p className="mt-1 text-sm text-white/55">{adaptive.rationale}</p></div><span className="rounded-full border border-amber-200/20 px-3 py-1 text-xs uppercase text-amber-100">{adaptive.mastery_score.toFixed(0)}% · {adaptive.difficulty}</span></div>{lastAdaptiveFeedback && <p className="mt-3 rounded-xl border border-white/[0.07] bg-black/20 p-3 text-sm text-amber-100"><strong>Previous answer:</strong> {lastAdaptiveFeedback}</p>}<div className="mt-4">{questionCard(adaptive.question, true)}</div></div>}
          <div className="mt-5 grid gap-4 xl:grid-cols-2">{questions.map((item) => questionCard(item))}</div>
        </section>
      </div>
    </div>
  </main>;
}

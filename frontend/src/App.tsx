import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { JobParseResult } from "./api";
import {
  fetchHealth,
  parseJob,
  renderLatexToPdf,
  submitApply,
  tailorResume,
} from "./api";

type LoadState = "idle" | "loading" | "ok" | "error";

function Panel({
  title,
  step,
  children,
  className = "",
}: {
  title: string;
  step: string | number;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-2xl border border-white/[0.08] bg-surface-800/60 shadow-panel backdrop-blur-sm ${className}`}
    >
      <div className="flex items-center gap-3 border-b border-white/[0.06] px-5 py-4">
        <span className="flex h-8 min-w-8 shrink-0 items-center justify-center rounded-xl bg-brand/15 px-1 font-display text-sm font-semibold text-brand-glow">
          {step}
        </span>
        <h2 className="font-display text-lg font-semibold tracking-tight text-ink-50">
          {title}
        </h2>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function PdfViewerModal({
  url,
  onClose,
}: {
  url: string | null;
  onClose: () => void;
}) {
  if (!url) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="relative flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-white/10 bg-surface-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
          <h3 className="font-display text-xl font-bold text-ink-50">PDF Preview</h3>
          <button
            onClick={onClose}
            className="rounded-xl bg-white/5 p-2 text-ink-300 transition hover:bg-white/10 hover:text-ink-50"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="flex-1 bg-surface-950">
          <iframe src={url} className="h-full w-full border-none" title="PDF Preview" />
        </div>
      </div>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback for older browsers
      const el = document.createElement("textarea");
      el.value = text;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    }
  };
  return (
    <button
      type="button"
      className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-semibold transition ${
        copied
          ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-200"
          : "border-brand/30 bg-brand/10 text-brand-glow hover:bg-brand/20"
      }`}
      onClick={handleCopy}
    >
      {copied ? (
        <>
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          Copied!
        </>
      ) : (
        <>
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          Copy LaTeX
        </>
      )}
    </button>
  );
}

export function App() {
  const [apiOk, setApiOk] = useState<LoadState>("idle");
  const [apiVersion, setApiVersion] = useState<string>("");
  const [groqOn, setGroqOn] = useState<boolean | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const [jobText, setJobText] = useState("");
  const [parsed, setParsed] = useState<JobParseResult | null>(null);
  const [parseBusy, setParseBusy] = useState(false);

  // Sync resume text to local storage
  const [resumeText, setResumeText] = useState(() => localStorage.getItem("job_agent_resume") || "");
  const [resumeErr, setResumeErr] = useState<string | null>(null);

  const [tailored, setTailored] = useState<string | null>(null);
  const [matchScore, setMatchScore] = useState<number | null>(null);
  const [tailorBusy, setTailorBusy] = useState(false);

  // PDF Preview State
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfBusy, setPdfBusy] = useState(false);

  const [applyUrl, setApplyUrl] = useState("");
  const [applyPath, setApplyPath] = useState("");
  const [applyBusy, setApplyBusy] = useState(false);
  const [applyResult, setApplyResult] = useState<string | null>(null);

  const [banner, setBanner] = useState<string | null>(null);
  const gradId = useId().replace(/:/g, "");

  useEffect(() => {
    localStorage.setItem("job_agent_resume", resumeText);
  }, [resumeText]);

  const workflowSteps = useMemo(
    () => [
      { label: "Add your resume", done: resumeText.trim().length >= 50 },
      { label: "Paste job description", done: jobText.trim().length >= 30 },
      { label: "Get updated resume", done: Boolean(tailored) },
    ],
    [resumeText, jobText, tailored]
  );

  const showError = useCallback((msg: string) => {
    setBanner(msg);
    window.setTimeout(() => setBanner(null), 8000);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const h = await fetchHealth();
        if (!cancelled) {
          setApiOk("ok");
          setApiVersion(h.version);
        }
        const cfgRes = await fetch("/api/config/paths");
        if (cfgRes.ok && !cancelled) {
          const cfg = (await cfgRes.json()) as {
            groq_configured?: boolean;
            groq_model?: string;
          };
          setGroqOn(Boolean(cfg.groq_configured));
        }
      } catch {
        if (!cancelled) setApiOk("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const loadSamples = async () => {
    try {
      const [jobR, resR] = await Promise.all([
        fetch("/samples/sample_job.txt"),
        fetch("/samples/sample_resume.tex"),
      ]);
      setJobText(await jobR.text());
      setResumeText(await resR.text());
      setParsed(null);
      setTailored(null);
      setMatchScore(null);
    } catch {
      showError("Could not load sample files. Check that the dev server is running.");
    }
  };

  const closePdf = useCallback(() => {
    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl);
      setPdfUrl(null);
    }
  }, [pdfUrl]);

  const handlePreview = async (latex: string) => {
    if (!latex.trim()) return;
    setPdfBusy(true);
    setBanner(null);
    try {
      const blob = await renderLatexToPdf(latex);
      const url = URL.createObjectURL(blob);
      setPdfUrl(url);
    } catch (err) {
      showError(err instanceof Error ? err.message : String(err));
    } finally {
      setPdfBusy(false);
    }
  };

  const handleResumeFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      const text = await file.text();
      setResumeText(text);
      setResumeErr(null);
      setBanner("Resume loaded from file.");
      window.setTimeout(() => setBanner(null), 4000);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Failed to read file");
    }
  };

  const handleParse = async () => {
    if (!jobText.trim()) {
      showError("Paste a job description first.");
      return;
    }
    setParseBusy(true);
    setBanner(null);
    try {
      const { job } = await parseJob(jobText);
      setParsed(job);
    } catch (e) {
      showError(e instanceof Error ? e.message : "Parse failed");
    } finally {
      setParseBusy(false);
    }
  };

  const handleTailor = async () => {
    if (!resumeText.trim()) {
      showError("Add your resume LaTeX first.");
      return;
    }
    if (!jobText.trim()) {
      showError("Add a job description to tailor against.");
      return;
    }
    setTailorBusy(true);
    setBanner(null);
    try {
      const out = await tailorResume({
        base_latex: resumeText,
        job_description: jobText,
      });
      setTailored(out.tailored_latex);
      setMatchScore(out.match_score);
    } catch (e) {
      showError(e instanceof Error ? e.message : "Tailor failed");
    } finally {
      setTailorBusy(false);
    }
  };

  const handleApply = async () => {
    if (!applyUrl.trim() || !applyPath.trim()) {
      showError("Enter both LinkedIn job URL and the PDF path on this machine.");
      return;
    }
    setApplyBusy(true);
    setApplyResult(null);
    try {
      const r = await submitApply(applyUrl.trim(), applyPath.trim());
      setApplyResult(`${r.success ? "✓" : "✗"} ${r.message}`);
    } catch (e) {
      setApplyResult(e instanceof Error ? e.message : "Apply request failed");
    } finally {
      setApplyBusy(false);
    }
  };

  return (
    <div className="bg-grid min-h-screen">
      <div className="mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6 lg:px-8">
        <header className="mb-10 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-brand-glow/90">
              Job Agent
            </p>
            <h1 className="font-display text-3xl font-bold tracking-tight text-ink-50 sm:text-4xl">
              Apply smarter, stay honest
            </h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-300">
              Paste or upload your LaTeX resume → paste any job description → we update your
              resume for that role (AI when Gemini is on).
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${
                apiOk === "ok"
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                  : apiOk === "error"
                    ? "border-red-500/30 bg-red-500/10 text-red-300"
                    : "border-white/10 bg-white/5 text-ink-300"
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  apiOk === "ok"
                    ? "bg-emerald-400 shadow-[0_0_8px_#34d399]"
                    : apiOk === "error"
                      ? "bg-red-400"
                      : "bg-ink-400 animate-pulse"
                }`}
              />
              {apiOk === "ok"
                ? `API ${apiVersion}`
                : apiOk === "error"
                  ? "API unreachable"
                  : "Checking API…"}
            </span>
            {groqOn !== null && (
              <span
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium ${
                  groqOn
                    ? "border-violet-500/30 bg-violet-500/10 text-violet-200"
                    : "border-white/10 bg-white/5 text-ink-400"
                }`}
                title="Groq-powered tailoring when APP_GROQ_API_KEY is set"
              >
                Groq AI {groqOn ? "ON" : "off"}
              </span>
            )}
            <a
              className="rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-xs font-medium text-ink-100 transition hover:bg-white/10"
              href="/docs"
              target="_blank"
              rel="noreferrer"
            >
              OpenAPI docs
            </a>
          </div>
        </header>

        {banner && (
          <div
            className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100"
            role="alert"
          >
            {banner}
          </div>
        )}

        <div
          className="mb-6 rounded-2xl border border-white/[0.08] bg-surface-800/40 p-4"
          aria-label="Workflow steps"
        >
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.15em] text-ink-400">
            Your flow
          </p>
          <ol className="grid gap-3 sm:grid-cols-3">
            {workflowSteps.map((s, i) => (
              <li
                key={s.label}
                className={`flex items-start gap-2 rounded-xl border px-3 py-2 text-sm ${
                  s.done
                    ? "border-emerald-500/35 bg-emerald-500/10 text-emerald-100"
                    : "border-white/10 bg-surface-900/50 text-ink-300"
                }`}
              >
                <span
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    s.done ? "bg-emerald-500/30 text-emerald-200" : "bg-white/10 text-ink-400"
                  }`}
                >
                  {s.done ? "✓" : i + 1}
                </span>
                <span className="leading-snug">{s.label}</span>
              </li>
            ))}
          </ol>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="flex flex-col gap-6">
            <Panel title="1 · Your resume (stored locally)" step={1}>
              <p className="mb-3 text-sm text-ink-300">
                Edit LaTeX here or use <strong className="text-ink-200">Upload .tex</strong>.
                It is automatically saved to your browser's local storage.
              </p>
              <textarea
                className="mb-2 min-h-[280px] w-full resize-y rounded-xl border border-white/10 bg-surface-900/80 px-4 py-3 font-mono text-xs leading-relaxed text-ink-100 focus:border-brand/50 focus:outline-none focus:ring-1 focus:ring-brand/30"
                value={resumeText}
                onChange={(e) => setResumeText(e.target.value)}
                spellCheck={false}
              />
              {resumeErr && (
                <p className="mb-2 text-sm text-red-300">{resumeErr}</p>
              )}
              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                <button
                  type="button"
                  className="rounded-xl border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-ink-100 transition hover:bg-white/10"
                  onClick={() => fileInputRef.current?.click()}
                >
                  Upload .tex
                </button>
                <button
                  type="button"
                  className="rounded-xl border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-ink-100 transition hover:bg-white/10"
                  onClick={loadSamples}
                >
                  Load sample
                </button>
                <button
                  type="button"
                  disabled={pdfBusy || !resumeText.trim()}
                  className="rounded-xl border border-brand/30 bg-brand/10 px-3 py-1.5 text-xs font-medium text-brand-glow transition hover:bg-brand/20 disabled:opacity-50"
                  onClick={() => handlePreview(resumeText)}
                >
                  {pdfBusy ? "Compiling..." : "Preview PDF"}
                </button>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".tex,text/plain"
                className="hidden"
                onChange={handleResumeFile}
              />
            </Panel>

            <Panel title="3 · Updated resume" step={3}>
              {matchScore != null && (
                <div className="mb-4 flex items-center gap-4">
                  <div
                    className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-surface-900/80 font-display text-lg font-bold text-brand-glow"
                    title="Match score"
                  >
                    <svg className="absolute inset-0 -rotate-90" viewBox="0 0 36 36">
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke="rgba(255,255,255,0.08)"
                        strokeWidth="3"
                      />
                      <path
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                        fill="none"
                        stroke={`url(#${gradId})`}
                        strokeDasharray={`${matchScore}, 100`}
                        strokeLinecap="round"
                        strokeWidth="3"
                      />
                      <defs>
                        <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
                          <stop offset="0%" stopColor="#3d9cf0" />
                          <stop offset="100%" stopColor="#7ec8ff" />
                        </linearGradient>
                      </defs>
                    </svg>
                    <span className="relative text-sm">{Math.round(matchScore)}</span>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-ink-400">
                      Match score
                    </p>
                    <p className="text-sm text-ink-200">
                      Based on skill overlap, keywords, and experience wording.
                    </p>
                  </div>
                </div>
              )}

              {tailored ? (
                <>
                  <div className="mb-4 rounded-xl border border-white/10 bg-surface-900/50">
                    <pre className="max-h-96 overflow-auto p-4 font-mono text-[13px] leading-relaxed text-ink-200">
                      {tailored}
                    </pre>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <CopyButton text={tailored} />
                    <button
                      type="button"
                      className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/20"
                      title="Load the tailored resume back as your base resume for further tailoring"
                      onClick={() => {
                        setResumeText(tailored);
                        setTailored(null);
                        setMatchScore(null);
                      }}
                    >
                      Use as base resume
                    </button>
                    <button
                      type="button"
                      disabled={pdfBusy}
                      className="rounded-xl border border-brand/30 bg-brand/10 px-4 py-2 text-sm font-medium text-brand-glow transition hover:bg-brand/20 disabled:opacity-50"
                      onClick={() => handlePreview(tailored)}
                    >
                      {pdfBusy ? "Compiling..." : "Preview PDF"}
                    </button>
                    <button
                      type="button"
                      className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-ink-100 transition hover:bg-white/10"
                      onClick={() => {
                        setTailored(null);
                        setMatchScore(null);
                      }}
                    >
                      Clear output
                    </button>
                  </div>
                </>
              ) : (
                <p className="mb-4 text-sm text-ink-400">
                  Tailor your resume to see the updated LaTeX code.
                </p>
              )}
            </Panel>

            
            <Panel title="LinkedIn Easy Apply (advanced)" step={4}>
              <p className="mb-3 text-sm text-ink-300">
                Requires Playwright browsers and often manual login. Provide a{" "}
                <strong className="text-ink-200">local absolute path</strong> to the PDF on
                this machine (e.g. from the output folder after generating).
              </p>
              <label className="mb-2 block text-xs font-medium text-ink-400">
                Job URL
              </label>
              <input
                className="mb-3 w-full rounded-xl border border-white/10 bg-surface-900/80 px-4 py-2.5 text-sm text-ink-100 focus:border-brand/50 focus:outline-none focus:ring-1 focus:ring-brand/30"
                placeholder="https://www.linkedin.com/jobs/view/…"
                value={applyUrl}
                onChange={(e) => setApplyUrl(e.target.value)}
              />
              <label className="mb-2 block text-xs font-medium text-ink-400">
                Resume PDF path (this computer)
              </label>
              <input
                className="mb-3 w-full rounded-xl border border-white/10 bg-surface-900/80 px-4 py-2.5 font-mono text-sm text-ink-100 focus:border-brand/50 focus:outline-none focus:ring-1 focus:ring-brand/30"
                placeholder="/Users/you/.../output/resume-….pdf"
                value={applyPath}
                onChange={(e) => setApplyPath(e.target.value)}
              />
              <button
                type="button"
                className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-ink-100 transition hover:bg-white/10 disabled:opacity-50"
                onClick={handleApply}
                disabled={applyBusy}
              >
                {applyBusy ? "Running…" : "Run automation"}
              </button>
              {applyResult && (
                <p className="mt-3 rounded-lg border border-white/10 bg-surface-900/60 px-3 py-2 font-mono text-xs text-ink-200">
                  {applyResult}
                </p>
              )}
            </Panel>
          </div>

          <div className="flex flex-col gap-6">
            <Panel title="2 · Job description (what you’re applying to)" step={2}>
              <p className="mb-3 text-sm text-ink-300">
                Paste the full posting here. We use it to update your
                stored resume for this role (parse is optional — helps preview skills).
              </p>
              <textarea
                className="mb-3 min-h-[220px] w-full resize-y rounded-xl border border-white/10 bg-surface-900/80 px-4 py-3 font-mono text-sm text-ink-100 placeholder:text-ink-400 focus:border-brand/50 focus:outline-none focus:ring-1 focus:ring-brand/30"
                placeholder="Paste job description here…"
                value={jobText}
                onChange={(e) => setJobText(e.target.value)}
                spellCheck
              />
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-surface-900 shadow-lg shadow-brand/20 transition hover:bg-brand-glow disabled:opacity-50"
                  onClick={handleParse}
                  disabled={parseBusy}
                >
                  {parseBusy ? "Parsing…" : "Parse job (optional)"}
                </button>
                <button
                  type="button"
                  className="rounded-xl bg-gradient-to-r from-accent/90 to-amber-500/90 px-4 py-2 text-sm font-bold text-surface-900 shadow-lg shadow-amber-500/15 transition hover:brightness-110 disabled:opacity-50"
                  onClick={handleTailor}
                  disabled={tailorBusy}
                >
                  {tailorBusy ? "Tailoring…" : "Tailor resume"}
                </button>
              </div>

              {parsed && (
                <div className="mt-6 rounded-xl border border-white/10 bg-surface-900/50 p-4">
                  <h4 className="mb-3 font-display font-semibold text-ink-100">Parsed Output</h4>
                  <div className="space-y-4">
                    <div>
                      <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-400">
                        Must-have Skills
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {parsed.must_have_skills?.map((s, i) => (
                          <span
                            key={i}
                            className="inline-flex rounded-full border border-pink-500/30 bg-pink-500/10 px-2 py-0.5 text-[11px] font-medium text-pink-200"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-400">
                        Good-to-have Skills
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {parsed.good_to_have_skills?.map((s, i) => (
                          <span
                            key={i}
                            className="inline-flex rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[11px] font-medium text-sky-200"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-400">
                        Keywords
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {parsed.keywords?.map((k, i) => (
                          <span
                            key={i}
                            className="inline-flex rounded border border-white/5 bg-surface-950 px-1.5 py-0.5 text-[11px] text-ink-300"
                          >
                            {k}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-400">
                        Responsibilities
                      </p>
                      <ul className="ml-4 list-disc space-y-1 text-sm text-ink-200 marker:text-white/20">
                        {parsed.responsibilities?.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}
            </Panel>
          </div>
        </div>
      </div>
      <PdfViewerModal url={pdfUrl} onClose={closePdf} />
    </div>
  );
}

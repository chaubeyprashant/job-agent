import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  apiUrl,
  fetchHealth,
  uploadAndTailor,
} from "./api";

type LoadState = "idle" | "loading" | "ok" | "error";

/* ------------------------------------------------------------------ */
/*  Reusable Panel                                                     */
/* ------------------------------------------------------------------ */
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

/* ------------------------------------------------------------------ */
/*  File size formatter                                                */
/* ------------------------------------------------------------------ */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ------------------------------------------------------------------ */
/*  Main App                                                           */
/* ------------------------------------------------------------------ */
export function App() {
  const [apiOk, setApiOk] = useState<LoadState>("idle");
  const [apiVersion, setApiVersion] = useState<string>("");
  const [groqOn, setGroqOn] = useState<boolean | null>(null);

  /* ---- Resume PDF state ---- */
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);

  /* ---- Job description state ---- */
  const [jobText, setJobText] = useState("");

  /* ---- Tailored output state ---- */
  const [tailoredBlob, setTailoredBlob] = useState<Blob | null>(null);
  const [tailoredUrl, setTailoredUrl] = useState<string | null>(null);
  const [tailorBusy, setTailorBusy] = useState(false);

  /* ---- Banner ---- */
  const [banner, setBanner] = useState<string | null>(null);
  const [bannerType, setBannerType] = useState<"info" | "error">("info");

  /* ---- Workflow progress ---- */
  const workflowSteps = useMemo(
    () => [
      { label: "Upload your resume (PDF)", done: resumeFile !== null },
      { label: "Paste job description", done: jobText.trim().length >= 30 },
      { label: "Download updated resume", done: tailoredBlob !== null },
    ],
    [resumeFile, jobText, tailoredBlob]
  );

  /* ---- Helpers ---- */
  const showError = useCallback((msg: string) => {
    setBanner(msg);
    setBannerType("error");
    window.setTimeout(() => setBanner(null), 8000);
  }, []);

  const showInfo = useCallback((msg: string) => {
    setBanner(msg);
    setBannerType("info");
    window.setTimeout(() => setBanner(null), 4000);
  }, []);

  /* Revoke object URL on cleanup */
  useEffect(() => {
    return () => {
      if (tailoredUrl) URL.revokeObjectURL(tailoredUrl);
    };
  }, [tailoredUrl]);

  /* ---- Health check on mount ---- */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const h = await fetchHealth();
        if (!cancelled) {
          setApiOk("ok");
          setApiVersion(h.version);
        }
        const cfgRes = await fetch(apiUrl("/api/config/paths"));
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

  /* ---- File handlers ---- */
  const handleFileSelect = (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showError("Please upload a PDF file.");
      return;
    }
    if (file.size > 10_000_000) {
      showError("File too large. Maximum 10 MB.");
      return;
    }
    setResumeFile(file);
    // Clear previous output when a new file is loaded
    if (tailoredUrl) URL.revokeObjectURL(tailoredUrl);
    setTailoredBlob(null);
    setTailoredUrl(null);
    showInfo(`Loaded "${file.name}" (${formatBytes(file.size)})`);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) handleFileSelect(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => setDragOver(false);

  /* ---- Tailor handler ---- */
  const handleTailor = async () => {
    if (!resumeFile) {
      showError("Upload your resume PDF first.");
      return;
    }
    if (!jobText.trim()) {
      showError("Paste a job description first.");
      return;
    }
    setTailorBusy(true);
    setBanner(null);
    try {
      const blob = await uploadAndTailor(resumeFile, jobText);
      const url = URL.createObjectURL(blob);
      if (tailoredUrl) URL.revokeObjectURL(tailoredUrl);
      setTailoredBlob(blob);
      setTailoredUrl(url);
    } catch (e) {
      showError(e instanceof Error ? e.message : "Tailoring failed.");
    } finally {
      setTailorBusy(false);
    }
  };

  /* ---- Download handler ---- */
  const handleDownload = () => {
    if (!tailoredUrl) return;
    const a = document.createElement("a");
    a.href = tailoredUrl;
    a.download = "tailored_resume.pdf";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  /* ================================================================ */
  /*  RENDER                                                           */
  /* ================================================================ */
  return (
    <div className="bg-grid min-h-screen">
      <div className="mx-auto max-w-6xl px-4 pb-20 pt-10 sm:px-6 lg:px-8">
        {/* ---- Header ---- */}
        <header className="mb-10 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-brand-glow/90">
              Job Agent
            </p>
            <h1 className="font-display text-3xl font-bold tracking-tight text-ink-50 sm:text-4xl">
              Apply smarter, stay honest
            </h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-300">
              Upload your resume PDF → paste the job description → download the
              tailored resume.
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
          </div>
        </header>

        {/* ---- Banner ---- */}
        {banner && (
          <div
            className={`mb-6 rounded-xl border px-4 py-3 text-sm ${
              bannerType === "error"
                ? "border-red-500/30 bg-red-500/10 text-red-100"
                : "border-amber-500/30 bg-amber-500/10 text-amber-100"
            }`}
            role="alert"
          >
            {banner}
          </div>
        )}

        {/* ---- Workflow progress bar ---- */}
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

        {/* ---- Main grid ---- */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* ---- LEFT COLUMN ---- */}
          <div className="flex flex-col gap-6">
            {/* Step 1: Upload resume PDF */}
            <Panel title="Upload your resume" step={1}>
              <p className="mb-4 text-sm text-ink-300">
                Drag & drop your resume PDF below, or click to browse.
              </p>

              {/* Drop zone */}
              <div
                id="resume-dropzone"
                className={`group relative flex min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed transition-all duration-200 ${
                  dragOver
                    ? "border-brand bg-brand/10 scale-[1.01]"
                    : resumeFile
                      ? "border-emerald-500/40 bg-emerald-500/5"
                      : "border-white/15 bg-surface-900/40 hover:border-white/25 hover:bg-surface-900/60"
                }`}
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
              >
                {resumeFile ? (
                  <div className="flex flex-col items-center gap-3 px-4 text-center">
                    {/* PDF icon */}
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/15">
                      <svg className="h-7 w-7 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                      </svg>
                    </div>
                    <div>
                      <p className="font-semibold text-emerald-200">{resumeFile.name}</p>
                      <p className="mt-0.5 text-xs text-ink-400">{formatBytes(resumeFile.size)}</p>
                    </div>
                    <p className="text-xs text-ink-400">Click or drop to replace</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-3 px-4 text-center">
                    {/* Upload icon */}
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5 transition group-hover:bg-brand/10">
                      <svg className="h-7 w-7 text-ink-300 transition group-hover:text-brand-glow" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                      </svg>
                    </div>
                    <div>
                      <p className="font-medium text-ink-200">
                        Drop your resume PDF here
                      </p>
                      <p className="mt-1 text-xs text-ink-400">
                        or <span className="text-brand-glow underline">browse</span> to select a file
                      </p>
                    </div>
                    <p className="text-[11px] text-ink-400/70">PDF files up to 10 MB</p>
                  </div>
                )}
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={handleInputChange}
              />

              {resumeFile && (
                <button
                  type="button"
                  className="mt-3 rounded-xl border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-ink-100 transition hover:bg-white/10"
                  onClick={(e) => {
                    e.stopPropagation();
                    setResumeFile(null);
                    if (tailoredUrl) URL.revokeObjectURL(tailoredUrl);
                    setTailoredBlob(null);
                    setTailoredUrl(null);
                  }}
                >
                  Remove file
                </button>
              )}
            </Panel>

            {/* Step 3: Download updated resume */}
            <Panel title="Updated resume" step={3}>
              {tailoredUrl ? (
                <>
                  {/* PDF preview */}
                  <div className="mb-4 overflow-hidden rounded-xl border border-white/10 bg-white">
                    <iframe
                      id="pdf-preview"
                      src={tailoredUrl}
                      className="h-[500px] w-full"
                      title="Tailored resume preview"
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      id="download-pdf-btn"
                      type="button"
                      className="inline-flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200 transition hover:bg-emerald-500/20"
                      onClick={handleDownload}
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      Download PDF
                    </button>
                    <button
                      type="button"
                      className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-ink-100 transition hover:bg-white/10"
                      onClick={() => {
                        if (tailoredUrl) URL.revokeObjectURL(tailoredUrl);
                        setTailoredBlob(null);
                        setTailoredUrl(null);
                      }}
                    >
                      Clear output
                    </button>
                  </div>
                </>
              ) : tailorBusy ? (
                <div className="flex flex-col items-center gap-4 py-10">
                  <div className="relative h-12 w-12">
                    <div className="absolute inset-0 animate-spin rounded-full border-[3px] border-brand/20 border-t-brand" />
                    <div className="absolute inset-2 animate-spin rounded-full border-[2px] border-violet-500/20 border-b-violet-400" style={{ animationDirection: "reverse", animationDuration: "0.8s" }} />
                  </div>
                  <div className="text-center">
                    <p className="font-medium text-ink-200">Tailoring your resume…</p>
                    <p className="mt-1 text-xs text-ink-400">
                      Groq AI is rewriting your resume for this role. This takes 10–30 seconds.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3 py-10 text-center">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/5">
                    <svg className="h-6 w-6 text-ink-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m.75 12l3 3m0 0l3-3m-3 3v-6m-1.5-9H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                  </div>
                  <p className="text-sm text-ink-400">
                    Upload resume & paste JD, then click "Tailor resume" to generate your updated PDF.
                  </p>
                </div>
              )}
            </Panel>
          </div>

          {/* ---- RIGHT COLUMN ---- */}
          <div className="flex flex-col gap-6">
            {/* Step 2: Job description */}
            <Panel title="Job description" step={2}>
              <p className="mb-3 text-sm text-ink-300">
                Paste the full job posting here. We use it to tailor your
                resume for this role.
              </p>
              <textarea
                id="job-description-input"
                className="mb-3 min-h-[220px] w-full resize-y rounded-xl border border-white/10 bg-surface-900/80 px-4 py-3 font-mono text-sm text-ink-100 placeholder:text-ink-400 focus:border-brand/50 focus:outline-none focus:ring-1 focus:ring-brand/30"
                placeholder="Paste job description here…"
                value={jobText}
                onChange={(e) => setJobText(e.target.value)}
                spellCheck
              />
              <div className="flex flex-wrap gap-2">
                <button
                  id="tailor-resume-btn"
                  type="button"
                  className="rounded-xl bg-gradient-to-r from-accent/90 to-amber-500/90 px-5 py-2.5 text-sm font-bold text-surface-900 shadow-lg shadow-amber-500/15 transition hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={handleTailor}
                  disabled={tailorBusy || !resumeFile || !jobText.trim()}
                >
                  {tailorBusy ? (
                    <span className="inline-flex items-center gap-2">
                      <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Tailoring…
                    </span>
                  ) : (
                    "🚀 Tailor resume"
                  )}
                </button>
              </div>

              {/* Validation hints */}
              {(!resumeFile || !jobText.trim()) && (
                <div className="mt-4 rounded-xl border border-white/5 bg-surface-900/30 px-4 py-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-400">
                    To get started
                  </p>
                  <ul className="space-y-1 text-xs text-ink-400">
                    <li className={resumeFile ? "line-through opacity-50" : ""}>
                      {resumeFile ? "✓" : "→"} Upload your resume PDF
                    </li>
                    <li className={jobText.trim().length >= 30 ? "line-through opacity-50" : ""}>
                      {jobText.trim().length >= 30 ? "✓" : "→"} Paste the job description
                    </li>
                  </ul>
                </div>
              )}
            </Panel>
          </div>
        </div>
      </div>
    </div>
  );
}

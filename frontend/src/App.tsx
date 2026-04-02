import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { JobParseResult, Resume, UserPublic } from "./api";
import {
  fetchHealth,
  generatePdf,
  getMe,
  getMyResume,
  getToken,
  loginAccount,
  optimizeSavedResume,
  parseJob,
  putMyResume,
  registerAccount,
  setToken,
  submitApply,
  tailorResume,
  uploadResumeFile,
} from "./api";

type LoadState = "idle" | "loading" | "ok" | "error";

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-xs font-medium text-ink-200">
      {children}
    </span>
  );
}

/** Name from server-backed resume JSON (for “what optimize uses” clarity). */
function resumeBasicsName(resume: Resume | null): string | null {
  if (!resume?.basics) return null;
  const raw = (resume.basics as Record<string, unknown>).name;
  return typeof raw === "string" && raw.trim() ? raw.trim() : null;
}

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

export function App() {
  const [apiOk, setApiOk] = useState<LoadState>("idle");
  const [apiVersion, setApiVersion] = useState<string>("");
  const [geminiOn, setGeminiOn] = useState<boolean | null>(null);

  const [user, setUser] = useState<UserPublic | null>(null);
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authBusy, setAuthBusy] = useState(false);
  const [savedResumeAt, setSavedResumeAt] = useState<string | null>(null);
  /** Last known name from GET/PUT/upload — matches what /api/me/optimize tailors from. */
  const [storedProfileName, setStoredProfileName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [jobText, setJobText] = useState("");
  const [parsed, setParsed] = useState<JobParseResult | null>(null);
  const [parseBusy, setParseBusy] = useState(false);

  const [resumeText, setResumeText] = useState("");
  const [resumeErr, setResumeErr] = useState<string | null>(null);

  const [tailored, setTailored] = useState<Resume | null>(null);
  const [matchScore, setMatchScore] = useState<number | null>(null);
  const [tailorBusy, setTailorBusy] = useState(false);
  const [optimizeSavedBusy, setOptimizeSavedBusy] = useState(false);

  const [pdfInfo, setPdfInfo] = useState<{
    filename: string;
    download_url: string | null;
  } | null>(null);
  const [pdfBusy, setPdfBusy] = useState(false);

  const [applyUrl, setApplyUrl] = useState("");
  const [applyPath, setApplyPath] = useState("");
  const [applyBusy, setApplyBusy] = useState(false);
  const [applyResult, setApplyResult] = useState<string | null>(null);

  const [banner, setBanner] = useState<string | null>(null);
  const gradId = useId().replace(/:/g, "");

  const canGeneratePdf = useMemo(() => {
    if (tailored) return true;
    try {
      const data = JSON.parse(resumeText) as Resume;
      return Boolean(data?.basics && data?.skills);
    } catch {
      return false;
    }
  }, [tailored, resumeText]);

  /** Resume row exists on server (required to tailor from stored profile + job). */
  const hasResumeStored = Boolean(user && savedResumeAt);

  const workflowSteps = useMemo(
    () => [
      { label: "Sign in", done: Boolean(user) },
      { label: "Store your resume", done: hasResumeStored },
      { label: "Paste job description", done: jobText.trim().length >= 30 },
      { label: "Get updated resume", done: Boolean(tailored) },
    ],
    [user, hasResumeStored, jobText, tailored]
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
            gemini_configured?: boolean;
            gemini_model?: string;
          };
          setGeminiOn(Boolean(cfg.gemini_configured));
        }
      } catch {
        if (!cancelled) setApiOk("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!getToken()) return;
    let cancelled = false;
    (async () => {
      try {
        const me = await getMe();
        if (cancelled) return;
        setUser(me);
        const mr = await getMyResume();
        if (cancelled) return;
        setSavedResumeAt(mr.updated_at);
        setStoredProfileName(resumeBasicsName(mr.resume));
        if (mr.resume) {
          setResumeText(JSON.stringify(mr.resume, null, 2));
          setResumeErr(null);
        }
      } catch {
        setToken(null);
        setUser(null);
        setSavedResumeAt(null);
        setStoredProfileName(null);
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
        fetch("/samples/sample_resume.json"),
      ]);
      setJobText(await jobR.text());
      setResumeText(JSON.stringify(await resR.json(), null, 2));
      setResumeErr(null);
      setParsed(null);
      setTailored(null);
      setMatchScore(null);
      setPdfInfo(null);
    } catch {
      showError("Could not load sample files. Check that the dev server is running.");
    }
  };

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!authEmail.trim() || !authPassword) {
      showError("Enter email and password.");
      return;
    }
    if (authMode === "register" && authPassword.length < 8) {
      showError("Password must be at least 8 characters (API requirement).");
      return;
    }
    setAuthBusy(true);
    setBanner(null);
    try {
      const fn = authMode === "register" ? registerAccount : loginAccount;
      const { access_token } = await fn(authEmail.trim(), authPassword);
      setToken(access_token);
      const me = await getMe();
      setUser(me);
      setAuthPassword("");
      const mr = await getMyResume();
      setSavedResumeAt(mr.updated_at);
      setStoredProfileName(resumeBasicsName(mr.resume));
      if (mr.resume) {
        setResumeText(JSON.stringify(mr.resume, null, 2));
        setResumeErr(null);
      }
    } catch (err) {
      showError(err instanceof Error ? err.message : "Authentication failed");
      setToken(null);
      setUser(null);
      setStoredProfileName(null);
    } finally {
      setAuthBusy(false);
    }
  };

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    setSavedResumeAt(null);
    setStoredProfileName(null);
    setAuthPassword("");
  };

  const handleSaveToAccount = async () => {
    const base = parseResumeJson();
    if (!base) return;
    if (!user) {
      showError("Sign in to save your resume to your account.");
      return;
    }
    setAuthBusy(true);
    try {
      const mr = await putMyResume(base);
      setSavedResumeAt(mr.updated_at);
      setStoredProfileName(resumeBasicsName(mr.resume ?? base));
      setBanner("Resume saved to your account.");
      window.setTimeout(() => setBanner(null), 4000);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setAuthBusy(false);
    }
  };

  const handleLoadFromAccount = async () => {
    if (!user) return;
    setAuthBusy(true);
    try {
      const mr = await getMyResume();
      setSavedResumeAt(mr.updated_at);
      setStoredProfileName(resumeBasicsName(mr.resume));
      if (mr.resume) {
        setResumeText(JSON.stringify(mr.resume, null, 2));
        setResumeErr(null);
      } else {
        showError("No resume stored yet. Paste JSON or upload a file.");
      }
    } catch (err) {
      showError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setAuthBusy(false);
    }
  };

  const handleResumeFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !user) return;
    setAuthBusy(true);
    try {
      const mr = await uploadResumeFile(file);
      setSavedResumeAt(mr.updated_at);
      setStoredProfileName(resumeBasicsName(mr.resume));
      if (mr.resume) {
        setResumeText(JSON.stringify(mr.resume, null, 2));
        setResumeErr(null);
      }
    } catch (err) {
      showError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setAuthBusy(false);
    }
  };

  const handleOptimizeSaved = async () => {
    if (!user) {
      showError("Sign in or register first — we store your resume on your account.");
      return;
    }
    if (!hasResumeStored) {
      showError(
        "Save your resume first: paste or upload JSON/PDF below, then click Save to account (or Upload)."
      );
      return;
    }
    if (!jobText.trim()) {
      showError("Paste the full job description (step 3), then try again.");
      return;
    }
    setOptimizeSavedBusy(true);
    setBanner(null);
    try {
      const out = await optimizeSavedResume(jobText);
      setTailored(out.resume);
      setMatchScore(out.match_score);
      setPdfInfo(null);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Optimize failed");
    } finally {
      setOptimizeSavedBusy(false);
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

  const parseResumeJson = (): Resume | null => {
    setResumeErr(null);
    try {
      const data = JSON.parse(resumeText) as Resume;
      if (!data.basics || !data.skills) {
        setResumeErr("Resume JSON must include basics and skills.");
        return null;
      }
      return data;
    } catch {
      setResumeErr("Invalid JSON. Fix the resume payload.");
      return null;
    }
  };

  const handleTailor = async () => {
    const base = parseResumeJson();
    if (!base) return;
    if (!jobText.trim()) {
      showError("Add a job description to tailor against.");
      return;
    }
    setTailorBusy(true);
    setBanner(null);
    try {
      const out = await tailorResume({
        base_resume: base,
        job_description: jobText,
      });
      setTailored(out.resume);
      setMatchScore(out.match_score);
      setPdfInfo(null);
    } catch (e) {
      showError(e instanceof Error ? e.message : "Tailor failed");
    } finally {
      setTailorBusy(false);
    }
  };

  const handlePdf = async () => {
    let source: Resume | null = tailored;
    if (!source) {
      try {
        const data = JSON.parse(resumeText) as Resume;
        if (!data.basics || !data.skills) throw new Error("missing fields");
        source = data;
      } catch {
        showError("Fix resume JSON before generating a PDF.");
        return;
      }
    }
    setPdfBusy(true);
    setBanner(null);
    try {
      const name = `resume-${Date.now()}.pdf`;
      const out = await generatePdf(source, name);
      setPdfInfo({ filename: out.filename, download_url: out.download_url });
    } catch (e) {
      showError(e instanceof Error ? e.message : "PDF generation failed");
    } finally {
      setPdfBusy(false);
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

  const downloadHref =
    pdfInfo?.download_url != null
      ? `${window.location.origin}${pdfInfo.download_url}`
      : null;

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
              Sign in → save your resume once → paste any job description → we update your
              stored resume for that role (AI when Gemini is on) and you can export a PDF.
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
            {geminiOn !== null && (
              <span
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium ${
                  geminiOn
                    ? "border-violet-500/30 bg-violet-500/10 text-violet-200"
                    : "border-white/10 bg-white/5 text-ink-400"
                }`}
                title="Gemini-powered tailoring when APP_GEMINI_API_KEY is set"
              >
                Gemini {geminiOn ? "ON" : "off"}
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
          <ol className="grid gap-3 sm:grid-cols-4">
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

        <div className="mb-6">
          <Panel title="1 · Account (save your profile here)" step="◆">
            <p className="mb-4 text-sm text-ink-300">
              We keep your resume on the server so you only paste a job next time. Upload a{" "}
              <strong className="text-ink-200">PDF</strong> or <strong className="text-ink-200">JSON</strong>
              , or type JSON in the editor below — then <strong className="text-ink-200">Save to account</strong>.
            </p>
            {!user ? (
              <form
                className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end"
                onSubmit={handleAuthSubmit}
              >
                <div className="flex min-w-[200px] flex-1 flex-col gap-1">
                  <label className="text-xs font-medium text-ink-400">Email</label>
                  <input
                    type="email"
                    autoComplete="email"
                    className="rounded-xl border border-white/10 bg-surface-900/80 px-3 py-2 text-sm text-ink-100 focus:border-brand/50 focus:outline-none focus:ring-1 focus:ring-brand/30"
                    value={authEmail}
                    onChange={(e) => setAuthEmail(e.target.value)}
                  />
                </div>
                <div className="flex min-w-[200px] flex-1 flex-col gap-1">
                  <label className="text-xs font-medium text-ink-400">
                    Password
                    {authMode === "register" && (
                      <span className="font-normal text-ink-500"> (min 8 characters)</span>
                    )}
                  </label>
                  <input
                    type="password"
                    autoComplete={authMode === "register" ? "new-password" : "current-password"}
                    className="rounded-xl border border-white/10 bg-surface-900/80 px-3 py-2 text-sm text-ink-100 focus:border-brand/50 focus:outline-none focus:ring-1 focus:ring-brand/30"
                    value={authPassword}
                    onChange={(e) => setAuthPassword(e.target.value)}
                    minLength={authMode === "register" ? 8 : undefined}
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className={`rounded-xl px-4 py-2 text-sm font-medium text-ink-200 transition ${
                      authMode === "login"
                        ? "bg-brand/20 text-brand-glow"
                        : "bg-white/5 hover:bg-white/10"
                    }`}
                    onClick={() => setAuthMode("login")}
                  >
                    Log in
                  </button>
                  <button
                    type="button"
                    className={`rounded-xl px-4 py-2 text-sm font-medium text-ink-200 transition ${
                      authMode === "register"
                        ? "bg-brand/20 text-brand-glow"
                        : "bg-white/5 hover:bg-white/10"
                    }`}
                    onClick={() => setAuthMode("register")}
                  >
                    Register
                  </button>
                  <button
                    type="submit"
                    disabled={authBusy}
                    className="rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-surface-900 shadow-lg shadow-brand/20 disabled:opacity-50"
                  >
                    {authBusy ? "…" : authMode === "register" ? "Create account" : "Sign in"}
                  </button>
                </div>
              </form>
            ) : (
              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
                <p className="text-sm text-ink-200">
                  Signed in as <strong>{user.email}</strong>
                  {savedResumeAt && (
                    <span className="ml-2 text-xs text-ink-400">
                      · Resume saved{" "}
                      {new Date(savedResumeAt).toLocaleString(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                      {storedProfileName && (
                        <>
                          {" "}
                          · <strong className="text-ink-300">Profile on server:</strong>{" "}
                          {storedProfileName}
                        </>
                      )}
                    </span>
                  )}
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="rounded-xl border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-ink-100 transition hover:bg-white/10 disabled:opacity-50"
                    onClick={handleLoadFromAccount}
                    disabled={authBusy}
                  >
                    Load from account
                  </button>
                  <button
                    type="button"
                    className="rounded-xl border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-ink-100 transition hover:bg-white/10 disabled:opacity-50"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={authBusy}
                  >
                    Upload PDF / JSON
                  </button>
                  <button
                    type="button"
                    className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-200 transition hover:bg-red-500/20"
                    onClick={handleLogout}
                  >
                    Log out
                  </button>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.json,application/pdf,application/json"
                  className="hidden"
                  onChange={handleResumeFile}
                />
              </div>
            )}
          </Panel>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="flex flex-col gap-6">
            <Panel title="2 · Your resume (we store this for you)" step={2}>
              {user && !hasResumeStored && (
                <div
                  className="mb-3 rounded-xl border border-sky-500/35 bg-sky-500/10 px-3 py-2 text-sm text-sky-100"
                  role="status"
                >
                  <strong className="text-sky-50">Next:</strong> add your resume (paste JSON,{" "}
                  <strong>Upload PDF / JSON</strong>, or <strong>Load samples</strong>), then click{" "}
                  <strong>Save to account</strong>. After that you can paste a job and update your
                  resume for it.
                </div>
              )}
              <p className="mb-3 text-sm text-ink-300">
                Edit JSON here or use <strong className="text-ink-200">Upload PDF / JSON</strong> in
                the account bar — PDFs are converted automatically; review in the editor, then save.
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
              <div className="mb-3 flex flex-wrap gap-2">
                {user && (
                  <button
                    type="button"
                    className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-200 transition hover:bg-emerald-500/20 disabled:opacity-50"
                    onClick={handleSaveToAccount}
                    disabled={authBusy || !canGeneratePdf}
                  >
                    Save to account
                  </button>
                )}
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                <button
                  type="button"
                  className="rounded-xl bg-gradient-to-r from-accent/90 to-amber-500/90 px-4 py-2.5 text-sm font-bold text-surface-900 shadow-lg shadow-amber-500/15 transition hover:brightness-110 disabled:opacity-50"
                  onClick={handleTailor}
                  disabled={tailorBusy}
                >
                  {tailorBusy ? "Tailoring…" : "Tailor (editor JSON)"}
                </button>
                <button
                  type="button"
                  className="rounded-xl border border-brand/40 bg-brand/10 px-4 py-2.5 text-sm font-semibold text-brand-glow transition hover:bg-brand/20 disabled:opacity-50"
                  onClick={handleOptimizeSaved}
                  disabled={optimizeSavedBusy || !user || !hasResumeStored}
                  title={
                    !user
                      ? "Sign in first"
                      : !hasResumeStored
                        ? "Save your resume to your account first"
                        : "Updates your stored resume using the job description (step 3)"
                  }
                >
                  {optimizeSavedBusy
                    ? "Updating resume…"
                    : "Update resume for this job"}
                </button>
              </div>
              <p className="mt-2 text-xs text-ink-400">
                <strong className="text-ink-300">Update resume for this job</strong> calls the API
                with your <strong>saved server profile</strong>
                {storedProfileName ? (
                  <> ({storedProfileName})</>
                ) : null}{" "}
                plus the job text — not unsaved edits in this box. With{" "}
                <code className="rounded bg-white/5 px-1">APP_GEMINI_API_KEY</code> set, Gemini
                rewrites; otherwise the server uses a light heuristic.{" "}
                <strong className="text-ink-300">Tailor (editor)</strong> only uses the JSON here
                (guest / no account save).
              </p>
            </Panel>

            <Panel title="4 · Updated resume & PDF" step={5}>
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
                <details className="mb-4 rounded-xl border border-white/10 bg-surface-900/50">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-ink-100">
                    View tailored JSON
                  </summary>
                  <pre className="max-h-56 overflow-auto border-t border-white/10 p-4 font-mono text-[11px] leading-relaxed text-ink-200">
                    {JSON.stringify(tailored, null, 2)}
                  </pre>
                </details>
              ) : (
                <p className="mb-4 text-sm text-ink-400">
                  Tailor your resume to see the updated JSON and score.
                </p>
              )}

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="rounded-xl border border-brand/40 bg-brand/10 px-4 py-2 text-sm font-semibold text-brand-glow transition hover:bg-brand/20 disabled:opacity-50"
                  onClick={handlePdf}
                  disabled={pdfBusy || !canGeneratePdf}
                >
                  {pdfBusy ? "Building PDF…" : "Generate PDF"}
                </button>
                {downloadHref && (
                  <a
                    className="inline-flex items-center rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-ink-100 transition hover:bg-white/10"
                    href={downloadHref}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Download {pdfInfo?.filename}
                  </a>
                )}
              </div>
            </Panel>

            <Panel title="LinkedIn Easy Apply (advanced)" step={6}>
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
            <Panel title="3 · Job description (what you’re applying to)" step={3}>
              <p className="mb-3 text-sm text-ink-300">
                After your resume is saved, paste the full posting here. We use it to update your
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
                  {parseBusy ? "Parsing…" : "Parse job"}
                </button>
                <button
                  type="button"
                  className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-ink-100 transition hover:bg-white/10"
                  onClick={loadSamples}
                >
                  Load demo files
                </button>
              </div>
              <p className="mt-2 text-xs text-ink-500">
                <strong className="text-ink-400">Load demo files</strong> pulls the bundled{" "}
                <code className="rounded bg-white/5 px-1">sample_resume.json</code> (demo name “Alex
                Rivera”) and a sample job — it replaces the editor. Only use it to try the app; put
                your own JSON in the editor and click <strong>Save to account</strong> so optimize
                uses <em>your</em> resume.
              </p>
            </Panel>

            <Panel title="Parsed role (optional)" step={4}>
              {!parsed ? (
                <p className="text-sm text-ink-400">
                  Run <strong className="text-ink-200">Parse job</strong> to see structured
                  fields here.
                </p>
              ) : (
                <div className="space-y-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-ink-400">
                      Role
                    </p>
                    <p className="font-display text-lg font-semibold text-ink-50">
                      {parsed.role}
                    </p>
                    <p className="mt-1 text-sm text-ink-300">
                      Seniority: <Chip>{parsed.seniority}</Chip>
                    </p>
                  </div>
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-400">
                      Must-have skills
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {parsed.must_have_skills.map((s, i) => (
                        <Chip key={`${s}-${i}`}>{s}</Chip>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-400">
                      Nice-to-have
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {parsed.good_to_have_skills.map((s, i) => (
                        <Chip key={`${s}-${i}`}>{s}</Chip>
                      ))}
                    </div>
                  </div>
                  {parsed.responsibilities.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-400">
                        Responsibilities
                      </p>
                      <ul className="list-inside list-disc space-y-1 text-sm text-ink-200">
                        {parsed.responsibilities.slice(0, 8).map((r) => (
                          <li key={r.slice(0, 40)}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </Panel>
          </div>
        </div>

        <footer className="mt-12 text-center text-xs text-ink-400">
          Development: run API on port 8000 and{" "}
          <code className="rounded bg-white/5 px-1.5 py-0.5 text-ink-200">
            npm run dev
          </code>{" "}
          in <code className="rounded bg-white/5 px-1.5 py-0.5">frontend/</code>. Production:
          build the SPA and serve it with Uvicorn from the repo root.
        </footer>
      </div>
    </div>
  );
}

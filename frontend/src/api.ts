/**
 * Typed helpers for the FastAPI backend (`/api/*`).
 */

/** API origin with no trailing slash. Empty uses same-origin `/api/*` (Vite dev proxy or Netlify rewrites). */
export function getApiOrigin(): string {
  return (import.meta.env.VITE_API_BASE_URL ?? "").trim().replace(/\/$/, "");
}

/** Absolute or same-origin path for API calls. */
export function apiUrl(path: string): string {
  const base = getApiOrigin();
  const p = path.startsWith("/") ? path : `/${path}`;
  return base ? `${base}${p}` : p;
}

export interface JobParseResult {
  role: string;
  seniority: string;
  must_have_skills: string[];
  good_to_have_skills: string[];
  keywords: string[];
  responsibilities: string[];
}

function formatApiErrorBody(text: string): string {
  try {
    const j = JSON.parse(text) as { detail?: unknown };
    if (typeof j.detail === "string") return j.detail;
    if (Array.isArray(j.detail)) {
      const parts = j.detail.map((item: unknown) => {
        if (item && typeof item === "object" && "msg" in item) {
          const o = item as { msg: string; loc?: unknown[] };
          const loc = Array.isArray(o.loc) ? o.loc.filter(Boolean).join(".") : "";
          return loc ? `${loc}: ${o.msg}` : o.msg;
        }
        return String(item);
      });
      return parts.join("; ");
    }
  } catch {
    /* ignore */
  }
  return text;
}

async function parseJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!res.ok) {
    const detail = formatApiErrorBody(text) || res.statusText;
    throw new Error(detail);
  }
  if (!text) return null;
  return JSON.parse(text) as unknown;
}

export async function fetchHealth(): Promise<{ status: string; version: string }> {
  const r = await fetch(apiUrl("/api/health"));
  return parseJson(r) as Promise<{ status: string; version: string }>;
}


export async function parseJob(description: string): Promise<{ job: JobParseResult }> {
  const r = await fetch(apiUrl("/api/parse-job"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
  });
  return parseJson(r) as Promise<{ job: JobParseResult }>;
}

export async function tailorResume(body: {
  base_latex: string;
  job_description?: string;
  job?: JobParseResult;
  force_heuristic?: boolean;
}): Promise<{ tailored_latex: string; match_score: number | null }> {
  const r = await fetch(apiUrl("/api/tailor-resume"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson(r) as Promise<{ tailored_latex: string; match_score: number | null }>;
}



export async function submitApply(
  jobUrl: string,
  resumePath: string
): Promise<{
  success: boolean;
  message: string;
  detail?: Record<string, unknown>;
}> {
  const r = await fetch(apiUrl("/api/apply"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_url: jobUrl, resume_path: resumePath }),
  });
  return parseJson(r) as Promise<{
    success: boolean;
    message: string;
    detail?: Record<string, unknown>;
  }>;
}

export async function renderLatexToPdf(latex: string): Promise<Blob> {
  const r = await fetch(apiUrl("/api/latex-to-pdf"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ latex }),
  });
  const ct = (r.headers.get("content-type") || "").toLowerCase();
  if (!r.ok) {
    const text = await r.text();
    const detail = formatApiErrorBody(text) || r.statusText;
    throw new Error(detail);
  }
  if (ct.includes("text/html")) {
    const text = await r.text();
    throw new Error(
      text.includes("<!DOCTYPE")
        ? "Got the app HTML instead of a PDF. Check Netlify /api/* proxy rules and redeploy."
        : "Server returned HTML instead of a PDF."
    );
  }
  const buf = await r.arrayBuffer();
  return new Blob([buf], { type: "application/pdf" });
}

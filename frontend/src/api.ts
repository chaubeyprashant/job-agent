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

/**
 * Upload a PDF resume + job description, receive a tailored PDF back.
 */
export async function uploadAndTailor(
  file: File,
  jobDescription: string,
): Promise<Blob> {
  const form = new FormData();
  form.append("resume", file);
  form.append("job_description", jobDescription);

  const r = await fetch(apiUrl("/api/upload-and-tailor"), {
    method: "POST",
    body: form,
  });

  if (!r.ok) {
    const text = await r.text();
    const detail = formatApiErrorBody(text) || r.statusText;
    throw new Error(detail);
  }

  return r.blob();
}

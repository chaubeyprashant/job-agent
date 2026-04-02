/**
 * Typed helpers for the FastAPI backend (`/api/*`).
 */

export interface JobParseResult {
  role: string;
  seniority: string;
  must_have_skills: string[];
  good_to_have_skills: string[];
  keywords: string[];
  responsibilities: string[];
}

export interface Resume {
  basics: Record<string, unknown>;
  skills: Record<string, unknown>;
  experience: unknown[];
  projects: unknown[];
  education: unknown[];
}

export const AUTH_TOKEN_KEY = "job_agent_token";

export function getToken(): string | null {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(AUTH_TOKEN_KEY, token);
  else localStorage.removeItem(AUTH_TOKEN_KEY);
}

function authHeaders(json = true): HeadersInit {
  const t = getToken();
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  if (t) h.Authorization = `Bearer ${t}`;
  return h;
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
  const r = await fetch("/health");
  return parseJson(r) as Promise<{ status: string; version: string }>;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserPublic {
  id: number;
  email: string;
}

export async function registerAccount(
  email: string,
  password: string
): Promise<TokenResponse> {
  const r = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return parseJson(r) as Promise<TokenResponse>;
}

export async function loginAccount(email: string, password: string): Promise<TokenResponse> {
  const r = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return parseJson(r) as Promise<TokenResponse>;
}

export async function getMe(): Promise<UserPublic> {
  const r = await fetch("/api/me", { headers: authHeaders() });
  return parseJson(r) as Promise<UserPublic>;
}

export interface MeResumeResponse {
  resume: Resume | null;
  updated_at: string | null;
}

export async function getMyResume(): Promise<MeResumeResponse> {
  const r = await fetch("/api/me/resume", { headers: authHeaders() });
  return parseJson(r) as Promise<MeResumeResponse>;
}

export async function putMyResume(resume: Resume): Promise<MeResumeResponse> {
  const r = await fetch("/api/me/resume", {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify({ resume }),
  });
  return parseJson(r) as Promise<MeResumeResponse>;
}

/** Upload ``.json`` (exact schema) or ``.pdf`` (text extracted and parsed heuristically). */
export async function uploadResumeFile(file: File): Promise<MeResumeResponse> {
  const t = getToken();
  if (!t) throw new Error("Not logged in");
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch("/api/me/resume/upload", {
    method: "POST",
    headers: { Authorization: `Bearer ${t}` },
    body: fd,
  });
  return parseJson(r) as Promise<MeResumeResponse>;
}

export async function optimizeSavedResume(
  jobDescription: string,
  options?: { force_heuristic?: boolean }
): Promise<{
  resume: Resume;
  match_score: number | null;
}> {
  const r = await fetch("/api/me/optimize", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      job_description: jobDescription,
      force_heuristic: options?.force_heuristic ?? false,
    }),
  });
  return parseJson(r) as Promise<{ resume: Resume; match_score: number | null }>;
}

export async function parseJob(description: string): Promise<{ job: JobParseResult }> {
  const r = await fetch("/api/parse-job", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
  });
  return parseJson(r) as Promise<{ job: JobParseResult }>;
}

export async function tailorResume(body: {
  base_resume: Resume;
  job_description?: string;
  job?: JobParseResult;
  force_heuristic?: boolean;
}): Promise<{ resume: Resume; match_score: number | null }> {
  const r = await fetch("/api/tailor-resume", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseJson(r) as Promise<{ resume: Resume; match_score: number | null }>;
}

export async function generatePdf(
  resume: Resume,
  filename?: string
): Promise<{
  pdf_path: string;
  filename: string;
  download_url: string | null;
}> {
  const r = await fetch("/api/generate-pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume, filename }),
  });
  return parseJson(r) as Promise<{
    pdf_path: string;
    filename: string;
    download_url: string | null;
  }>;
}

export async function submitApply(
  jobUrl: string,
  resumePath: string
): Promise<{
  success: boolean;
  message: string;
  detail?: Record<string, unknown>;
}> {
  const r = await fetch("/api/apply", {
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

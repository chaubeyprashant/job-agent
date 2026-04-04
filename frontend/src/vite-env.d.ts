/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** If set (e.g. in Netlify), API calls go here and skip the Netlify proxy (avoids ~26s timeout on long PDF). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

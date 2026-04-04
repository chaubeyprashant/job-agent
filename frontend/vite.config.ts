import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig, loadEnv } from "vite";

/**
 * Injects public site origin into index.html and writes robots.txt + sitemap.xml into dist/.
 * Set VITE_SITE_URL in Netlify (or .env.production.local) to your live URL, no trailing slash.
 */
function seoPlugin(mode: string): Plugin {
  const resolveSiteUrl = (): string => {
    const env = loadEnv(mode, process.cwd(), "");
    const raw = (env.VITE_SITE_URL ?? "").trim().replace(/\/$/, "");
    if (raw) return raw;
    if (mode === "development") return "http://localhost:5173";
    console.warn(
      "[job-agent] VITE_SITE_URL is unset for production build. Set it in Netlify (Site settings → Environment variables) so canonical, Open Graph, and sitemap URLs are correct."
    );
    return "http://localhost:5173";
  };

  return {
    name: "seo",
    transformIndexHtml(html) {
      return html.replaceAll("__SITE_URL__", resolveSiteUrl());
    },
    closeBundle() {
      const base = resolveSiteUrl();
      const outDir = resolve(process.cwd(), "dist");
      writeFileSync(
        resolve(outDir, "robots.txt"),
        [
          "User-agent: *",
          "Allow: /",
          "",
          `Sitemap: ${base}/sitemap.xml`,
          "",
        ].join("\n")
      );
      writeFileSync(
        resolve(outDir, "sitemap.xml"),
        [
          `<?xml version="1.0" encoding="UTF-8"?>`,
          `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">`,
          `  <url>`,
          `    <loc>${base}/</loc>`,
          `    <changefreq>weekly</changefreq>`,
          `    <priority>1.0</priority>`,
          `  </url>`,
          `</urlset>`,
          "",
        ].join("\n")
      );
    },
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), seoPlugin(mode)],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/docs": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/openapi.json": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/redoc": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
}));

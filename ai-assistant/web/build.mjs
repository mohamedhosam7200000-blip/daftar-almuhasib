// dist/        online site (Claude API) — drag onto Netlify Drop.
// dist-local/  offline UI served by `python -m khabeer.local.server`.
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import * as esbuild from "esbuild";

const builds = [
  { out: "dist", entry: "src/entry-claude.js" },
  { out: "dist-local", entry: "src/entry-local.js", offline: true },
];

for (const { out, entry, offline } of builds) {
  rmSync(out, { recursive: true, force: true });
  mkdirSync(out);
  cpSync("public", out, { recursive: true });
  if (offline) {
    // No external requests at all: drop web fonts (system fonts are used).
    const html = readFileSync(`${out}/index.html`, "utf8");
    const stripped = html.replace(/^\s*<link[^>]*fonts\.(googleapis|gstatic)\.com[^>]*>\n/gm, "");
    if (stripped === html) throw new Error("font links not found in index.html");
    // No API key in the offline app: remove the settings dialog and its button.
    const local = stripped
      .replace(/\s*<button id="open-settings"[^>]*>.*?<\/button>/, "")
      .replace(/\s*<dialog id="settings">[\s\S]*?<\/dialog>/, "");
    if (local.includes('id="settings"') || local.includes("open-settings")) throw new Error("settings not stripped");
    writeFileSync(`${out}/index.html`, local);
  }
  await esbuild.build({
    entryPoints: [entry],
    bundle: true,
    minify: true,
    format: "iife",
    target: "es2022",
    platform: "browser",
    outfile: `${out}/app.js`,
    legalComments: "linked",
  });
  console.log(`built ${out}/`);
}

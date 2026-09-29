// dist/        online site (Claude API) — drag onto Netlify Drop.
// dist-local/  offline UI served by `python -m khabeer.local.server`.
import { cpSync, mkdirSync, rmSync } from "node:fs";
import * as esbuild from "esbuild";

const builds = [
  { out: "dist", entry: "src/entry-claude.js" },
  { out: "dist-local", entry: "src/entry-local.js" },
];

for (const { out, entry } of builds) {
  rmSync(out, { recursive: true, force: true });
  mkdirSync(out);
  cpSync("public", out, { recursive: true });
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

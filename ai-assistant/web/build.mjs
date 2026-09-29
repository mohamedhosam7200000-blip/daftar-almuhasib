// Bundle src/ into dist/app.js and copy public/ next to it.
// dist/ is a complete static site: drag it onto Netlify Drop.
import { cpSync, mkdirSync, rmSync } from "node:fs";
import * as esbuild from "esbuild";

rmSync("dist", { recursive: true, force: true });
mkdirSync("dist");
cpSync("public", "dist", { recursive: true });
await esbuild.build({
  entryPoints: ["src/main.js"],
  bundle: true,
  minify: true,
  format: "iife",
  target: "es2022",
  platform: "browser",
  outfile: "dist/app.js",
  legalComments: "linked",
});
console.log("built dist/");

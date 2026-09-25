import { cpSync, existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { resolve } from "node:path";
const root = process.cwd();
const standalone = resolve(root, ".next/standalone");
if (!existsSync(resolve(standalone, "server.js"))) throw new Error("Run npm run build first.");
cpSync(resolve(root, ".next/static"), resolve(standalone, ".next/static"), {recursive: true});
const child = spawn(process.execPath, [resolve(standalone, "server.js")], {
  cwd: standalone, stdio: "inherit", env: {...process.env, HOSTNAME: process.env.FRAUDGRAPH_WEB_HOST || "127.0.0.1", PORT: process.env.PORT || "3000"}
});
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", code => process.exit(code ?? 0));

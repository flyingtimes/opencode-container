/**
 * 补丁：让 opencli 的 daemon 连接地址可通过 OPENCLI_DAEMON_HOST 环境变量覆盖。
 *
 * 背景：opencli 的 daemon-transport.js 把 daemon 地址硬编码为 http://127.0.0.1:19825，
 * 容器里 127.0.0.1 指向容器自身，无法连到宿主机的 daemon。
 * 本补丁将其改为读取 OPENCLI_DAEMON_HOST（默认回退 127.0.0.1，不影响本地直跑）。
 *
 * 注意：opencli 升级后需重新执行此补丁（npm i -g 会覆盖文件）。
 */
import { readFileSync, writeFileSync } from "node:fs";
import { execSync } from "node:child_process";

const root = execSync("npm root -g").toString().trim();
const file = `${root}/@jackwener/opencli/dist/src/browser/daemon-transport.js`;

const before = "const DAEMON_URL = `http://127.0.0.1:${DAEMON_PORT}`;";
const after =
  'const DAEMON_URL = `http://${process.env.OPENCLI_DAEMON_HOST || "127.0.0.1"}:${DAEMON_PORT}`;';

let src = readFileSync(file, "utf8");
if (!src.includes(before)) {
  // 已经打过补丁则跳过（幂等）
  if (src.includes("OPENCLI_DAEMON_HOST")) {
    console.log(`[patch] already patched, skip: ${file}`);
    process.exit(0);
  }
  throw new Error(`[patch] target string not found in ${file}`);
}
writeFileSync(file, src.replace(before, after));
console.log(`[patch] done: ${file}`);

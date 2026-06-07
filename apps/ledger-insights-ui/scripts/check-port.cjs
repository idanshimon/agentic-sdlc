#!/usr/bin/env node
/**
 * Preflight: refuse to start if the dev/start port is already in use.
 *
 * Reads PORT from env (default 3005). Uses `lsof -nP -iTCP:<port> -sTCP:LISTEN`
 * — works on macOS and most Linux distros without extra deps.
 *
 * Exits 0 if free, 1 with a readable message if taken.
 */
const { execSync } = require("node:child_process");

const port = process.env.PORT || "3005";

let listener = "";
try {
  listener = execSync(`lsof -nP -iTCP:${port} -sTCP:LISTEN`, {
    stdio: ["ignore", "pipe", "ignore"],
  })
    .toString()
    .trim();
} catch {
  // lsof exits non-zero when nothing matches — that's the happy path.
  listener = "";
}

if (!listener) {
  console.log(`✓ port ${port} free`);
  process.exit(0);
}

console.error(`✗ port ${port} is already in use:\n${listener}`);
console.error(
  `\nKill it first:  lsof -nP -iTCP:${port} -sTCP:LISTEN -t | xargs kill -9`,
);
console.error(`Or pick another port: PORT=3006 pnpm dev`);
process.exit(1);

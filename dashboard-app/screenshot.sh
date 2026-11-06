#!/bin/sh
# Screenshot one dashboard tab with headless Chrome, for headless review runs
# (the Polish button allowlists exactly this script).
#
#   sh dashboard-app/screenshot.sh <tab> <width>   e.g.  today 390  |  run 1280
#
# Writes dashboard-app/runs/shots/<tab>-<width>.png and prints the path. Reads
# the always-on server on 127.0.0.1:8000, which hot-reloads templates and
# static files; app.py edits need `launchctl kickstart` first.
set -eu

tab=${1:?usage: screenshot.sh <tab> <width>}
width=${2:?usage: screenshot.sh <tab> <width>}
case $tab in *[!a-z0-9-]*)
	echo "tab must be [a-z0-9-]" >&2
	exit 2
	;;
esac
case $width in '' | *[!0-9]*)
	echo "width must be a number" >&2
	exit 2
	;;
esac

chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
out="$(cd "$(dirname "$0")" && pwd)/runs/shots"
mkdir -p "$out"
file="$out/$tab-$width.png"

# Chrome happily screenshots an error page, so check the server first.
curl -sf -o /dev/null "http://127.0.0.1:8000/" || {
	echo "dashboard on 127.0.0.1:8000 did not return 200" >&2
	exit 1
}

# Set the viewport via DevTools. --window-size alone is clamped by Chrome's
# minimum desktop window width and silently crops narrow screenshots.
node --input-type=module - "$chrome" "$file" "$tab" "$width" <<'JS'
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [chrome, file, tab, widthText] = process.argv.slice(2);
const width = Number(widthText);
if (!Number.isInteger(width) || width < 320 || width > 2560) {
  throw new Error("width must be between 320 and 2560");
}
const profile = mkdtempSync(join(tmpdir(), "dashboard-shot-"));
const child = spawn(chrome, [
  "--headless=new", "--disable-gpu", "--hide-scrollbars",
  "--no-first-run", "--no-default-browser-check",
  `--user-data-dir=${profile}`, "--remote-debugging-pipe",
], { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"] });
const pending = new Map();
let nextId = 0;
let buffer = "";
function call(method, params = {}, sessionId) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    pending.set(id, { resolve, reject });
    child.stdio[3].write(JSON.stringify({ id, method, params, sessionId }) + "\0");
  });
}
child.stdio[4].setEncoding("utf8");
child.stdio[4].on("data", chunk => {
  buffer += chunk;
  let end;
  while ((end = buffer.indexOf("\0")) >= 0) {
    const message = JSON.parse(buffer.slice(0, end));
    buffer = buffer.slice(end + 1);
    const request = pending.get(message.id);
    if (!request) continue;
    pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message));
    else request.resolve(message.result);
  }
});
child.on("error", error => {
  for (const request of pending.values()) request.reject(error);
});
const exited = new Promise(resolve => child.once("close", resolve));
child.on("exit", () => {
  for (const request of pending.values()) request.reject(new Error("Chrome exited"));
});
const deadline = setTimeout(() => {
  for (const request of pending.values()) request.reject(new Error("Screenshot timed out"));
  child.kill("SIGKILL");
}, 30000);
try {
  const { targetId } = await call("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await call("Target.attachToTarget", { targetId, flatten: true });
  const page = (method, params) => call(method, params, sessionId);
  await page("Emulation.setDeviceMetricsOverride", {
    width, height: 2400, deviceScaleFactor: 1, mobile: width <= 640,
  });
  // Fetch the same page only after emulation is active.
  await page("Page.navigate", { url: `http://127.0.0.1:8000/#${tab}` });
  await page("Runtime.evaluate", {
    expression: `(async () => {
      while (document.readyState !== "complete" ||
             !document.querySelector("#page-${tab}.active")) {
        await new Promise(resolve => setTimeout(resolve, 50));
      }
      await document.fonts.ready;
      await new Promise(resolve => setTimeout(resolve, 500));
    })()`,
    awaitPromise: true,
  });
  const { data } = await page("Page.captureScreenshot", { format: "png" });
  writeFileSync(file, Buffer.from(data, "base64"));
  console.log(file);
} finally {
  child.kill();
  await exited;
  clearTimeout(deadline);
  rmSync(profile, { recursive: true, force: true });
}
JS

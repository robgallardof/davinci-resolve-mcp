// Runs agent-written JavaScript inside a Deno process started with every permission denied.
// Line-delimited JSON over stdin/stdout is its only channel. The host re-checks every message:
// nothing here is a security control, so code that tampers with this file's helpers gains nothing.
const { stdin, stdout, exit } = Deno;
const { stringify, parse } = JSON;
const encoder = new TextEncoder();
const decoder = new TextDecoder();
const AsyncFunction = (async () => {}).constructor;
const LOG_BYTES = 16384;

function send(message) {
  let bytes = encoder.encode(stringify(message) + "\n");
  while (bytes.length) bytes = bytes.subarray(stdout.writeSync(bytes));
}

const pending = new Map();
const lines = [];
let wake = null;
let nextId = 1;

(async function pump() {
  const chunk = new Uint8Array(65536);
  let text = "";
  for (;;) {
    const count = await stdin.read(chunk);
    if (count === null) exit(0); // the host went away
    text += decoder.decode(chunk.subarray(0, count), { stream: true });
    let end;
    while ((end = text.indexOf("\n")) >= 0) {
      const message = parse(text.slice(0, end));
      text = text.slice(end + 1);
      if (message.t === "reply" && pending.has(message.id)) {
        pending.get(message.id)(message.result);
        pending.delete(message.id);
      } else {
        lines.push(message);
        if (wake) wake();
      }
    }
  }
})();

class CapabilityError extends Error {
  constructor(tool, reply) {
    super(reply.error ?? `${tool} failed`);
    this.name = "CapabilityError";
    this.tool = tool;
    this.code = reply.code;
    this.hint = reply.hint;
  }
}

function capability(tool) {
  return (args = {}) =>
    new Promise((resolve, reject) => {
      const id = nextId++;
      pending.set(id, (reply) => (reply.ok === false ? reject(new CapabilityError(tool, reply)) : resolve(reply)));
      send({ t: "call", id, tool, args });
    });
}

// Timing helpers: integers over rational rates, so long timelines do not accumulate float error.
const NTSC = { 23.976: [24000, 1001], 29.97: [30000, 1001], 47.952: [48000, 1001], 59.94: [60000, 1001] };

function rate(fps) {
  const known = NTSC[Number(fps).toFixed(3).replace(/0+$/, "")];
  if (known) return known;
  if (!Number.isInteger(fps) || fps <= 0) throw new RangeError(`Unsupported frame rate ${fps}`);
  return [fps, 1];
}

const timecode = Object.freeze({
  rate,
  secondsToFrame: (seconds, fps) => {
    const [n, d] = rate(fps);
    return Math.round((seconds * n) / d);
  },
  frameToSeconds: (frame, fps) => {
    const [n, d] = rate(fps);
    return (frame * d) / n;
  },
  frameToTimecode: (frame, fps, { dropFrame = false } = {}) => {
    if (!Number.isInteger(frame) || frame < 0) throw new RangeError("frame must be a non-negative integer");
    const [n, d] = rate(fps);
    const base = Math.ceil(n / d);
    let shown = frame;
    if (dropFrame) {
      if (d !== 1001 || base % 30 !== 0) throw new RangeError("Drop-frame timecode only exists at 29.97 and 59.94");
      const drop = base / 15;
      const perTen = base * 600 - drop * 9;
      const perMinute = base * 60 - drop;
      const tens = Math.floor(frame / perTen);
      const rest = frame % perTen;
      shown += drop * 9 * tens + (rest >= drop ? drop * Math.floor((rest - drop) / perMinute) : 0);
    }
    const pad = (value) => String(value).padStart(2, "0");
    const [h, m, s] = [Math.floor(shown / (base * 3600)), Math.floor(shown / (base * 60)) % 60, Math.floor(shown / base) % 60];
    return `${pad(h)}:${pad(m)}:${pad(s)}${dropFrame ? ";" : ":"}${pad(shown % base)}`;
  },
});

const logs = [];
let logBytes = 0;
function log(...parts) {
  if (logBytes >= LOG_BYTES) return;
  const line = parts.map((part) => (typeof part === "string" ? part : stringify(part) ?? String(part))).join(" ");
  logBytes += line.length;
  logs.push(line.slice(0, LOG_BYTES));
}

const config = await new Promise((resolve) => {
  wake = () => resolve(lines.shift());
  if (lines.length) wake();
});

// Everything that could leave the sandbox, even though the process permissions already refuse it.
for (const name of ["Deno", "fetch", "WebSocket", "WebSocketStream", "EventSource", "Worker", "BroadcastChannel",
                    "caches", "localStorage", "sessionStorage", "navigator", "process", "Buffer"]) {
  delete globalThis[name];
}
globalThis.console = Object.freeze({ log, info: log, warn: log, error: log, debug: log });
globalThis.CapabilityError = CapabilityError;
globalThis.timecode = timecode;
globalThis.resolve = Object.freeze(Object.fromEntries(config.tools.map((tool) => [tool, capability(tool)])));
globalThis.run = Object.freeze({
  mode: config.mode,
  check: (label, passed, details) => {
    send({ t: "check", label: String(label), passed: passed === true, details: details ?? null });
    return passed === true;
  },
});

try {
  const value = await new AsyncFunction(`"use strict";\n${config.code}`)();
  send({ t: "done", result: value === undefined ? null : value, logs });
} catch (error) {
  send({ t: "error", name: error?.name ?? "Error", message: String(error?.message ?? error), code: error?.code ?? null, logs });
}
exit(0);

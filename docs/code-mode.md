# Code Mode

A way for an agent to compose Resolve operations by writing JavaScript, instead of calling tools one at a time. It runs
entirely on your machine, with no account or paid service. The idea comes from Cloudflare's
[Code Mode](https://blog.cloudflare.com/code-mode-mcp/) (search + execute); the implementation here is our own.

It is always available, beside the direct tools. Its runtime, Deno, is a regular dependency (about 94 MB on Windows;
PyPI has no wheel for Windows on ARM). `uv run resolve-forge-doctor` shows whether it is found. If it is missing,
`execute` reports `MISSING_DEPENDENCY` and the direct tools keep working.

## When to use it

Measured in [code-mode-benchmarks.md](code-mode-benchmarks.md), with these limits: the workflows are replayed scripts
on a fake Resolve, not a real model on real footage.

| You want | Use |
|---|---|
| A single simple call | A direct tool: through `execute` it took about 2.5 times the traffic |
| Several steps, reads filtered down to what matters | `execute`: about a third less traffic |
| Several edits with one approval, and fewer round trips | `execute` then `approve_execution` |

Code Mode's four tools add to the list every conversation pays for; they do not replace the others. Without a prompt
cache, every extra round trip re-sends that list, so the timeline inspection cost more input through Code Mode (one more
round trip) even with less traffic, while the long edit cost about half (three fewer).

| Variable | Default | Meaning |
|---|---|---|
| `RESOLVE_FORGE_CODE_MODE_TIMEOUT_MS` | `10000` | Script running time; time inside tool calls does not count |
| `RESOLVE_FORGE_CODE_MODE_WALL_MS` | `600000` | A whole run, tool calls included |
| `RESOLVE_FORGE_CODE_MODE_MAX_OUTPUT_BYTES` | `65536` | Reply to the model; beyond it, parts are truncated and marked |
| `RESOLVE_FORGE_CODE_MODE_MEMORY_MB` | `128` | Script heap; the process ceiling is this plus 256 MB for Deno itself |
| `RESOLVE_FORGE_CODE_MODE_MAX_CALLS` | `200` | Tool calls in one run |
| `RESOLVE_FORGE_CODE_MODE_APPROVAL` | `client` | `elicitation` refuses to apply on a client that cannot prompt the user |
| `RESOLVE_FORGE_CODE_MODE_TRACE` | `~/.resolve-forge/code-mode-traces.jsonl` | Audit log |

An invalid value stops the server with a clear message. It never falls back to something weaker. Nothing in Code Mode is
specific to one client: these are ordinary MCP tools. It has been tested through a real stdio MCP session (the Python SDK);
the individual clients have not each been run against it.

## The tools

| Tool | What it does |
|---|---|
| `search` | Finds operations. No arguments: categories. `query`, `category`, `risk`: compact matches. `names`: full schemas |
| `execute` | Runs a script. Reads run; state-changing calls become a plan |
| `approve_execution` | Applies a plan |
| `cancel_execution` | Stops the active run |

Inside a script: `resolve.<tool>(args)` for every tool `search` lists, `run.mode`, `run.check(label, passed, details)`,
`timecode.*` and `console.log`. Failures throw `CapabilityError` with `.code` and `.hint`, the same codes as the direct tools.

### Plan, approve, verify

```javascript
// execute: stage "plan"
const clips = (await resolve.list_clips({track: 1})).clips;
const long = clips.filter(c => c.duration >= 300).map(c => c.index);
const edit = await resolve.edit_clips({properties: {ZoomX: 1.2, ZoomY: 1.2}, indices: long, copy_name: 'Cut A', dry_run: false});

if (run.mode === 'apply') {           // the second pass, after approval
  const after = (await resolve.list_clips({track: 1})).clips;
  run.check('zoom applied', long.every(i => Number(after[i - 1].zoom) === 1.2));
}
return {long, timeline: edit.timeline};
```

1. `execute` runs the script. `edit_clips` is answered with the tool's own preview and recorded; nothing changes. The
   reply has `status: "needs_approval"`, a `plan_id` and every operation with its arguments and preview.
2. The agent shows that to you, then calls `approve_execution(plan_id)`.
3. The same script runs again. Each state-changing call must be exactly the next approved one.

Passing `dry_run: false` is how a script says "this is a real edit". Without it, the call is just a preview.

### Status of a run

| `status` | Meaning |
|---|---|
| `success` | Finished, and every edit was verified by the tool's readback or a passing `run.check` |
| `needs_approval` | A plan is ready. Nothing changed |
| `partial` | Some steps ran and others failed or did not run. See `applied`, `not_run` and `recovery` |
| `blocked` | Refused before any edit (not approved, stale, denied, preflight missing) |
| `failed` | The script or sandbox failed before any edit |
| `unverified` | Edits ran, but nothing read them back. Check them before relying on them |
| `contradictory` | A readback or `run.check` disagrees with what should have happened |
| `cancelled`, `timeout` | Stopped. Anything already applied stays, and `applied` lists it |

Catching an error in the script does not make the run a success. Runs are **not atomic**: Resolve has no transactions,
so nothing is rolled back. Timeline edits land on copies, so the source timeline stays as it was.

## Workflows

Each runs against the fake Resolve in `tests/integration/test_code_mode.py`.

**Timeline analysis (read-only)**
```javascript
const status = await resolve.forge_status();
const audit = await resolve.audit_timeline();
const clips = (await resolve.list_clips({track: 1})).clips;
return {timeline: status.timeline, clips: clips.length,
        ends: clips.map(c => timecode.frameToTimecode(c.start + c.duration, status.fps)),
        gaps: audit.issues.filter(i => i.code === 'GAP' || i.code === 'OVERLAP')};
```

**Short-form edit.** The example above, plus `make_platform_version` for the vertical copy. Face-based framing needs the
`vision` extra; `locate_subject` says what it found. Nothing here guesses a speaker or a reframe.

**Subtitles.** `transcribe_timeline(include_words: true)` or `align_text`, fix the timing in JavaScript, then
`add_captions({words})`. Existing captions cannot be edited in place: a corrected set goes on a new track of a copy.

**Media organisation.** `list_media`, then `organise_media({by: 'extension' | 'directory', dry_run: false})`. Those are
the only groupings a tool offers; arbitrary moves between bins are not available.

**Render preparation**
```javascript
const check = await resolve.preflight_render({format: 'youtube_1080'});
if (!check.technical_passed) return {problems: check.issues};
const job = await resolve.render_for({format: 'youtube_1080', name: 'final_v2', start: false});
return {job: job.job_id ?? null};
```
`start: false` queues without rendering. A started render does not hold the run open: poll `render_status` afterwards.
`preflight_render` is technical only. You still have to look at `review_shots` and `review_video` sheets.

## What it protects, and how

The rules are the existing tools' rules, because every call goes through FastMCP's own dispatch into the same handlers:
same validation, same `dry_run` defaults, same copies, same error codes. On top of that, Code Mode adds:

| Risk | Control |
|---|---|
| Unapproved edit | Host-side gate on every call: state-changing tools need a plan that the sandbox has no way to approve |
| Script does something other than what was approved | Ordered match on tool and exact arguments; the first mismatch halts all later edits |
| Approving an old plan | One shot, 15-minute expiry, refused if the project, timeline, tracks or any clip's name/position changed |
| Editing during a render, or another agent writing | Refused during a render; direct writes get `RESOLVE_BUSY` while edits apply; one run at a time |
| Overwriting a render | `render_for` refuses an existing output unless `overwrite=true`. This applies to direct calls too |
| Rendering unchecked | `render_for` needs a passing `preflight_render` of the same format in that script |
| A new tool slipping in | A tool missing from the table in `domain/code_mode.py` is denied, and a test fails until it is classified |
| Reporting success falsely | A status never reads better than its worst step; an edit with no readback is `unverified` |

**Source media.** No tool deletes, overwrites, relinks or replaces source files, so a script cannot either.

### The sandbox

Each run is a new Deno process with every permission denied, an empty environment and an empty temporary working
directory. Its only channel is JSON lines over stdin/stdout. The host treats everything on that channel as untrusted.

| Control | How it is enforced | Tested by |
|---|---|---|
| Files, environment, network, processes, native code | Deno permissions (no `--allow-*`, explicit `--deny-*`) | A hostile script with Deno intact, 18 attack paths |
| Remote modules | `--no-remote`, `--no-npm`, `--deny-import` | Same |
| Script time | Host kills the process at the deadline | Infinite loops, unresolved promises, microtask loops |
| Memory, heap | V8 `--max-old-space-size` | Allocation bomb |
| Memory, off-heap | Windows: job object. Linux, macOS: resident-size watchdog polling every 50 ms | Buffer bomb |
| Child processes | Windows: job object limit of 1. All: Deno permissions | Spawn attempts |
| CPU | The script deadline, plus `RLIMIT_CPU` on Linux and macOS | Infinite loop |
| Output | Message and reply limits; floods end the run | Oversized and garbage messages |
| Sandbox outlives the server | Windows: job closes with the server. Others: exits when stdin closes; `RLIMIT_CPU` bounds a stuck loop | Not directly tested |

If a control cannot be applied (no runtime, job object refused, memory unreadable), the run is refused. There is no
insecure fallback.

### What it does not protect against

- **A V8 or Deno exploit.** Deno's permissions live in the same process as the JavaScript engine. An engine escape would
  run with your user account's rights, limited on Windows by the job object. There is no AppContainer, seccomp or
  Landlock layer. For hostile input, run the server in the [Docker image](docker.md), which adds a read-only filesystem
  and no capabilities.
- **The agent approving itself.** On a client without a user prompt, `approve_execution` is an ordinary tool call marked
  destructive, so the human gate is your client's tool permission. If your client auto-approves tools, so is this one.
  That matches the direct tools, where an agent can pass `dry_run=false`. Set
  `RESOLVE_FORGE_CODE_MODE_APPROVAL=elicitation` to refuse unless the client can prompt you.
- **Analysis side effects.** Analysis tools given a file path may import that file into the Media Pool, before any
  approval, as they do directly. Reads, analysis and review sheets may write caches and new files outside the project.
- **What tools can read.** A script can pass any path to a tool, as an agent can directly. A script cannot read the file
  itself, but what a tool returns reaches the model.
- **Unverifiable results.** A preview can differ from what really happens: step 2's preview runs against the state before
  step 1 is applied. Tools measure; they do not see. Visual review still applies.
- **Stopping Resolve mid-call.** Cancelling never interrupts a Resolve call in progress. It finishes, then the run stops.

## Frame accuracy

Scripts get integer frame positions from the tools. `timecode` uses rational rates (30000/1001 for 29.97) and exact
drop-frame maths, and refuses drop-frame at rates where it does not exist.

The existing tools still accept seconds and convert with `round(seconds * fps)`, using the rate Resolve reports. Code
Mode did not change them. Markers and cut lists are rounded to whole frames, so errors do not accumulate between
calls, but sub-frame intent is lost. Prefer positions read from `list_clips`.

## Resolve compatibility

Code Mode reaches Resolve only through the existing `Session`, so it supports what the server supports: the bridge and
direct scripting, Free and Studio, with the behaviour in [api-behavior.md](api-behavior.md). It adds no licensing
bypass and no assumption about an edition. Availability is observed at runtime (`list_capabilities`), and an unavailable
feature returns the tool's usual `BACKEND_UNSUPPORTED`.

**Not offered, because no tool can do it:** native transitions, trimming clips in place, deleting anything, relinking
media and arbitrary bin moves. `search` says so when asked.

## Why these choices

**Why not replace the direct tools?** Intent-level tools are already cheap per call, and simple reads came out worse
through Code Mode. Hiding them would shrink the tool list by about 13,000 tokens but force every call through a script.

**Why Deno?** Measured on Windows, November 2026:

| Runtime | Startup | Finding |
|---|---:|---|
| Deno 2.9 (`deno` on PyPI) | 38 ms | Denies files, env, network, processes and FFI by default, across workers and `node:` modules. Wheels for Windows, macOS, Linux on x64 and arm64 |
| Node 24 `--permission` | 39 ms | **Network still allowed** (a real request returned 200). Rejected |
| QuickJS (`quickjs` on PyPI) | 45 ms | Last release 2023. Embedded only, needs its own process boundary. Rejected |
| V8 (`mini-racer`) | 209 ms | Embedded only, no permission layer. Rejected |

**Why `search` is not code, unlike Cloudflare's?** They search 2,500+ endpoints. Here there are a few dozen tools, so a
keyword query is enough and saves a sandbox start.

**Why run the script twice?** So it can read back between steps and report the result in one approval. Replaying a
stored list would need another `execute` to verify.

## Troubleshooting

| Code | Meaning | Do this |
|---|---|---|
| `MISSING_DEPENDENCY` | No Deno runtime | `uv sync` (with your extras) in `mcp/resolve-forge`, restart the server |
| `SANDBOX_UNAVAILABLE` | A limit could not be applied | Read the message; direct tools still work |
| `SANDBOX_MEMORY_LIMIT` | Over the memory limit | Filter earlier, or raise `..._MEMORY_MB` |
| `CODE_MODE_TIMEOUT` | Over the script time | Raise `..._TIMEOUT_MS`. Slow tool calls count only against `..._WALL_MS` |
| `OUTPUT_LIMIT`, `RESULT_TOO_LARGE` | A message was too big | Return less, or narrow the tool call |
| `CALL_LIMIT` | Too many calls | Raise `..._MAX_CALLS`, or use fewer calls |
| `CODE_MODE_BUSY` | Another run is active | Wait, or `cancel_execution` |
| `CODE_MODE_DENIED` | Tool unavailable in Code Mode | `repair_bridge_connection` must be called directly |
| `PLAN_NOT_FOUND` | Used, expired or unknown | `execute` again |
| `STALE_STATE` | Resolve changed after planning | Inspect, then `execute` again |
| `NOT_APPROVED` | The script's second pass differed | Keep edit arguments the same in both passes; use `run.mode` only around reads |
| `RUN_HALTED` | An earlier approved step failed | See `applied` and `recovery` |
| `PREFLIGHT_REQUIRED` | No passing preflight for that format | Call `preflight_render` in the script and fix what it reports |
| `APPROVAL_DECLINED`, `APPROVAL_UNAVAILABLE` | Declined, or strict mode on a client without prompts | See the hint |

Every run is logged to the trace file with its code, calls and outcome.

## Verification status

| Layer | Status |
|---|---|
| Fake Resolve, real tools, real sandbox, real stdio (Windows) | Executed, passing |
| Same suites on Linux in a container, non-root | Executed, passing |
| Same suites on macOS, in CI | Executed, passing (fake Resolve) |
| Real Resolve Free 21.0.4.5 on Windows, through the bridge (`uv run pytest -m live tests/live/test_live_code_mode.py`) | Executed once on 2026-11-02, passing: inspect a timeline, plan and approve markers on a copy, read back exact frames, source unchanged, plan refused on reuse |
| Other edits on a real Resolve (zoom, captions, media organisation, render) | **Not executed.** Only on the fake |
| Real Resolve Studio, or on macOS or Linux | **Not executed** |
| Real agents, real models, a client's approval prompt | **Not executed.** Benchmarks replay fixed scripts; the live run approved by tool call |

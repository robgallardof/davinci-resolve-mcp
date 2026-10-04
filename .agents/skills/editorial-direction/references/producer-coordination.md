# Producer references and coordination

Read this reference for pieces with several specialists, visual references or multi-shot composition.
The producer owns final decisions and MCP writes; specialists propose from evidence.

## Interpreting the reference

Separate what is observed from how it applies: sources/angles, real subjects, temporal continuity, panel
hierarchy, text and narrative function. Do not infer four participants because there are four images: they may
be different takes of the same person. Interview + photo + camera shot may suggest support,
context or story; it does not require keeping a collage for the whole duration.

For each idea record `observation`, `candidate`, `reason`, `use_when`, `avoid_when` and `available_sources`.
If equivalent takes are missing, choose an honest adaptation (verified crop, available B-roll, another layout);
do not promise a new perspective from a single shot. The number of people alone does not choose a layout.
Two horizontal speakers in a vertical can alternate faces on confirmed turns with protected reactions;
a large group may work better with rotation/wide shot than with illegible thumbnail faces.

## Brief and proposal contract

Give every specialist the same `job_id`, goal/genre, observed references, format/dimensions/FPS,
project/timeline and version, working copy, sources with stable ids/ranges, confirmed cut,
authority limits, task owner, dependencies and acceptance. Source and timeline ranges differ: use
seconds relative to their declared start, `[start, end)` intervals, and keep offsets/FPS for conversion.
When the cut changes, bump the version and remap; a plan based on an older version is not applied.
`plan_production` produces these work orders from the brief; specialists fill in the proposals.

Use JSON for the proposal; this is a coordination contract, not an MCP tool or an implemented schema:

```json
{
  "job_id": "reel-01",
  "owner": "composition-editor",
  "base_version": "cut-v2",
  "target": {"project": "Project", "timeline": "Reel_COPY", "format": "vertical"},
  "depends_on": ["cut-v2"],
  "observations": [{"evidence": "frame-001.png", "finding": "The reference combines takes of one person"}],
  "proposals": [{
    "id": "composition-01",
    "source_id": "clip-A",
    "source_range_s": [4.0, 7.0],
    "timeline_range_s": [0.0, 3.0],
    "reason": "Bring the confirmed reaction closer",
    "operation": {"tool": null, "args": {}, "schema_verified": false},
    "acceptance": ["Complete face at start, middle and end", "No zoom jump"],
    "evidence_required": ["before_after_same_time", "readback"],
    "uncertainties": []
  }],
  "blockers": [],
  "status": "proposed"
}
```

`operation.tool` and `args` are only filled with names/parameters of available tools and inspected schemas;
if unavailable leave null and describe the desired operation. Never invent a tool to satisfy the contract.
For existing planning tools, attach their results and warnings without confusing them with execution.
People/boxes/turns include evidence and confidence; never label a detection as confirmed without review.

## Serial application and evidence

Only the coordinator executes MCP mutations and operations that select a project/timeline. Specialists
use copies of local artifacts for parallel work. Reading state is not permission to change it.
Before applying: correct active target, current version, verified arguments, dependencies satisfied and
preview/dry-run reviewed when it exists. After applying: record the result, readback, visual/audio evidence and
the new version. Distinguish `planned`, `applied`, `verified`, `failed`; never declare verified from a successful return alone.
On timeout/failure inspect state to learn whether anything changed before retrying.

Composition/cut precede text and audio sync. Audio and color can be analysed in parallel with geometry,
but their application is serialised. New trims invalidate cues; new panels invalidate text zones. QA
returns `severity`, `timeline_range_s`, `evidence`, `owner`, `fix`, `acceptance` and status; the producer resolves
aesthetic conflicts and reassigns defects. No final render with open blockers. Save the project first.

Pre-render QA: visual review of shots and animations, text accuracy, listening to the mix and
`preflight_render`. Post-render QA: the real file, specs/measurements and an observed `review_video` plus listening.
Report coverage and open items, not a promise of perfection. A contact sheet does not prove every frame;
correct LUFS does not prove intelligibility; LUT readback does not prove natural skin.

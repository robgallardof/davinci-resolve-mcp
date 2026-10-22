# Transitions and editorial flow

Read when improving transitions, smoothness, continuity or a complete polished edit.
This is editorial guidance, not a declaration of new MCP capabilities.

## Choose the join from the story

Start with a clean cut. For each noticeable join, identify what connects the outgoing and incoming shots:
action, gaze, shape, sound, an idea, a musical phrase or a deliberate change of time/place.
Protect complete words, breaths needed for meaning, demonstrations, jokes and reactions.
Review neighboring shots together; a good isolated shot can still make a bad sequence.

| Situation | Preferred approach | Check |
|---|---|---|
| Continuous action | Cut on matching action | Movement phase, direction, subject position and screen geography |
| Talking-head retake | Finished thought, relevant B-roll or a purposeful framing change | No clipped syllables, distracting pose jump or repeated gesture |
| Interview or story | J-cut to introduce incoming sound; L-cut to retain outgoing sound | Speech remains intelligible; do not fabricate responses or overlap competing sentences |
| Time passing or reflective passage | Short dissolve if it clarifies the passage | Enough source handles; no doubled faces, unreadable titles or accidental opacity dip |
| Chapter or ending | Motivated fade or deliberate pause | Black/silence is intentional and recorded for QA |
| Energetic music or action | Cut on a confirmed beat, phrase or movement | The beat does not interrupt the action or destroy musical contrast |
| Stylized reference | Match its transition vocabulary selectively | Establish direction before a whip/zoom; land on a readable stable frame |

Use one coherent transition vocabulary for the piece. A dissolve or whip at every cut makes timing
harder to read. Prefer purposeful variety of shot size and sound continuity to accumulating effects.
Reduced-motion work should favor clean cuts and restrained fades.

## Timing and execution

- Record each designed join: outgoing/incoming source ranges, timeline time, visual/audio treatment,
  duration, reason and review status. Label source seconds separately from timeline seconds.
- As starting points, audition dissolves around 0.2–0.5 s and stylized accents around 0.1–0.25 s;
  choose duration from the actual movement, tempo and destination, not a fixed template.
  Convert seconds to whole frames at the timeline fps and verify the realized duration.
- Check available source handles before overlapping clips. Do not silently shorten the story, repeat
  frames, freeze tails or desynchronize the audio to create a transition.
- Keep the music master continuous unless the brief calls for a music edit. Smooth dialogue edits
  with matched room tone and short fades where supported; listen for clicks, ambience jumps and pumping.
- Ease camera starts/stops where appropriate. Match direction, scale and subject position at boundaries,
  or make the change clearly intentional. Avoid an unexplained snap back to the original framing.
- Finish cuts and transitions before final captions. Recheck caption timing, speaker changes, safe zones,
  audio cues and total duration after every timing change. Match exposure/white balance between shots
  before choosing a look; confirm text stays legible during overlaps.

## Capability boundary

Inspect the available tool schemas and `docs/api-behavior.md` before execution. Current Forge assembly
and motion tools do not imply native timeline transition insertion or arbitrary J/L audio trimming.
Never invent `add_transition`, pass unsupported transition arguments, or equate a camera zoom/text fade
with a transition between clips. Preserve existing Fusion effects.

Where a verified tool or supported UI workflow can execute the treatment, work on a copy, preview a
short section and read back the result. If execution is unavailable, complete supported improvements
and record the exact pending join/treatment. Report it as pending rather than claiming it was applied.
Do not flatten or replace the whole edit just to hide an unsupported operation.

## Watch and listen across the boundaries

Contact sheets are useful for composition, but cannot prove temporal smoothness. Play every designed
transition with sound, including roughly one second before and after (longer for dialogue or music).
Inspect the first/last frames and any overlap for black gaps, ghosting, flash frames, repeated/frozen
frames, edge exposure, scale snaps and unintended speed changes. Listen for clicks, cut-off words,
music phase/level jumps and missing ambience. Recheck after rendering.

If playback/listening is unavailable, state that limit and keep temporal/audio QA pending. Do not infer
smoothness from `technical_passed` or a few sampled frames. Deliver a report of applied work, evidence
and unresolved defects; a blocked treatment is not a finished effect.

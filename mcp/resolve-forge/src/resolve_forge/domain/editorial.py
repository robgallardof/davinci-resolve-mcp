"""Genre-aware production briefs. Decisions require meaningful, supplied story moments."""

from __future__ import annotations

import math

from .formats import get as get_format


RECIPES = {
    "education": dict(text="studio", motion="tiktok_smooth", principle="Show the idea as it is explained; cut on completed thoughts, keep breaths and proof shots.",
                      avoid="Do not remove pauses needed to understand a demonstration.", moments=["hook", "idea", "proof", "payoff"]),
    "comedy": dict(text="creator", motion="emphasis", principle="Protect setup, anticipation, punchline and reaction. Hold the payoff long enough to register; cut to a reaction only when it improves the joke.",
                   avoid="Do not reveal the punchline in an early title or remove the deliberate comic pause. No automatic SFX on every joke.", moments=["setup", "anticipation", "punchline", "reaction", "callback"]),
    "music": dict(text="editorial", motion="warm_push", principle="Keep the master song intact; build visual motifs and match selected cuts to musical phrases or gestures, rather than every beat.",
                  avoid="Do not transcribe singing with speech Whisper and claim accurate lyrics; use provided lyric timestamps. Do not time-stretch the master without direction.", moments=["intro", "verse", "chorus", "bridge", "outro"]),
    "electronic": dict(text="impact", motion="tiktok_punch", principle="Contrast build, release and breakdown. Use subdivisions sparingly, more motion at confirmed drops, and breathe in atmospheric sections.",
                       avoid="No rapid full-screen flashing. Beat grids are estimates; a loud transient is not proof of a drop.", moments=["intro", "build", "drop", "breakdown", "outro"]),
    "interview": dict(text="studio", motion="youtube_dynamic", principle="Respect the speaker, eyelines and reactions. Cover necessary edits with relevant B-roll, let emotional answers hold.",
                      avoid="Do not change the meaning by removing qualifications or manufacture a reaction.", moments=["hook", "question", "answer", "reaction", "conclusion"]),
    "cinematic": dict(text="editorial", motion="warm_push", principle="Follow story, screen direction and motivated transitions; use silence, texture and sustained shots when appropriate.",
                      avoid="Do not add a visual change merely because a timer expired.", moments=["opening", "development", "turn", "climax", "resolution"]),
    "product": dict(text="studio", motion="tiktok_smooth", principle="Lead with the benefit, show a real demonstration, retain readable proof and a clear ending.",
                    avoid="Do not add unverified claims or cram multiple calls to action into one frame.", moments=["hook", "problem", "demo", "proof", "cta"]),
    "gaming": dict(text="creator", motion="emphasis", principle="Preserve spatial context and the action that explains the outcome; emphasize the player's reaction and readable HUD.",
                   avoid="Do not crop essential game UI or cover the decisive action with captions.", moments=["setup", "action", "payoff", "reaction"]),
    "vlog": dict(text="creator", motion="vlog_mix", principle="Establish place, alternate detail and presence, use useful J/L cuts and let authentic moments breathe.",
                 avoid="Do not replace lived moments with repetitive zooms or stock B-roll unrelated to the story.", moments=["hook", "context", "journey", "turn", "payoff"]),
}


def plan(brief: str, content_type: str, platform: str, duration_s: float, moments: list[dict] | None = None):
    if not brief.strip():
        raise ValueError("brief must describe the idea, audience or emotional intention")
    if content_type not in RECIPES:
        raise ValueError(f"content_type must be one of {', '.join(RECIPES)}")
    if isinstance(duration_s, bool) or not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("duration_s must be positive and finite")
    fmt = get_format(platform)
    recipe = RECIPES[content_type]
    evidence = []
    for moment in moments or []:
        if not isinstance(moment, dict) or not isinstance(moment.get("reason"), str) or not moment["reason"].strip():
            raise ValueError("Each moment requires a human/agent editorial reason, kind and time_s")
        time_s, kind = moment.get("time_s"), moment.get("kind")
        if isinstance(time_s, bool) or not isinstance(time_s, (int, float)) or not math.isfinite(time_s) or not 0 <= time_s < duration_s:
            raise ValueError("moment time_s must lie inside the timeline duration")
        if kind not in recipe["moments"]:
            raise ValueError(f"moment kind for {content_type} must be one of {', '.join(recipe['moments'])}")
        evidence.append(dict(time_s=time_s, kind=kind, reason=moment["reason"], decision="Review at this story moment; no cut is applied automatically."))
    evidence.sort(key=lambda m: m["time_s"])
    text_style = "creator" if content_type == "education" and fmt.orientation == "vertical" else recipe["text"]
    motion = "youtube_dynamic" if content_type == "education" and fmt.orientation == "horizontal" else recipe["motion"]
    return {"brief": brief, "content_type": content_type, "format": fmt.as_dict(), "duration_s": duration_s,
            "direction": recipe["principle"], "avoid": recipe["avoid"], "caption_style": text_style,
            "motion_style": motion, "confirmed_story_moments": evidence,
            "warnings": ["Requested duration exceeds the configured platform limit."] if fmt.max_seconds and duration_s > fmt.max_seconds else [],
            "needs_review": ["Watch/listen to the source and identify real story moments." if not evidence else "Check each supplied moment against the actual source.",
                             "Review full pacing, continuity, transcript accuracy, faces/HUD and text collisions.",
                             "Verify render pixels, stereo mix, source resolution and platform delivery settings."],
            "tools": (["analyse_music", "plan_beat_cuts", "assemble_montage", "create_music_visualizer"] if content_type in ("music", "electronic")
                      else ["find_story_moments", "transcribe_timeline", "assemble_timeline"])
                     + ["list_text_styles", "preview_text_style", "add_captions", "timeline_markers", "audit_timeline", "render_for"],
            "automation_boundary": "A production brief, not semantic recognition or an automatically approved edit. Agent supplies observations and exercises editorial judgment."}

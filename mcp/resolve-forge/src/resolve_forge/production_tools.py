"""Thin MCP surface for genre-aware direction, music assets and reviewed multi-source cuts."""

from .domain.editorial import plan
from .services import energize_service, review_service, montage_service, music_bed_service, music_service, sfx_service, story_service, transcript_service


def register(mcp, session, safe):
    @mcp.tool()
    @safe
    def plan_edit(brief: str, content_type: str, platform: str, duration_s: float, moments: list[dict] | None = None) -> dict:
        """Produce a genre-aware editorial brief without modifying a project.

        content_type: education/comedy/music/electronic/interview/cinematic/product/gaming/vlog.
        moments: observed {time_s,kind,reason} in timeline seconds. Humor and musical sections require listening/viewing.
        Returns direction, style, safeguards and review steps; never invents a punchline, drop or automatically applied cut.
        """
        return plan(brief, content_type, platform, duration_s, moments)

    @mcp.tool()
    @safe
    def analyse_music(source: str) -> dict:
        """Local spectral onsets, estimated BPM/beat grid and energy section candidates in SOURCE seconds.

        File paths work without Resolve. Uses the speech extra for decoding. Reports confidence and half/double-time risks.
        No downbeat/genre/drop recognition; listen and confirm sections before using any cuts.
        """
        return music_service.analyse(session, source)

    @mcp.tool()
    @safe
    def assemble_montage(shots: list[dict], name: str, format: str | None = None, music_source: str | None = None,
                         music_start_s: float = 0.0, dry_run: bool = True) -> dict:
        """Create a NEW timeline from reviewed multi-source shots, with optional uninterrupted master music on A1.

        shots: {source,start_s,end_s}, in desired order, all times in SOURCE seconds. Preview by default.
        If music_source is supplied, shot audio is excluded. No looping, automatic beat cuts or retiming of the master.
        Mixed aspect ratios require make_platform_version afterward. Does not alter existing timelines.
        """
        return montage_service.assemble(session, shots, name, format, music_source, music_start_s, dry_run)

    @mcp.tool()
    @safe
    def create_music_visualizer(source: str, title: str = "", artist: str = "", theme: str = "spectrum",
                                width: int = 1080, height: int = 1920, fps: int = 30,
                                start_s: float = 0.0, duration_s: float = 15.0, accent: str = "#B8A4FF") -> dict:
        """Create a new MP4 music asset with audio-reactive spectrum or smooth rings, titles and original soundtrack.

        Ranges in SOURCE seconds. Works offline with a file path. Keeps source stereo; no invented music, flashing or normalization.
        0.1-120 seconds per asset; even dimensions 320-3840. Supports HD/4K and portrait. Returns verified video and poster.
        This creates assets; it does not import or modify any Resolve project.
        """
        return music_service.visualizer(session, source, title, artist, theme, width, height, fps, start_s, duration_s, accent)

    @mcp.tool()
    @safe
    def find_story_moments(source: str, content_type: str, language: str | None = None, limit: int = 40) -> dict:
        """Candidate story beats in one source: comic pauses before short lines, reactions/laughs after lines,
        questions and stressed words, each with evidence and a genre kind (comedy: setup/punchline/reaction...).

        Times in SOURCE seconds. Local transcription + audio energy; nothing is edited.
        Candidates are not recognised humor: watch each one, then pass confirmed ones to plan_edit(moments=...).
        content_type: comedy/interview/education/vlog/gaming/product/cinematic (music: use analyse_music).
        """
        return story_service.find(session, source, content_type, language, limit)

    @mcp.tool()
    @safe
    def plan_beat_cuts(music_source: str, shots: list[dict], duration_s: float, music_start_s: float = 0.0,
                       beats_per_cut: int = 4, intense: list[list[float]] | None = None,
                       intense_beats_per_cut: int | None = None, beats_s: list[float] | None = None) -> dict:
        """Cut reviewed shots on the music's beat grid, ready for assemble_montage. Nothing is edited.

        shots: usable {source,start_s,end_s} ranges in SOURCE seconds, in story order; reused cyclically and trimmed, never stretched.
        beats_per_cut: phrase length (4 = one bar in 4/4). intense: [[start,end]] MUSIC seconds you confirmed by
        listening (e.g. a drop) where cuts go every intense_beats_per_cut beats (default half). beats_s overrides analysis.
        """
        return music_service.beat_cuts(session, music_source, shots, duration_s, music_start_s, beats_per_cut,
                                       intense, intense_beats_per_cut, beats_s)

    @mcp.tool()
    @safe
    def align_text(source: str, text: str, language: str | None = None, timeline_offset_s: float = 0.0,
                   focus_vocals: bool = False) -> dict:
        """Time a KNOWN text (song lyrics, script, names spelled right) against one source's voice.

        The supplied text is what gets captioned; local recognition only provides timing. Returns words in timeline
        seconds (source seconds + timeline_offset_s; e.g. -music_start_s for a montage) and the matched coverage.
        For songs, isolated vocals align best; focus_vocals=true analyses the centre channel in the voice band of a full mix
        (an aid, not stem separation). Feed the result to add_captions(words=...).
        """
        return transcript_service.align_text(session, source, text, language=language, timeline_offset_s=timeline_offset_s,
                                             focus_vocals=focus_vocals)

    @mcp.tool()
    @safe
    def place_sound_effects(cues: list[dict], gain_db: float = -8.0, dry_run: bool = True) -> dict:
        """Motivated sound effects at confirmed moments, on NEW audio tracks of a working copy.

        cues: {time_s (timeline seconds), source (your sound file or media-pool clip), reason, gain_db?}.
        A reason is mandatory: a whoosh on a real section change, a hit on a confirmed punchline/drop - never on every cut.
        Gain is baked into a new WAV (originals untouched); overlapping effects get separate tracks. Preview by default
        with density warnings. Forge ships no sound library; use effects the user is licensed to use.
        """
        return sfx_service.place(session, cues, gain_db, dry_run)

    @mcp.tool()
    @safe
    def add_music_bed(music_source: str, music_start_s: float = 0.0, speech_db: float = -20.0, open_db: float = -10.0,
                      words: list[dict] | None = None, dry_run: bool = True) -> dict:
        """Background music under the voice, on a NEW stereo track of a working copy, covering the whole timeline.

        Ducks to speech_db while someone talks (from the transcript, or corrected words in timeline seconds) and rises
        to open_db between lines, with smooth ramps and fades. The ducking is baked into a new 48 kHz WAV; the original
        music is untouched. music_start_s is in MUSIC seconds; no looping. Preview by default (regions + gain curve).
        """
        return music_bed_service.add(session, music_source, music_start_s, speech_db, open_db, words, dry_run)

    @mcp.tool()
    @safe
    def plan_energized_edit(source: str, ranges: list[list[float]] | None = None, min_shot_s: float = 1.2,
                            max_shot_s: float = 2.8, trim_dead: bool = True, max_zoom: float = 1.6,
                            use_faces: bool = True, hints: list[dict] | None = None, format: str | None = None,
                            drop_dull: bool = True) -> dict:
        """Entertainment pacing plan: short shots (1.2-2.8 s) with alternating framings that follow the action.

        Detects where things move (the pet, the hands, the jump), action peaks, camera moves, faces and dead time.
        Framings: wide (establish/camera move), medium x1.25, close x1.5 (single subject or a face reaction),
        crash (fast punch at a peak). The zoom pivot pulls the subject toward the centre without showing edges.
        ranges: the story parts to keep, SOURCE seconds (default: whole source minus dead time). No Resolve needed.
        hints: after WATCHING, correct the detector: [{start_s, end_s, focus: [x, y]}] to aim at the real subject
        (it follows the biggest motion, often the person, not the pet) and/or framing: wide|medium|close|crash.
        Each shot is self-reviewed: zooms that push the subject to an edge, crop the action, cut a face or exceed
        the source's sharpness (format sets the target resolution) are downgraded and reported in self_review.
        drop_dull: cut shots with no interaction (a person seen from behind, no face, nothing else happening);
        each cut is listed in cut_dull with its reason. Protect a shot with a hint {start_s, end_s, keep: true}.
        """
        return energize_service.plan(session, source, ranges, min_shot_s, max_shot_s, trim_dead, max_zoom, use_faces,
                                     hints, format, drop_dull)

    @mcp.tool()
    @safe
    def review_shots(source: str, shots: list[dict], format: str = "tiktok", texts: list[dict] | None = None) -> dict:
        """BEFORE building: a contact sheet of what every planned shot will really show (its crop), with faces,
        subject and text boxes drawn, plus flagged problems, text positions that avoid faces and a colour/exposure
        assessment with a suggested CDL. texts: [{text, start_s, duration_s, position}] in timeline seconds.
        Open the returned sheet image and judge it; fix flagged shots before energize_timeline. No Resolve needed.
        """
        return review_service.review_shots(session, source, shots, format, texts)

    @mcp.tool()
    @safe
    def review_video(path: str, every_s: float = 1.5) -> dict:
        """AFTER rendering: contact sheet of the delivered file over time, black or frozen stretches and picture
        quality (exposure, contrast, saturation, cast). Open the sheet and fix anything wrong before delivering.
        """
        return review_service.review_video(session, path, every_s)

    @mcp.tool()
    @safe
    def energize_timeline(source: str, name: str, format: str | None = None, shots: list[dict] | None = None,
                          ranges: list[list[float]] | None = None, max_shot_s: float = 2.8, max_zoom: float = 1.6,
                          hints: list[dict] | None = None, dry_run: bool = True) -> dict:
        """Build a NEW timeline from an energized plan: one clip per shot, each with its own zoom and focus.

        shots: from plan_energized_edit (edit them freely); omitted -> planned now from `ranges`.
        Applies focus_hold / crash_zoom / warm_push per shot on the source frame rate. Preview by default.
        Then add captions for real speech, text pops on beats and motivated sound effects.
        """
        return energize_service.apply(session, source, name, format, shots, dry_run,
                                      ranges=ranges, max_shot_s=max_shot_s, max_zoom=max_zoom, hints=hints)

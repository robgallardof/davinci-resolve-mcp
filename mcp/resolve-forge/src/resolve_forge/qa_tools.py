"""Thin pre-render inspection and non-destructive picture/audio preparation tools."""
from .services import preflight_service, grade_preset_service, audio_enhance_service, bridge_recovery_service


def register(mcp, session, safe):
    @mcp.tool()
    @safe
    def repair_bridge_connection(dry_run: bool = True) -> dict:
        """Windows-only recovery of one verified orphaned installed Forge fuscript helper.
        Requires exact executable/launcher, configured loopback listener, dead parent and
        current Resolve. Preview by default; false revalidates identity before stopping
        only that helper. Never stops Resolve or a helper with a living parent.
        Run Workspace > Scripts > resolve_bridge afterward.
        """
        return bridge_recovery_service.repair(dry_run)

    @mcp.tool()
    @safe
    def preflight_render(format: str | None = None) -> dict:
        """Read-only pre-render checks for enabled video/audio coverage, offline files,
        invalid zoom/pan properties and target resolution/duration. format is a platform key.
        technical_passed never certifies framing, animated paths, subtitles, color or loudness:
        inspect review_shots and listen before rendering, then review_video after render.
        """
        return preflight_service.inspect(session, format)

    @mcp.tool()
    @safe
    def apply_grade_preset(preset: str = "natural", intensity: float = .5, track: int = 1,
                           indices: list[int] | None = None, copy_name: str | None = None,
                           dry_run: bool = True) -> dict:
        """Preview natural/warm/crisp/muted creative CDL at intensity 0..1.
        dry_run=false applies to a NEW timeline copy using grade_clips' backend.
        Requires correct input color management; no automatic log/HDR conversion.
        Replaces node-1 CDL on the copy; compare faces/highlights visually before render.
        """
        return grade_preset_service.apply(session, preset, intensity, track, indices, copy_name, dry_run)

    @mcp.tool()
    @safe
    def enhance_audio(source: str, preset: str = "dialogue", output_path: str | None = None,
                      dry_run: bool = True) -> dict:
        """Measure source and preview gentle dialogue/podcast/entertainment highpass,
        compression and limiter. dry_run=false writes a NEW 48 kHz 24-bit WAV and
        measures output LUFS/true peak. Never overwrites or inserts into timeline.
        No denoise, voice isolation or recovery of clipped audio; listen before import.
        """
        return audio_enhance_service.enhance(session, source, preset, output_path, dry_run)

"""Forge-owned MCP endpoints. Validation and native work belong to services/."""
from .services import (analysis_service, audio_service, color_service, fusion_service, ingest_service,
                       native_ai_service, project_service, qc_service, timeline_service)
from .services.native import accepted, invoke
from .services import lut_service, sync_service


def register(mcp, session, safe):
    @mcp.tool()
    @safe
    def prepare_lut(source_path: str, strength: float = 1, output_path: str | None = None, dry_run: bool = True) -> dict:
        """Validate a 3D cube LUT and blend its strength into a new LUT file without overwriting the original."""
        return lut_service.prepare(source_path, strength, output_path, dry_run)

    @mcp.tool()
    @safe
    def sync_audio(sources: list[str], mode: str = "waveform", dry_run: bool = True) -> dict:
        """Synchronise existing camera/audio media by waveform or timecode using observed native capabilities."""
        return sync_service.sync(session, sources, mode, dry_run)

    @mcp.tool()
    @safe
    def project_workflow(action: str = "inspect", project_name: str | None = None, output_path: str | None = None) -> dict:
        """List/inspect/create/load/save projects or save and verify a new .drp backup. Never deletes projects."""
        return project_service.manage(session, action, project_name, output_path)

    @mcp.tool()
    @safe
    def configure_project(settings: dict, dry_run: bool = True) -> dict:
        """Preview or apply project settings with native readback."""
        return project_service.configure(session, settings, dry_run)

    @mcp.tool()
    @safe
    def list_media() -> dict:
        """Read media bins, source properties and metadata without importing anything."""
        return ingest_service.catalogue(session)

    @mcp.tool()
    @safe
    def ingest_media(paths: list[str], bin_name: str = "Imported", dry_run: bool = True) -> dict:
        """Import existing files into a bin, deduplicating by resolved source path; restore the previous bin."""
        return ingest_service.ingest(session, paths, bin_name, dry_run)

    @mcp.tool()
    @safe
    def organise_media(by: str = "extension", dry_run: bool = True) -> dict:
        """Preview or organise media into bins by extension or source directory. Never deletes sources."""
        return ingest_service.organise(session, by, dry_run)

    @mcp.tool()
    @safe
    def media_metadata(source: str, values: dict | None = None, dry_run: bool = True) -> dict:
        """Read or update one unambiguous existing media source's metadata with readback."""
        return ingest_service.metadata(session, source, values, dry_run)

    @mcp.tool()
    @safe
    def timeline_versions(action: str = "list", timeline_name: str | None = None) -> dict:
        """List/create/select/duplicate timelines. Versions never overwrite existing timelines."""
        return timeline_service.versions(session, action, timeline_name)

    @mcp.tool()
    @safe
    def edit_clips(properties: dict | None = None, track: int = 1, indices: list[int] | None = None,
                   enabled: bool | None = None, color: str | None = None, copy_name: str | None = None, dry_run: bool = True) -> dict:
        """Apply validated transform/enabled/color changes to a new timeline copy; verify native readback."""
        return timeline_service.clips(session, properties, track, indices, enabled, color, copy_name, dry_run)

    @mcp.tool()
    @safe
    def timeline_markers(entries: list[dict] | None = None, copy_name: str | None = None, dry_run: bool = True) -> dict:
        """Read markers or add markers at timeline-relative seconds on a new copy. Existing markers are preserved."""
        return timeline_service.markers(session, entries, copy_name, dry_run)

    @mcp.tool()
    @safe
    def configure_track(kind: str = "video", index: int = 1, track_name: str | None = None,
                        enabled: bool | None = None, locked: bool | None = None, add: bool = False,
                        copy_name: str | None = None, dry_run: bool = True) -> dict:
        """Add/name/enable/lock a track on a new timeline copy, with readback. No track deletion."""
        return timeline_service.track(session, kind, index, track_name, enabled, locked, add, copy_name, dry_run)

    @mcp.tool()
    @safe
    def export_interchange(output_path: str, format_name: str = "otio") -> dict:
        """Save the project and export the current timeline as OTIO/FCPXML/AAF/EDL/DRT to a new file."""
        return timeline_service.export(session, output_path, format_name)

    @mcp.tool()
    @safe
    def grade_clips(slope: list[float] | None = None, offset: list[float] | None = None, power: list[float] | None = None,
                    saturation: float = 1, lut_path: str | None = None, node: int = 1, track: int = 1,
                    indices: list[int] | None = None, copy_name: str | None = None, dry_run: bool = True) -> dict:
        """Preview/apply validated CDL or LUT grading on a new timeline copy."""
        return color_service.grade(session, slope, offset, power, saturation, lut_path, node, track, indices, copy_name, dry_run)

    @mcp.tool()
    @safe
    def inspect_grade(track: int = 1, index: int = 1) -> dict:
        """Inspect an existing clip's color node labels and LUTs."""
        return color_service.inspect(session, track, index)

    @mcp.tool()
    @safe
    def gallery_stills(action: str = "list", label: str | None = None, output_dir: str | None = None) -> dict:
        """List gallery albums, capture the playhead frame or export the current album into a new directory."""
        return color_service.gallery(session, action, label, output_dir)

    @mcp.tool()
    @safe
    def apply_fusion_graph(nodes: list[dict], edges: list[list[str]], track: int = 1, index: int = 1,
                           copy_name: str | None = None, dry_run: bool = True) -> dict:
        """Apply a validated acyclic effect graph on a new timeline copy. Nodes: id/type/inputs. Edges: source/destination/input."""
        return fusion_service.graph(session, nodes, edges, track, index, copy_name, dry_run)

    @mcp.tool()
    @safe
    def inspect_fusion(track: int = 1, index: int = 1) -> dict:
        """Read composition tool attributes without changing the clip."""
        return fusion_service.inspect(session, track, index)

    @mcp.tool()
    @safe
    def analyse_audio(source: str, threshold_db: float = -40, minimum_s: float = .5, padding_s: float = .15) -> dict:
        """Find silence and energy onsets; return breath-preserving keep ranges in source seconds for assemble_timeline."""
        return analysis_service.audio(session, source, threshold_db, minimum_s, padding_s)

    @mcp.tool()
    @safe
    def analyse_scenes(source: str, threshold: float = .45, minimum_gap_s: float = .5) -> dict:
        """Detect visual scene boundaries locally and return source ranges; never modifies the timeline."""
        return analysis_service.scenes(session, source, threshold, minimum_gap_s)

    @mcp.tool()
    @safe
    def normalise_audio(source: str, output_path: str | None = None, target_lufs: float = -14,
                        peak_db: float = -1, dry_run: bool = True) -> dict:
        """Measure and optionally normalise audio with ffmpeg's two-pass loudnorm into a new 48kHz/24-bit WAV."""
        return audio_service.normalise(session, source, output_path, target_lufs, peak_db, dry_run)

    @mcp.tool()
    @safe
    def native_ai(action: str, source: str | None = None, copy_name: str | None = None, dry_run: bool = True) -> dict:
        """Use observed native AI capabilities: subtitles/scene_cuts/transcribe_media. Timeline AI works on copies."""
        return native_ai_service.apply(session, action, source, copy_name, dry_run)

    @mcp.tool()
    @safe
    def list_capabilities() -> dict:
        """Report observed method availability on the connected build, with no edition/version guesses."""
        return qc_service.capabilities(session)

    @mcp.tool()
    @safe
    def audit_timeline() -> dict:
        """Read-only QC of gaps, overlaps, empty clips and local source availability."""
        return qc_service.audit(session)

    @mcp.tool()
    @safe
    def open_resolve_page(page: str) -> dict:
        """Open media/cut/edit/fusion/color/fairlight/deliver, validating the page name."""
        if page not in {"media", "cut", "edit", "fusion", "color", "fairlight", "deliver"}:
            raise ValueError("Unknown Resolve page.")
        accepted(session.resolve(), "OpenPage", page)
        return {"page": invoke(session.resolve(), "GetCurrentPage")}

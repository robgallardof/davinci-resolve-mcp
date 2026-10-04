"""Compose separately timed videos/stills into new assets; one uninterrupted explicit audio master."""
import io
import math
import re
import secrets
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw
from ..domain import composition, formats
from ..domain.layouts import crop_for
from .analysis_service import source_path
from .audio_service import ffmpeg_executable
from .render_service import DEFAULT_OUTPUT


def _run(args):
    result = subprocess.run([ffmpeg_executable(), "-hide_banner", "-nostdin", *args], capture_output=True,
                            timeout=600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise ValueError("Composition processing failed: " + result.stderr.decode("utf8", errors="replace")[-1000:])
    return result.stdout


def _probe(path):
    try:
        with Image.open(path) as image:
            if getattr(image, "is_animated", False):
                raise ValueError("Animated images need conversion to video first")
            return {"width": image.width, "height": image.height, "still": True, "audio": False, "duration_s": None}
    except (OSError, Image.UnidentifiedImageError):
        pass
    result = subprocess.run([ffmpeg_executable(), "-hide_banner", "-nostdin", "-i", path], capture_output=True,
                            timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    header = result.stderr.decode("utf8", errors="replace")
    duration = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", header)
    video = next((line for line in header.splitlines() if "Video:" in line), "")
    dimensions = re.search(r"(?:\s|,)(\d{2,5})x(\d{2,5})(?:\s|,|\[)", video)
    if not duration:
        raise ValueError("Source needs a finite media duration: " + path)
    h, m, s = map(float, duration.groups())
    return {"width": int(dimensions[1]) if dimensions else 0, "height": int(dimensions[2]) if dimensions else 0,
            "still": False, "audio": "Audio:" in header, "duration_s": h*3600+m*60+s}


def _prepare(session, segments, audio_master, format):
    fmt = formats.get(format)
    planned = composition.plan(segments, audio_master, fmt.width, fmt.height)
    cache = {}
    def media(source):
        path = source_path(session, source)
        if path not in cache:
            cache[path] = _probe(path)
        return path, cache[path]
    for segment in planned["segments"]:
        for visual in segment["sources"]:
            path, meta = media(visual["source"])
            if not meta["width"] or not meta["height"]:
                raise ValueError("Panel source needs decodable video or a still image")
            if meta["still"] and visual["start_s"] != 0:
                raise ValueError("Still image source start_s must be zero")
            if not meta["still"] and visual["start_s"] + segment["duration_s"] > meta["duration_s"] + .001:
                raise ValueError("Visual range exceeds source duration")
            visual.update(source=path, media=meta)
            if visual["subject"] is not None:
                r = visual["screen"]
                aspect = (r[2]-r[0])*fmt.width/((r[3]-r[1])*fmt.height)
                visual["crop"] = list(crop_for(tuple(visual["subject"]), aspect, meta["width"]/meta["height"]))
                # A subject box is protected by contain; cover could cut a face after fitting.
                visual["fit"] = "contain"
    audio = planned["audio_master"]
    path, meta = media(audio["source"])
    if not meta["audio"]:
        raise ValueError("Explicit audio master has no audio stream")
    if audio["start_s"] + planned["duration_s"] > meta["duration_s"] + .001:
        raise ValueError("Continuous audio master is shorter than the composition")
    audio["source"] = path
    planned.update(format=fmt.key, fps=fmt.fps)
    return planned


def _graph(planned, width, height):
    args, filters, video_labels = [], [], []
    index = 0
    for si, segment in enumerate(planned["segments"]):
        tiles, positions = [], []
        duration = segment["duration_s"]
        for pi, item in enumerate(segment["sources"]):
            if item["media"]["still"]:
                args += ["-loop", "1", "-framerate", str(planned["fps"]), "-t", str(duration)]
            args += ["-i", item["source"]]
            sw, sh = item["media"]["width"], item["media"]["height"]
            crop = item["crop"]
            x, y = int(crop[0]*sw), int(crop[1]*sh)
            cw, ch = int(crop[2]*sw)-x, int(crop[3]*sh)-y
            if cw < 2 or ch < 2:
                raise ValueError("Crop is smaller than two source pixels")
            r = item["screen"]
            # Shared rounded boundaries prevent gaps for 3/5 panel layouts.
            bounds = [round(r[0]*width/2)*2, round(r[1]*height/2)*2, round(r[2]*width/2)*2, round(r[3]*height/2)*2]
            pw, ph = bounds[2]-bounds[0], bounds[3]-bounds[1]
            resize = (f"scale={pw}:{ph}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={pw}:{ph}:(ow-iw)/2:(oh-ih)/2" if item["fit"] == "contain" else
                      f"scale={pw}:{ph}:force_original_aspect_ratio=increase:force_divisible_by=2,crop={pw}:{ph}")
            label = f"p{si}_{pi}"
            filters.append(f"[{index}:v]trim=start={item['start_s']}:duration={duration},setpts=PTS-STARTPTS,fps={planned['fps']},crop={cw}:{ch}:{x}:{y},{resize},setsar=1[{label}]")
            tiles.append(f"[{label}]")
            positions.append(f"{bounds[0]}_{bounds[1]}")
            index += 1
        label = f"seg{si}"
        if len(tiles) == 1:
            filters.append(f"{tiles[0]}null[{label}]")
        else:
            filters.append(''.join(tiles)+f"xstack=inputs={len(tiles)}:layout={'|'.join(positions)}:fill=black[{label}]")
        video_labels.append(f"[{label}]")
    filters.append(''.join(video_labels)+f"concat=n={len(video_labels)}:v=1:a=0[vout]")
    args += ["-i", planned["audio_master"]["source"]]
    filters.append(f"[{index}:a]atrim=start={planned['audio_master']['start_s']}:duration={planned['duration_s']},asetpts=PTS-STARTPTS[aout]")
    return args, ';'.join(filters)


def _preview(planned, directory):
    width = 360 if planned["height"] > planned["width"] else 640
    height = round(width*planned["height"]/planned["width"]/2)*2
    args, graph = _graph(planned, width, height)
    preview = directory / "preview.mp4"
    _run(["-n", *args, "-filter_complex_threads", "1", "-filter_complex", graph, "-map", "[vout]", "-map", "[aout]", "-t", str(planned["duration_s"]), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", str(preview)])
    times = [math.floor((s["start_s"] + max(0, min(s["duration_s"]*f, s["duration_s"]-1/planned["fps"]))) * planned["fps"]) / planned["fps"] for s in planned["segments"] for f in (.05,.5,.95)]
    sheet = Image.new("RGB", (width*3, (height+26)*len(planned["segments"])), "#181818")
    draw = ImageDraw.Draw(sheet)
    for i, time in enumerate(times):
        frame = _run(["-ss", str(time), "-i", str(preview), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"])
        image = Image.open(io.BytesIO(frame))
        x, y = (i%3)*width, (i//3)*(height+26)
        sheet.paste(image, (x,y))
        draw.text((x+4,y+height+4), f"Segment {i//3+1}  {time:.2f}s", fill="white")
    path = directory / "contact-sheet.jpg"
    sheet.save(path, quality=90)
    return {"sheet": str(path), "preview_video": str(preview), "sample_times_s": times,
            "next": "Open the sheet and watch/listen to preview_video. Confirm every crop and continuity before build_composition."}


def plan(session, segments, audio_master, format="tiktok"):
    planned = _prepare(session, segments, audio_master, format)
    directory = DEFAULT_OUTPUT / "compositions" / secrets.token_hex(6)
    directory.mkdir(parents=True, exist_ok=False)
    return {**planned, **_preview(planned, directory), "timeline_modified": False,
            "warnings": ["Manual source timing and subjects; no automatic speaker identity or background removal.",
                         "Mosaics and hero/support are editorial options; preview does not certify visual quality."]}


def build(session, segments, audio_master, name, format="tiktok", into_resolve=False, dry_run=True, reviewed=False):
    planned = _prepare(session, segments, audio_master, format)
    if not name or len(name) > 100 or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name.endswith((" ", ".")):
        raise ValueError("name must be a safe nonempty file basename")
    if dry_run:
        return {"dry_run": True, **planned, "next": "plan_composition produces the visual preview; inspect it then use reviewed=true and dry_run=false."}
    if not reviewed:
        raise ValueError("Inspect plan_composition contact sheet and preview_video, then explicitly set reviewed=true")
    directory = DEFAULT_OUTPUT / "compositions" / secrets.token_hex(6)
    directory.mkdir(parents=True, exist_ok=False)
    output = directory / (name + ".mp4")
    args, graph = _graph(planned, planned["width"], planned["height"])
    _run(["-n", *args, "-filter_complex_threads", "1", "-filter_complex", graph, "-map", "[vout]", "-map", "[aout]", "-t", str(planned["duration_s"]), "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(output)])
    result = {"dry_run": False, "file": str(output), "duration_s": planned["duration_s"], "audio_master": planned["audio_master"],
              "next": "review_video(file) and LOOK before captions, additional effects or delivery"}
    if into_resolve:
        from . import assembly_service
        assembled = assembly_service.assemble(session, str(output), [[0, planned["duration_s"]]], name=name, format=format)
        result["timeline"] = assembled["timeline"]
    return result


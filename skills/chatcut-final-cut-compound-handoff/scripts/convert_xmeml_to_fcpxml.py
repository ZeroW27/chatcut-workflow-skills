#!/usr/bin/env python3
"""Convert only simple 1x hard cuts from ChatCut FCP7/XMEML to FCPXML.

This converter is intentionally conservative: it preserves the source media
reference and turns linked video/audio clip pairs into embedded-audio
asset-clips, which is the natural FCPXML representation for one source movie.
"""

from __future__ import annotations

import argparse
import html
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path


def text(parent: ET.Element, path: str, default: str = "") -> str:
    value = parent.findtext(path)
    return value if value is not None else default


def frame_time(frames: int, fps: int) -> str:
    return f"{frames}/{fps}s"


def file_uri(path: str) -> str:
    # as_uri() requires an absolute path and correctly escapes spaces and
    # non-ASCII characters for Final Cut's media reference.
    return Path(path).expanduser().resolve().as_uri()


def convert(
    input_path: Path,
    output_path: Path,
    source_path: str,
    cuts_only: bool,
) -> dict[str, object]:
    if not cuts_only:
        raise ValueError("This packaged converter requires --cuts-only")
    if output_path.exists():
        raise ValueError(f"Output already exists; refusing to overwrite: {output_path}")
    root = ET.parse(input_path).getroot()
    sequence = root.find(".//sequence")
    if sequence is None:
        raise ValueError("No <sequence> found in the XMEML file")

    fps = int(text(sequence, "rate/timebase", "30"))
    sequence_name = text(sequence, "name", input_path.stem)
    duration_frames = int(text(sequence, "duration", "0"))

    video_items = sequence.findall("./media/video/track/clipitem")
    if not video_items:
        raise ValueError("No video clip items found in the XMEML file")

    source_file = video_items[0].find("file")
    source_name = text(video_items[0], "name", input_path.stem + ".mp4")
    if source_file is not None:
        source_name = text(source_file, "name", source_name)
        source_duration_frames = int(text(source_file, "duration", str(max(int(text(x, "out", "0")) for x in video_items))))
    else:
        source_duration_frames = max(int(text(x, "out", "0")) for x in video_items)

    width = text(sequence, "media/video/format/samplecharacteristics/width", "1920")
    height = text(sequence, "media/video/format/samplecharacteristics/height", "1080")
    format_name = f"FFVideoFormat{height}p{fps}"

    fcpxml = ET.Element("fcpxml", {"version": "1.10"})
    resources = ET.SubElement(fcpxml, "resources")
    ET.SubElement(
        resources,
        "format",
        {
            "id": "r1",
            "name": format_name,
            "frameDuration": frame_time(1, fps),
            "width": width,
            "height": height,
            "colorSpace": "1-1-1 (Rec. 709)",
        },
    )
    ET.SubElement(
        resources,
        "asset",
        {
            "id": "r2",
            "name": source_name,
            "src": file_uri(source_path),
            "start": "0s",
            "duration": frame_time(source_duration_frames, fps),
            "hasVideo": "1",
            "hasAudio": "1",
            "audioSources": "1",
            "audioChannels": "2",
            "format": "r1",
            "videoFrameRate": str(fps),
        },
    )

    library = ET.SubElement(fcpxml, "library")
    event = ET.SubElement(library, "event", {"name": sequence_name})
    project = ET.SubElement(event, "project", {"name": sequence_name})
    sequence_out = ET.SubElement(
        project,
        "sequence",
        {
            "format": "r1",
            "duration": frame_time(duration_frames, fps),
            "tcStart": "0s",
            "tcFormat": "NDF",
            "audioLayout": "stereo",
            "audioRate": "48k",
        },
    )
    spine = ET.SubElement(sequence_out, "spine")

    expected_offset = 0
    gaps = 0
    for item in video_items:
        start = int(text(item, "start", str(expected_offset)))
        end = int(text(item, "end", str(start)))
        source_in = int(text(item, "in", "0"))
        source_out = int(text(item, "out", str(source_in)))
        clip_duration = max(0, end - start)
        if clip_duration <= 0 or source_out - source_in != clip_duration:
            raise ValueError(
                "The standalone cuts-only converter supports only positive-duration 1x clips"
            )
        if start > expected_offset:
            gap = start - expected_offset
            ET.SubElement(
                spine,
                "gap",
                {
                    "offset": frame_time(expected_offset, fps),
                    "duration": frame_time(gap, fps),
                },
            )
            gaps += 1

        ET.SubElement(
            spine,
            "asset-clip",
            {
                "name": source_name,
                "ref": "r2",
                "offset": frame_time(start, fps),
                "duration": frame_time(clip_duration, fps),
                "start": frame_time(source_in, fps),
                "enabled": "1",
            },
        )
        expected_offset = end

    if expected_offset < duration_frames:
        ET.SubElement(
            spine,
            "gap",
            {
                "offset": frame_time(expected_offset, fps),
                "duration": frame_time(duration_frames - expected_offset, fps),
            },
        )
        gaps += 1

    ET.indent(fcpxml, space="    ")
    xml_body = ET.tostring(fcpxml, encoding="unicode")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n' + xml_body + "\n",
        encoding="utf-8",
    )

    return {
        "sequence": sequence_name,
        "fps": fps,
        "durationFrames": duration_frames,
        "videoClipCount": len(video_items),
        "gapCount": gaps,
        "sourceName": source_name,
        "sourcePath": source_path,
        "sourceExists": Path(source_path).expanduser().exists(),
        "transformPolicy": "cuts-only; ChatCut visual motion ignored",
        "output": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument(
        "--cuts-only",
        action="store_true",
        help="Required safety flag: transfer only 1x hard-cut ranges.",
    )
    args = parser.parse_args()
    result = convert(args.input, args.output, args.source, args.cuts_only)
    print(result)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Apply only ChatCut XMEML hard cuts to one existing FCP compound reference.

The Final Cut source may be a plain FCPXML file, an .fcpxmld directory, or a
macOS .textClipping whose public UTF-8 payload is FCPXML. The source is never
modified. The output keeps the original resources/media tree and replaces the
project spine with ref-clips pointing at the same compound media resource.
ChatCut Basic Motion, position, keyframes, and speed changes are never copied.
"""

from __future__ import annotations

import argparse
import copy
import plistlib
import uuid
import xml.etree.ElementTree as ET
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from urllib.parse import unquote, urlparse


def parse_time(value: str | None) -> Fraction:
    if not value:
        return Fraction(0)
    raw = value[:-1] if value.endswith("s") else value
    return Fraction(raw)


def format_time(value: Fraction) -> str:
    value = Fraction(value)
    if value == 0:
        return "0s"
    if value.denominator == 1:
        return f"{value.numerator}s"
    return f"{value.numerator}/{value.denominator}s"


def nearest_integer(value: Fraction) -> int:
    if value < 0:
        raise ValueError(f"Expected non-negative time, got {value}")
    return (value.numerator * 2 + value.denominator) // (2 * value.denominator)


def snap_time(seconds: Fraction, frame_duration: Fraction) -> Fraction:
    return nearest_integer(seconds / frame_duration) * frame_duration


def load_fcpxml(source: Path) -> ET.Element:
    input_path = source / "Info.fcpxml" if source.is_dir() else source
    raw = input_path.read_bytes()
    if raw.startswith(b"bplist"):
        outer = plistlib.loads(raw)
        uti_data = outer.get("UTI-Data", {})
        payload = uti_data.get("public.utf8-plain-text")
        if not isinstance(payload, str):
            raise ValueError("textClipping has no public.utf8-plain-text FCPXML payload")
        raw = payload.encode("utf-8")
    root = ET.fromstring(raw)
    if root.tag != "fcpxml":
        raise ValueError(f"Final Cut source root is <{root.tag}>, expected <fcpxml>")
    return root


def required_text(parent: ET.Element, path: str) -> str:
    value = parent.findtext(path)
    if value is None:
        raise ValueError(f"Missing ChatCut XML value: {path}")
    return value.strip()


def basic_motion_scale(clip: ET.Element) -> Decimal | None:
    for parameter in clip.findall("./filter/effect/parameter"):
        if parameter.findtext("parameterid") == "scale":
            value = parameter.findtext("value")
            return Decimal(value) if value else None
    return None


def basic_motion_center(clip: ET.Element) -> tuple[Decimal, Decimal] | None:
    for parameter in clip.findall("./filter/effect/parameter"):
        if parameter.findtext("parameterid") == "center":
            horiz = parameter.findtext("value/horiz")
            vert = parameter.findtext("value/vert")
            if horiz is not None and vert is not None:
                return Decimal(horiz), Decimal(vert)
    return None


def parse_chatcut(xmeml_path: Path) -> tuple[list[dict[str, object]], int, Decimal | None]:
    root = ET.parse(xmeml_path).getroot()
    sequence = root.find("./project/children/sequence")
    if sequence is None:
        raise ValueError("ChatCut XML has no project/children/sequence")
    rate = int(required_text(sequence, "./rate/timebase"))
    clips = sequence.findall("./media/video/track/clipitem")
    if not clips:
        raise ValueError("ChatCut XML has no video clip items")

    sequence_w = Decimal(required_text(sequence, "./media/video/format/samplecharacteristics/width"))
    sequence_h = Decimal(required_text(sequence, "./media/video/format/samplecharacteristics/height"))
    first_file = clips[0].find("file")
    proxy_w = proxy_h = None
    if first_file is not None:
        width = first_file.findtext("./media/video/samplecharacteristics/width")
        height = first_file.findtext("./media/video/samplecharacteristics/height")
        if width and height:
            proxy_w, proxy_h = Decimal(width), Decimal(height)
    base_scale = (
        min(sequence_w / proxy_w, sequence_h / proxy_h) * Decimal(100)
        if proxy_w and proxy_h
        else None
    )

    result: list[dict[str, object]] = []
    for index, clip in enumerate(clips, 1):
        start = int(required_text(clip, "./start"))
        end = int(required_text(clip, "./end"))
        source_in = int(required_text(clip, "./in"))
        source_out = int(required_text(clip, "./out"))
        if end <= start or source_out <= source_in:
            raise ValueError(f"Invalid ChatCut range at clip {index}")
        if end - start != source_out - source_in:
            raise ValueError(
                f"ChatCut clip {index} changes speed or has mismatched ranges; "
                "this converter only supports 1x A-roll cuts"
            )
        result.append(
            {
                "index": index,
                "timeline_start": start,
                "timeline_end": end,
                "source_in": source_in,
                "source_out": source_out,
                "scale": basic_motion_scale(clip),
                "center": basic_motion_center(clip),
            }
        )
    return result, rate, base_scale


def find_project(root: ET.Element, requested_name: str | None) -> ET.Element:
    projects = root.findall("./project") + root.findall("./library/event/project")
    if requested_name:
        matches = [p for p in projects if p.get("name") == requested_name]
        if len(matches) != 1:
            raise ValueError(f"Expected one project named {requested_name!r}, found {len(matches)}")
        return matches[0]
    if len(projects) != 1:
        raise ValueError(f"Expected exactly one Final Cut project, found {len(projects)}")
    return projects[0]


def media_paths(root: ET.Element) -> list[tuple[str, bool]]:
    paths: list[tuple[str, bool]] = []
    for rep in root.findall("./resources/asset/media-rep"):
        parsed = urlparse(rep.get("src", ""))
        if parsed.scheme == "file":
            path = Path(unquote(parsed.path))
            paths.append((str(path), path.exists()))
    return paths


def build(
    chatcut_path: Path,
    fcpxml_source: Path,
    output_dir: Path,
    requested_project: str | None,
    output_name: str | None,
    cuts_only: bool,
) -> dict[str, object]:
    if not cuts_only:
        raise ValueError("This packaged converter requires --cuts-only")
    if output_dir.exists():
        raise ValueError(f"Output already exists; refusing to overwrite: {output_dir}")

    root = load_fcpxml(fcpxml_source)
    project = find_project(root, requested_project)
    sequence = project.find("./sequence")
    spine = sequence.find("./spine") if sequence is not None else None
    if sequence is None or spine is None:
        raise ValueError("Final Cut project has no sequence/spine")
    original_items = list(spine)
    if len(original_items) != 1 or original_items[0].tag != "ref-clip":
        raise ValueError("Final Cut project spine must contain exactly one compound ref-clip")
    template = original_items[0]
    media_ref = template.get("ref")
    media = root.find(f"./resources/media[@id='{media_ref}']")
    if media is None:
        raise ValueError(f"Project ref-clip does not point to a media resource: {media_ref}")

    format_ref = sequence.get("format")
    fmt = root.find(f"./resources/format[@id='{format_ref}']")
    if fmt is None or not fmt.get("frameDuration"):
        raise ValueError(f"Missing sequence format/frameDuration for {format_ref}")
    frame_duration = parse_time(fmt.get("frameDuration"))
    media_sequence = media.find("./sequence")
    media_duration = parse_time(media_sequence.get("duration")) if media_sequence is not None else Fraction(0)
    original_start = parse_time(template.get("start"))

    chatcut_clips, chatcut_rate, base_scale = parse_chatcut(chatcut_path)
    new_project = copy.deepcopy(project)
    new_project.set("name", output_name or f"{project.get('name', 'Project')}｜ChatCut复合片段粗剪")
    new_project.set("uid", str(uuid.uuid4()).upper())
    new_project.attrib.pop("modDate", None)
    new_sequence = new_project.find("./sequence")
    assert new_sequence is not None
    new_spine = new_sequence.find("./spine")
    assert new_spine is not None
    new_spine.clear()

    timeline_offset = Fraction(0)
    ignored_visual_clips = 0
    centers: set[tuple[str, str]] = set()
    report_rows: list[dict[str, str]] = []
    for row in chatcut_clips:
        timeline_start = snap_time(Fraction(int(row["timeline_start"]), chatcut_rate), frame_duration)
        timeline_end = snap_time(Fraction(int(row["timeline_end"]), chatcut_rate), frame_duration)
        duration = timeline_end - timeline_start
        source_in = original_start + snap_time(
            Fraction(int(row["source_in"]), chatcut_rate), frame_duration
        )
        if duration <= 0:
            raise ValueError(f"ChatCut clip {row['index']} collapses after frame snapping")
        if media_duration and source_in + duration > media_duration:
            raise ValueError(
                f"ChatCut clip {row['index']} exceeds compound duration: "
                f"{format_time(source_in + duration)} > {format_time(media_duration)}"
            )
        clip = ET.SubElement(
            new_spine,
            "ref-clip",
            {
                "ref": str(media_ref),
                "offset": format_time(timeline_offset),
                "name": f"{media.get('name', 'Compound')} [ChatCut {int(row['index']):02d}]",
                "start": format_time(source_in),
                "duration": format_time(duration),
            },
        )
        scale = row["scale"]
        relative_scale = Decimal(1)
        if isinstance(scale, Decimal) and base_scale:
            relative_scale = scale / base_scale
            if abs(relative_scale - Decimal(1)) > Decimal("0.001"):
                ignored_visual_clips += 1
        center = row["center"]
        if isinstance(center, tuple):
            centers.add((str(center[0]), str(center[1])))
        report_rows.append(
            {
                "index": str(row["index"]),
                "timeline_offset": format_time(timeline_offset),
                "source_in": format_time(source_in),
                "duration": format_time(duration),
                "chatcut_relative_scale_ignored": f"{relative_scale:.6f}".rstrip("0").rstrip("."),
            }
        )
        timeline_offset += duration

    new_sequence.set("duration", format_time(timeline_offset))
    parent = root
    if project not in list(root):
        parent = next(e for e in root.findall("./library/event") if project in list(e))
    insert_at = list(parent).index(project)
    parent.remove(project)
    parent.insert(insert_at, new_project)

    output_dir.mkdir(parents=True)
    output_xml = output_dir / "Info.fcpxml"
    ET.indent(root, space="    ")
    output_xml.write_bytes(
        b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n\n'
        + ET.tostring(root, encoding="utf-8")
        + b"\n"
    )

    paths = media_paths(root)
    report = output_dir / "ChatCut-compound-report.txt"
    lines = [
        f"source_project={project.get('name', '')}",
        f"new_project={new_project.get('name', '')}",
        f"compound_ref={media_ref}",
        f"compound_name={media.get('name', '')}",
        f"chatcut_rate={chatcut_rate}",
        f"target_frame_duration={format_time(frame_duration)}",
        f"clips={len(report_rows)}",
        "transform_policy=cuts-only; ChatCut visual motion ignored",
        f"ignored_visual_clips={ignored_visual_clips}",
        f"timeline_duration={format_time(timeline_offset)}",
        f"chatcut_center_values={sorted(centers)}",
        "center_policy=not transferred; values are sub-unit legacy XMEML offsets",
        "",
        "media_path\texists",
        *[f"{path}\t{exists}" for path, exists in paths],
        "",
        "index\ttimeline_offset\tsource_in\tduration\tchatcut_relative_scale_ignored",
        *[
            "\t".join(
                row[key]
                for key in (
                    "index",
                    "timeline_offset",
                    "source_in",
                    "duration",
                    "chatcut_relative_scale_ignored",
                )
            )
            for row in report_rows
        ],
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "output": str(output_xml),
        "report": str(report),
        "clips": len(report_rows),
        "ignored_visual_clips": ignored_visual_clips,
        "duration": format_time(timeline_offset),
        "media_paths": paths,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chatcut", type=Path, required=True)
    parser.add_argument("--fcpxml-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project")
    parser.add_argument("--name")
    parser.add_argument(
        "--cuts-only",
        action="store_true",
        help="Required safety flag: transfer only hard-cut ranges and ignore visual motion.",
    )
    args = parser.parse_args()
    result = build(
        args.chatcut,
        args.fcpxml_source,
        args.output,
        args.project,
        args.name,
        args.cuts_only,
    )
    for key, value in result.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()

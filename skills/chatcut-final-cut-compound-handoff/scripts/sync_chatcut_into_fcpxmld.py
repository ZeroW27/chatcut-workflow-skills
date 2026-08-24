#!/usr/bin/env python3
"""Create a safe, side-by-side FCPXMLD project with ChatCut hard cuts only.

The input FCPXMLD is left untouched.  The script copies the existing project,
splits its inline sync clip at the source ranges from ChatCut's XMEML export,
and keeps the original video, external audio, and adjustment-layer resources.
"""

from __future__ import annotations

import argparse
import copy
import os
import uuid
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path


def parse_fcp_time(value: str | None) -> Fraction:
    if not value:
        return Fraction(0)
    raw = value[:-1] if value.endswith("s") else value
    if "/" in raw:
        numerator, denominator = raw.split("/", 1)
        return Fraction(int(numerator), int(denominator))
    return Fraction(raw)


def format_fcp_time(value: Fraction) -> str:
    value = Fraction(value)
    if value == 0:
        return "0s"
    if value.denominator == 1:
        return f"{value.numerator}s"
    return f"{value.numerator}/{value.denominator}s"


def nearest_integer(value: Fraction) -> int:
    """Nearest integer for non-negative time/frame values."""
    if value < 0:
        raise ValueError(f"Expected non-negative value, got {value}")
    return (value.numerator * 2 + value.denominator) // (2 * value.denominator)


def snap_time(seconds: Fraction, frame_duration: Fraction) -> Fraction:
    """Snap seconds to the frame grid read from the current Final Cut project."""
    frame_number = nearest_integer(seconds / frame_duration)
    return frame_number * frame_duration


def text_of(parent: ET.Element, path: str) -> str:
    child = parent.find(path)
    if child is None or child.text is None:
        raise ValueError(f"Missing XML value: {path}")
    return child.text.strip()


def read_chatcut_segments(
    xmeml_path: Path,
) -> tuple[list[tuple[int, int, int, int]], int]:
    root = ET.parse(xmeml_path).getroot()
    sequence = root.find("./project/children/sequence")
    if sequence is None:
        raise ValueError("ChatCut XML has no sequence")

    rate = int(text_of(sequence, "./rate/timebase"))
    clipitems = sequence.findall("./media/video/track/clipitem")
    if not clipitems:
        raise ValueError("ChatCut XML has no video clip items")

    segments: list[tuple[int, int, int, int]] = []
    for clipitem in clipitems:
        timeline_start = int(text_of(clipitem, "./start"))
        timeline_end = int(text_of(clipitem, "./end"))
        in_frame = int(text_of(clipitem, "./in"))
        out_frame = int(text_of(clipitem, "./out"))
        if out_frame <= in_frame:
            raise ValueError(f"Invalid ChatCut range {in_frame}-{out_frame}")
        if timeline_end <= timeline_start:
            raise ValueError(f"Invalid ChatCut timeline range {timeline_start}-{timeline_end}")
        segments.append((timeline_start, timeline_end, in_frame, out_frame))

    return segments, rate


def find_project(root: ET.Element, name: str | None) -> ET.Element:
    projects = root.findall(".//project")
    if name:
        matches = [project for project in projects if project.get("name") == name]
        if len(matches) != 1:
            raise ValueError(f"Expected one FCP project named {name!r}, found {len(matches)}")
        return matches[0]
    if len(projects) != 1:
        raise ValueError(f"Expected exactly one FCP project, found {len(projects)}")
    return projects[0]


def first_child(parent: ET.Element, tag: str, **attrs: str) -> ET.Element | None:
    for child in parent:
        if child.tag != tag:
            continue
        if all(child.get(key) == value for key, value in attrs.items()):
            return child
    return None


def create_split_project(
    root: ET.Element,
    project_name: str,
    chatcut_segments: list[tuple[int, int, int, int]],
    chatcut_rate: int,
    frame_duration: Fraction,
    output_name: str | None = None,
    as_compound_refs: bool = False,
    flatten_sync: bool = False,
) -> tuple[ET.Element, list[dict[str, str]]]:
    original_project = find_project(root, project_name)
    original_sequence = original_project.find("./sequence")
    if original_sequence is None:
        raise ValueError("The source project has no sequence")
    original_spine = original_sequence.find("./spine")
    if original_spine is None:
        raise ValueError("The source project has no spine")

    original_sync = next(
        (child for child in original_spine if child.tag == "sync-clip"), None
    )
    if original_sync is None:
        raise ValueError("The source project has no sync clip in its spine")

    new_project = copy.deepcopy(original_project)
    if output_name:
        new_project_name = output_name
    elif flatten_sync:
        new_project_name = f"{project_name}｜ChatCut纯硬切"
    else:
        new_project_name = f"{project_name}｜ChatCut纯硬切（保留同步嵌套）"
    new_project.set("name", new_project_name)
    new_project.set("uid", str(uuid.uuid4()).upper())

    new_sequence = new_project.find("./sequence")
    assert new_sequence is not None
    new_spine = new_sequence.find("./spine")
    assert new_spine is not None
    for child in list(new_spine):
        new_spine.remove(child)

    compound_media_id: str | None = None
    if as_compound_refs or flatten_sync:
        resources = root.find("./resources")
        if resources is None:
            raise ValueError("The source FCPXML has no resources element")

        resource_ids = {
            child.get("id")
            for child in resources
            if child.get("id")
        }
        next_resource_number = 1
        while f"r{next_resource_number}" in resource_ids:
            next_resource_number += 1
        compound_media_id = f"r{next_resource_number}"

        # Build one genuine Compound Clip Media resource. In normal mode, its
        # internal spine contains the original synchronized clip exactly once.
        # In flatten mode, unwrap only that outer sync-clip and place its
        # original asset-clip (including anchored audio and adjustments)
        # directly in the compound spine.
        original_name = original_sync.get("name") or project_name
        compound_media_name = f"{original_name}｜原始复合片段"
        compound_media = ET.Element(
            "media",
            {
                "id": compound_media_id,
                "name": compound_media_name,
            },
        )
        sequence_attrs = {"duration": original_sync.get("duration", "0s")}
        if original_sequence.get("format"):
            sequence_attrs["format"] = original_sequence.get("format")
        compound_sequence = ET.SubElement(compound_media, "sequence", sequence_attrs)
        compound_spine = ET.SubElement(compound_sequence, "spine")
        if flatten_sync:
            embedded_asset = next(
                (child for child in original_sync if child.tag == "asset-clip"),
                None,
            )
            if embedded_asset is None:
                raise ValueError("The source sync clip has no asset-clip to unwrap")
            embedded_asset = copy.deepcopy(embedded_asset)
            embedded_asset.set("offset", "0s")
            embedded_asset.set("name", f"{original_name}（复合片段内视频与外部音频）")
            compound_spine.append(embedded_asset)
        else:
            embedded_sync = copy.deepcopy(original_sync)
            embedded_sync.set("offset", "0s")
            embedded_sync.set("name", original_name)
            compound_spine.append(embedded_sync)
        resources.append(compound_media)

        # Add one browser item for the compound clip so every timeline ref can
        # be opened as the same Final Cut Pro compound clip.
        source_event = next(
            (
                candidate
                for candidate in root.findall(".//event")
                if any(
                    child.tag == "project" and child.get("name") == project_name
                    for child in candidate
                )
            ),
            None,
        )
        if source_event is None:
            raise ValueError(f"Could not locate event containing project {project_name}")
        browser_ref = ET.Element(
            "ref-clip",
            {
                "ref": compound_media_id,
                "name": compound_media_name,
                "duration": original_sync.get("duration", "0s"),
            },
        )
        source_event.append(browser_ref)

    report: list[dict[str, str]] = []
    timeline_offset = Fraction(0)
    compound_duration = parse_fcp_time(original_sync.get("duration"))

    for index, (timeline_start_frame, timeline_end_frame, in_frame, out_frame) in enumerate(
        chatcut_segments, start=1
    ):
        timeline_start = snap_time(Fraction(timeline_start_frame, chatcut_rate), frame_duration)
        timeline_end = snap_time(Fraction(timeline_end_frame, chatcut_rate), frame_duration)
        source_in = snap_time(Fraction(in_frame, chatcut_rate), frame_duration)
        duration = timeline_end - timeline_start
        if duration <= 0:
            raise ValueError(f"Segment {index} becomes empty after frame snapping")
        # Use the snapped timeline duration for the new clip. This keeps the
        # resulting 29.97p sequence at the same length as ChatCut's timeline.
        source_out = source_in + duration
        if compound_duration and source_out > compound_duration:
            raise ValueError(
                f"ChatCut segment {index} exceeds compound duration: "
                f"{format_fcp_time(source_out)} > {format_fcp_time(compound_duration)}"
            )

        if as_compound_refs or flatten_sync:
            assert compound_media_id is not None
            cut_name = f"{compound_media_name} [ChatCut {index:02d}]"
            cut = ET.Element(
                "ref-clip",
                {
                    "ref": compound_media_id,
                    "offset": format_fcp_time(timeline_offset),
                    "name": cut_name,
                    "start": format_fcp_time(source_in),
                    "duration": format_fcp_time(duration),
                },
            )
            new_spine.append(cut)
        else:
            split_sync = copy.deepcopy(original_sync)
            split_sync.set("offset", format_fcp_time(timeline_offset))
            split_sync.set("name", f"{original_sync.get('name', project_name)} [ChatCut {index:02d}]")
            # The sync clip's start is the visible window into the original
            # synchronized container. Keep its internal video/audio/effects intact
            # so FCP retains the original audio relationship.
            split_sync.set("start", format_fcp_time(source_in))
            split_sync.set("duration", format_fcp_time(duration))
            new_spine.append(split_sync)
        report.append(
            {
                "index": str(index),
                "source_in": format_fcp_time(source_in),
                "source_out": format_fcp_time(source_out),
                "duration": format_fcp_time(duration),
                "timeline_offset": format_fcp_time(timeline_offset),
            }
        )
        timeline_offset += duration

    new_sequence.set("duration", format_fcp_time(timeline_offset))
    return new_project, report


def write_fcpxml(root: ET.Element, output_xml: Path) -> None:
    ET.indent(root, space="    ")
    body = ET.tostring(root, encoding="utf-8")
    output_xml.write_bytes(
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b"<!DOCTYPE fcpxml>\n\n"
        + body
        + b"\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chatcut", type=Path, required=True)
    parser.add_argument("--fcpxmld", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project")
    parser.add_argument("--name")
    parser.add_argument(
        "--cuts-only",
        action="store_true",
        help="Required safety flag: transfer only hard-cut ranges.",
    )
    parser.add_argument(
        "--as-compound-refs",
        action="store_true",
        help="Create one Compound Clip Media and cut it with ref-clip references.",
    )
    parser.add_argument(
        "--as-flat-compound-refs",
        action="store_true",
        help="Create Compound Clip Media without nesting the original sync-clip.",
    )
    args = parser.parse_args()

    if not args.cuts_only:
        raise SystemExit("This packaged converter requires --cuts-only")

    input_xml = args.fcpxmld / "Info.fcpxml"
    if not input_xml.is_file():
        raise SystemExit(f"Missing FCPXMLD payload: {input_xml}")
    if args.output.exists():
        raise SystemExit(f"Output already exists; refusing to overwrite: {args.output}")

    segments, chatcut_rate = read_chatcut_segments(args.chatcut)
    if args.as_compound_refs and args.as_flat_compound_refs:
        raise SystemExit("Choose only one compound reference mode")
    tree = ET.parse(input_xml)
    root = tree.getroot()
    source_project = find_project(root, args.project)
    project_name = source_project.get("name")
    if not project_name:
        raise ValueError("The source Final Cut project has no name")
    source_sequence = source_project.find("./sequence")
    if source_sequence is None:
        raise ValueError("The source project has no sequence")
    format_ref = source_sequence.get("format")
    fmt = root.find(f"./resources/format[@id='{format_ref}']")
    if fmt is None or not fmt.get("frameDuration"):
        raise ValueError(f"Missing sequence format/frameDuration for {format_ref}")
    frame_duration = parse_fcp_time(fmt.get("frameDuration"))
    new_project, report = create_split_project(
        root,
        project_name,
        segments,
        chatcut_rate,
        frame_duration,
        output_name=args.name,
        as_compound_refs=args.as_compound_refs,
        flatten_sync=args.as_flat_compound_refs or not args.as_compound_refs,
    )
    event = new_project.getparent() if hasattr(new_project, "getparent") else None
    # ElementTree has no getparent(); append to the same event as the source.
    if event is None:
        for candidate in root.findall(".//event"):
            if any(child is new_project for child in candidate):
                event = candidate
                break
    # The project is currently a detached deep copy, so locate the source event.
    source_event = None
    for candidate in root.findall(".//event"):
        if any(child.tag == "project" and child.get("name") == project_name for child in candidate):
            source_event = candidate
            break
    if source_event is None:
        raise ValueError(f"Could not locate event containing project {project_name}")
    source_event.append(new_project)

    args.output.mkdir(parents=True)
    output_xml = args.output / "Info.fcpxml"
    write_fcpxml(root, output_xml)

    timeline_duration = new_project.find("./sequence").get("duration", "0s")

    # A small sidecar report makes the generated XML auditable without opening it.
    report_path = args.output / "ChatCut-sync-report.txt"
    lines = [
        f"source_project={project_name}",
        f"new_project={new_project.get('name')}",
        f"chatcut_rate={chatcut_rate}",
        f"segments={len(report)}",
        f"timeline_duration={timeline_duration}",
        f"target_frame_duration={format_fcp_time(frame_duration)}",
        "transform_policy=cuts-only; ChatCut visual motion ignored",
        f"mode={'compound-ref-clip' if args.as_compound_refs else 'compound-flat-ref-clip'}",
        "",
        "index\ttimeline_offset\tsource_in\tsource_out\tduration",
    ]
    lines.extend(
        f"{row['index']}\t{row['timeline_offset']}\t{row['source_in']}\t{row['source_out']}\t{row['duration']}"
        for row in report
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {output_xml}")
    print(f"Wrote {report_path}")
    print(f"segments={len(report)} timeline_duration={timeline_duration}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate the generated project-level cuts in a ChatCut-to-Final-Cut handoff."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path


def parse_time(value: str | None) -> Fraction:
    if not value:
        return Fraction(0)
    raw = value[:-1] if value.endswith("s") else value
    return Fraction(raw)


def load_root(source: Path) -> ET.Element:
    payload = source / "Info.fcpxml" if source.is_dir() else source
    if not payload.is_file():
        raise ValueError(f"Missing FCPXML payload: {payload}")
    root = ET.parse(payload).getroot()
    if root.tag != "fcpxml":
        raise ValueError(f"Expected <fcpxml>, found <{root.tag}>")
    return root


def choose_project(root: ET.Element, requested: str | None) -> ET.Element:
    projects = root.findall("./project") + root.findall("./library/event/project")
    if requested:
        matches = [project for project in projects if project.get("name") == requested]
        if len(matches) != 1:
            raise ValueError(f"Expected one project named {requested!r}, found {len(matches)}")
        return matches[0]
    if not projects:
        raise ValueError("No Final Cut project found")
    return projects[-1]


def validate(source: Path, project_name: str | None, expect_cuts_only: bool) -> dict[str, object]:
    root = load_root(source)
    project = choose_project(root, project_name)
    sequence = project.find("./sequence")
    spine = sequence.find("./spine") if sequence is not None else None
    if sequence is None or spine is None:
        raise ValueError("Selected project has no sequence/spine")

    format_ref = sequence.get("format")
    fmt = root.find(f"./resources/format[@id='{format_ref}']")
    if fmt is None or not fmt.get("frameDuration"):
        raise ValueError(f"Missing format/frameDuration for {format_ref}")
    frame_duration = parse_time(fmt.get("frameDuration"))
    if frame_duration <= 0:
        raise ValueError("frameDuration must be positive")

    resource_ids = {
        element.get("id")
        for element in root.findall("./resources/*")
        if element.get("id")
    }
    items = list(spine)
    if not items:
        raise ValueError("Selected project spine is empty")

    frame_errors: list[str] = []
    missing_refs: list[str] = []
    ref_values: list[str] = []
    visual_motion: list[str] = []
    expected_offset = Fraction(0)
    for index, item in enumerate(items, 1):
        for attribute in ("offset", "start", "duration"):
            if item.get(attribute) is None:
                continue
            value = parse_time(item.get(attribute))
            if (value / frame_duration).denominator != 1:
                frame_errors.append(f"item {index} {attribute}={item.get(attribute)}")
        offset = parse_time(item.get("offset"))
        duration = parse_time(item.get("duration"))
        if offset != expected_offset:
            frame_errors.append(
                f"item {index} non-contiguous offset={item.get('offset')} expected={expected_offset}"
            )
        expected_offset = offset + duration

        ref = item.get("ref")
        if ref:
            ref_values.append(ref)
            if ref not in resource_ids:
                missing_refs.append(ref)
        if item.find("./adjust-transform") is not None:
            visual_motion.append(f"item {index} adjust-transform")
        if item.find("./timeMap") is not None:
            visual_motion.append(f"item {index} timeMap")

    sequence_duration = parse_time(sequence.get("duration"))
    if sequence_duration != expected_offset:
        frame_errors.append(
            f"sequence duration={sequence.get('duration')} expected={expected_offset}"
        )
    if frame_errors:
        raise ValueError("Frame/timeline validation failed: " + "; ".join(frame_errors))
    if missing_refs:
        raise ValueError(f"Missing resource refs: {sorted(set(missing_refs))}")
    if expect_cuts_only and visual_motion:
        raise ValueError("Cuts-only output contains visual motion: " + "; ".join(visual_motion))

    ref_clip_refs = [item.get("ref") for item in items if item.tag == "ref-clip"]
    if ref_clip_refs:
        unique_refs = {ref for ref in ref_clip_refs if ref}
        if len(ref_clip_refs) != len(items):
            raise ValueError("Compound handoff mixes ref-clip with other spine item types")
        if len(unique_refs) != 1:
            raise ValueError(f"Compound handoff uses multiple media refs: {sorted(unique_refs)}")
        only_ref = next(iter(unique_refs))
        media = root.find(f"./resources/media[@id='{only_ref}']")
        if media is None:
            raise ValueError(f"Compound ref {only_ref} does not point to a media resource")
        media_sequence = media.find("./sequence")
        media_duration = (
            parse_time(media_sequence.get("duration")) if media_sequence is not None else Fraction(0)
        )
        if media_duration:
            out_of_bounds = [
                index
                for index, item in enumerate(items, 1)
                if parse_time(item.get("start")) + parse_time(item.get("duration"))
                > media_duration
            ]
            if out_of_bounds:
                raise ValueError(f"Compound cuts exceed media duration: {out_of_bounds}")

    return {
        "project": project.get("name", ""),
        "frameDuration": fmt.get("frameDuration"),
        "items": len(items),
        "timelineDuration": sequence.get("duration", "0s"),
        "compoundRef": ref_clip_refs[0] if ref_clip_refs else None,
        "cutsOnly": not visual_motion,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--project")
    parser.add_argument("--expect-cuts-only", action="store_true")
    args = parser.parse_args()
    result = validate(args.input, args.project, args.expect_cuts_only)
    for key, value in result.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()

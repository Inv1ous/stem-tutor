"""Find duplicate question images in the Library: read-only, no model calls.

  find_question_duplicates.py                 exact copies (same sha256) from the catalog: instant, no file reads
  find_question_duplicates.py --perceptual    also near-copies (same picture, different bytes) by a 64-bit
                                              difference hash with 4-band bucketing; reads each image once

Nothing is deleted or merged. Output: Work/Preparation/question-library-organize/duplicates.json (+ a short
summary on stdout). A group's `kind` says where the copies live, so the learner can decide which to keep:
  same-course         copies inside one course's Questions folders
  course+sourcepractice  a course image also stored in the shared SourcePractice/Media
  cross-course        the same image under different courses
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tutorlib.asset_library import AssetLibrary  # noqa: E402

IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
OUT = ROOT.parent / "Work/Preparation/question-library-organize/duplicates.json"


def place(path: str) -> tuple[str, str]:
    """(course or 'shared', area) of a Library path."""
    parts = PurePosixPath(path).parts
    if parts[:2] == ("Library", "Courses") and len(parts) > 4:
        return parts[2], parts[4] if parts[3] == "Questions" else parts[3]
    if parts[:2] == ("Library", "SourcePractice"):
        return "shared", "SourcePractice"
    return "other", parts[1] if len(parts) > 1 else ""


def candidate_images(records: dict) -> dict[str, dict]:
    out = {}
    for ident, record in records.items():
        path = record["path"]
        if PurePosixPath(path).suffix.lower() not in IMAGE:
            continue
        course, area = place(path)
        if area in ("Media", "Topicals", "SourceVerified", "SourcePractice") or "/Questions/" in path:
            out[ident] = {"path": path, "sha256": record["sha256"], "course": course, "area": area}
    return out


def exact_groups(images: dict) -> list[dict]:
    by_hash = collections.defaultdict(list)
    for ident, info in images.items():
        by_hash[info["sha256"]].append((ident, info))
    groups = []
    for digest, rows in by_hash.items():
        if len(rows) < 2:
            continue
        courses = {info["course"] for _, info in rows}
        areas = {info["area"] for _, info in rows}
        real_courses = courses - {"shared", "other"}
        if len(real_courses) > 1:
            kind = "cross-course"
        elif "SourcePractice" in areas and real_courses:
            kind = "course+sourcepractice"
        elif "SourcePractice" in areas:
            kind = "sourcepractice-only"
        else:
            kind = "same-course"
        groups.append({"sha256": digest, "kind": kind, "count": len(rows),
                       "copies": [{"id": i, "path": info["path"]} for i, info in sorted(rows)]})
    return sorted(groups, key=lambda g: (-g["count"], g["sha256"]))


def dhash(path: Path) -> int | None:
    from PIL import Image
    try:
        with Image.open(path) as image:
            small = image.convert("L").resize((9, 8))
            pixels = list(small.getdata())
    except (OSError, ValueError):
        return None
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return bits


def perceptual_groups(library: AssetLibrary, images: dict, exact_hashes: set[str], max_distance: int) -> list[dict]:
    """Near-copies among images that are NOT byte-identical: bucket by four 16-bit bands (any pair within 3 bits
    shares a band), then confirm with the full Hamming distance."""
    seen_hash: dict[str, tuple[str, int]] = {}
    for ident, info in sorted(images.items()):
        if info["sha256"] in seen_hash:  # one representative per content; exact copies are already grouped
            continue
        try:
            path = library.resolve("asset:" + ident)
        except (OSError, ValueError):
            continue
        value = dhash(Path(path))
        if value is not None:
            seen_hash[info["sha256"]] = (ident, value)
    items = list(seen_hash.items())
    buckets = collections.defaultdict(list)
    for index, (_, (_, value)) in enumerate(items):
        for band in range(4):
            buckets[(band, (value >> (16 * band)) & 0xFFFF)].append(index)
    pairs = set()
    for members in buckets.values():
        if len(members) < 2 or len(members) > 400:  # a huge bucket is a flat/blank image family, not a duplicate
            continue
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                i, j = members[a], members[b]
                if bin(items[i][1][1] ^ items[j][1][1]).count("1") <= max_distance:
                    pairs.add((i, j))
    parent = list(range(len(items)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, j in pairs:
        parent[find(i)] = find(j)
    groups = collections.defaultdict(list)
    for index in range(len(items)):
        groups[find(index)].append(index)
    out = []
    for members in groups.values():
        if len(members) < 2:
            continue
        copies = []
        for index in members:
            sha, (ident, _) = items[index]
            copies.append({"id": ident, "path": images[ident]["path"], "sha256": sha})
        out.append({"kind": "near-duplicate", "count": len(copies), "copies": sorted(copies, key=lambda c: c["path"])})
    return sorted(out, key=lambda g: -g["count"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", type=Path, default=ROOT.parent / "STEM Tutor")
    ap.add_argument("--perceptual", action="store_true")
    ap.add_argument("--max-distance", type=int, default=3, help="Hamming distance for near-duplicates (default 3 of 64)")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    library = AssetLibrary(args.vault)
    images = candidate_images(library.records())
    groups = exact_groups(images)
    report = {"images": len(images), "exact": groups}
    kinds = collections.Counter(g["kind"] for g in groups)
    surplus = sum(g["count"] - 1 for g in groups)
    print(f"{len(images)} question images; {len(groups)} exact-duplicate groups ({surplus} surplus copies)")
    for kind, n in kinds.most_common():
        extra = sum(g["count"] - 1 for g in groups if g["kind"] == kind)
        print(f"  {kind:<24} {n:>5} groups  {extra:>5} surplus copies")
    if args.perceptual:
        near = perceptual_groups(library, images, {g["sha256"] for g in groups}, args.max_distance)
        report["near"] = near
        print(f"near-duplicates (distance <= {args.max_distance}): {len(near)} groups, "
              f"{sum(g['count'] for g in near)} images")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

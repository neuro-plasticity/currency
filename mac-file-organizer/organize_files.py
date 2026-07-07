#!/usr/bin/env python3
"""
Mac File Organizer
==================

Scans a folder on your Mac and:

  1. DETECTS DUPLICATES  - files with identical content (compared by size,
     then SHA-256 hash) are found no matter what they are called.
  2. NAMES VERSIONS      - files that are copies/versions of each other
     (e.g. "report.pdf", "report copy.pdf", "report (2).pdf") are renamed
     to a clean scheme: "report_v1.pdf", "report_v2.pdf", ... ordered by
     modification date (oldest = v1).
  3. ORGANIZES FOLDERS   - files are moved into category folders
     (Images, Documents, Videos, Music, Archives, Code, Other).
     Exact duplicates go into a "Duplicates" folder instead of being
     deleted, so nothing is ever lost.

SAFE BY DEFAULT: running the script only PRINTS what it would do
(a "dry run"). Add --apply to actually rename/move files.

Usage examples (in Terminal):

    # Preview what would happen in your Downloads folder
    python3 organize_files.py ~/Downloads

    # Actually do it
    python3 organize_files.py ~/Downloads --apply

    # Organize into a different destination folder
    python3 organize_files.py ~/Downloads --dest ~/Sorted --apply

    # Only find duplicates, don't rename or sort into folders
    python3 organize_files.py ~/Downloads --no-rename --no-sort

Requires: macOS (or any Unix) with Python 3. No third-party packages.
"""

import argparse
import hashlib
import os
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# File categories used for the "put them in correct folders" step
# ---------------------------------------------------------------------------
CATEGORIES = {
    "Images":    {".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".tiff",
                  ".tif", ".bmp", ".webp", ".svg", ".raw", ".cr2", ".nef",
                  ".ico", ".psd", ".ai"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".pages",
                  ".xls", ".xlsx", ".numbers", ".csv", ".ppt", ".pptx",
                  ".key", ".md", ".epub", ".mobi"},
    "Videos":    {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm",
                  ".m4v", ".mpg", ".mpeg"},
    "Music":     {".mp3", ".aac", ".wav", ".flac", ".m4a", ".ogg", ".aiff",
                  ".wma", ".mid"},
    "Archives":  {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
                  ".dmg", ".iso", ".pkg"},
    "Code":      {".py", ".js", ".ts", ".html", ".css", ".json", ".xml",
                  ".yml", ".yaml", ".sh", ".swift", ".c", ".cpp", ".h",
                  ".java", ".rb", ".go", ".rs", ".sql"},
}
FALLBACK_CATEGORY = "Other"
DUPLICATES_FOLDER = "Duplicates"

# Patterns macOS/browsers add to copies: "name copy.pdf", "name copy 2.pdf",
# "name (1).pdf", "name - Copy.pdf", "name_2.pdf" etc.
COPY_SUFFIX_RE = re.compile(
    r"""^(?P<base>.+?)
        (?:
            [ _-]*copy(?:[ _-]*\d+)?      # "name copy", "name copy 2"
          | [ _-]*\((?:\d+)\)             # "name (1)"
          | [ _-]+(?:\d{1,3})             # "name 2", "name_2", "name-2"
          | [ _-]*-[ _-]*copy             # "name - Copy"
        )$""",
    re.IGNORECASE | re.VERBOSE,
)


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} B"


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def category_for(path: Path) -> str:
    ext = path.suffix.lower()
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return FALLBACK_CATEGORY


def strip_copy_suffix(stem: str) -> str:
    """Remove trailing copy markers: 'Report copy 2' -> 'Report'."""
    while True:
        m = COPY_SUFFIX_RE.match(stem)
        if not m:
            break
        stem = m.group("base")
    return stem.strip()


def base_name_key(path: Path) -> str:
    """Normalized name used to group versions of the same file.

    'Report copy 2.pdf' and 'report (1).PDF' both map to 'report'.
    """
    return strip_copy_suffix(path.stem).lower()


def collect_files(root: Path, recursive: bool) -> list[Path]:
    """All regular files under root, skipping hidden files and our own
    output folders so re-running the script is safe."""
    skip_dirs = set(CATEGORIES) | {FALLBACK_CATEGORY, DUPLICATES_FOLDER}
    files = []
    if recursive:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if not d.startswith(".") and d not in skip_dirs]
            for name in filenames:
                if not name.startswith("."):
                    files.append(Path(dirpath) / name)
    else:
        for p in root.iterdir():
            if p.is_file() and not p.name.startswith("."):
                files.append(p)
    return files


def find_duplicates(files: list[Path]) -> tuple[list[Path], dict[Path, Path]]:
    """Return (originals, duplicates) where duplicates maps each duplicate
    file to the original it copies. The oldest file of each identical group
    is kept as the original."""
    by_size = defaultdict(list)
    for f in files:
        try:
            by_size[f.stat().st_size].append(f)
        except OSError:
            continue

    originals, duplicates = [], {}
    for size, group in by_size.items():
        if len(group) == 1:
            originals.append(group[0])
            continue
        by_hash = defaultdict(list)
        for f in group:
            try:
                by_hash[sha256_of(f)].append(f)
            except OSError as e:
                print(f"  ! could not read {f}: {e}", file=sys.stderr)
        for same in by_hash.values():
            same.sort(key=lambda p: p.stat().st_mtime)  # oldest first
            originals.append(same[0])
            for dup in same[1:]:
                duplicates[dup] = same[0]
    return originals, duplicates


def unique_target(target: Path) -> Path:
    """If target exists, append -1, -2, ... before the extension."""
    if not target.exists():
        return target
    n = 1
    while True:
        candidate = target.with_name(f"{target.stem}-{n}{target.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def version_names(originals: list[Path]) -> dict[Path, str]:
    """DECIDE what each file should be called (no side effects).

    Files sharing a base name and extension are treated as versions of
    one another and named base_v1, base_v2, ... oldest first. Files with
    no siblings keep their current name.
    """
    groups = defaultdict(list)
    for f in originals:
        groups[(base_name_key(f), f.suffix.lower())].append(f)

    names = {}
    for (base, ext), group in groups.items():
        if len(group) == 1:
            names[group[0]] = group[0].name
            continue
        # oldest = v1; when timestamps tie, the file without a copy
        # suffix in its name ("x.txt" vs "x copy.txt") counts as older
        group.sort(key=lambda p: (p.stat().st_mtime,
                                  p.stem != strip_copy_suffix(p.stem),
                                  p.name))
        # keep the original capitalization of the oldest file's name
        display_base = strip_copy_suffix(group[0].stem)
        for i, f in enumerate(group, start=1):
            names[f] = f"{display_base}_v{i}{f.suffix.lower()}"
    return names


def plan_moves(originals: list[Path], duplicates: dict[Path, Path],
               dest: Path, rename_versions: bool, sort_folders: bool):
    """DECIDE the full (source, target) move list (no side effects)."""
    names = version_names(originals) if rename_versions \
        else {f: f.name for f in originals}

    moves = []
    for f in sorted(originals):
        folder = dest / category_for(f) if sort_folders else f.parent
        target = folder / names[f]
        if target != f:
            moves.append((f, target))

    # duplicates go to the Duplicates folder, never deleted
    for dup, original in sorted(duplicates.items()):
        moves.append((dup, dest / DUPLICATES_FOLDER / dup.name))

    return moves


def execute_moves(moves, root: Path, dest: Path, apply: bool) -> None:
    """DO the moves (all side effects live here). With apply=False this
    only prints the plan, which is what makes the dry run trustworthy:
    preview and real run share exactly the same plan."""
    for src, target in moves:
        rel_src = src.relative_to(root) if src.is_relative_to(root) else src
        try:
            rel_tgt = target.relative_to(dest)
        except ValueError:
            rel_tgt = target
        print(f"  {rel_src}  ->  {rel_tgt}")
        if apply:
            target = unique_target(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(target))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Find duplicate files, rename versions, and sort files "
                    "into category folders. Dry run unless --apply is given.")
    ap.add_argument("folder", help="folder to scan, e.g. ~/Downloads")
    ap.add_argument("--dest", help="destination folder (default: the scanned "
                                   "folder itself)")
    ap.add_argument("--apply", action="store_true",
                    help="actually move/rename files (otherwise just preview)")
    ap.add_argument("--recursive", action="store_true",
                    help="also scan subfolders")
    ap.add_argument("--no-rename", action="store_true",
                    help="skip the version-renaming step")
    ap.add_argument("--no-sort", action="store_true",
                    help="skip sorting files into category folders")
    args = ap.parse_args()

    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        print(f"error: {root} is not a folder", file=sys.stderr)
        return 1
    dest = Path(args.dest).expanduser().resolve() if args.dest else root

    print(f"Scanning {root} {'(recursive)' if args.recursive else ''}...")
    files = collect_files(root, args.recursive)
    total = sum(f.stat().st_size for f in files)
    print(f"Found {len(files)} files ({human_size(total)}).\n")

    print("Checking for duplicates (this hashes file contents)...")
    originals, duplicates = find_duplicates(files)
    if duplicates:
        wasted = sum(f.stat().st_size for f in duplicates)
        print(f"Found {len(duplicates)} duplicate file(s) "
              f"wasting {human_size(wasted)}:")
        for dup, orig in sorted(duplicates.items()):
            print(f"  {dup.name}  ==  {orig.name}")
    else:
        print("No duplicates found.")
    print()

    moves = plan_moves(originals, duplicates, dest,
                       rename_versions=not args.no_rename,
                       sort_folders=not args.no_sort)

    if not moves:
        print("Everything is already organized. Nothing to do.")
        return 0

    print(f"{'APPLYING' if args.apply else 'PREVIEW (dry run)'}: "
          f"{len(moves)} change(s)\n")
    execute_moves(moves, root, dest, apply=args.apply)

    if not args.apply:
        print("\nNothing was changed. Re-run with --apply to make these "
              "changes.")
    else:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

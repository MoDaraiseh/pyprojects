"""
File organizer & duplicate finder — a small desktop-automation tool.

Features
--------
* Sort a messy folder into category sub-folders (Images/, Documents/, ...).
* Optionally nest by year-month taken from the file's modified time.
* Find byte-identical duplicate files (SHA-256) anywhere under a folder.
* Always previews with --dry-run; nothing moves until you drop the flag.

Standard library only. Works the same on Windows, macOS and Linux.

Examples
--------
    python organize.py sort ~/Downloads --dry-run
    python organize.py sort ~/Downloads --by-date
    python organize.py dupes ~/Pictures
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Extension -> category. Everything unknown falls into "Other".
CATEGORIES: dict[str, tuple[str, ...]] = {
    "Images": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic", ".svg"),
    "Documents": (".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt", ".xls",
                  ".xlsx", ".csv", ".ppt", ".pptx", ".epub"),
    "Audio": (".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"),
    "Video": (".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv", ".flv"),
    "Archives": (".zip", ".tar", ".gz", ".bz2", ".7z", ".rar", ".xz"),
    "Code": (".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".rs", ".go",
             ".rb", ".sh", ".html", ".css", ".json", ".yaml", ".yml", ".toml"),
    "Installers": (".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage"),
}

_EXT_TO_CATEGORY = {ext: cat for cat, exts in CATEGORIES.items() for ext in exts}


def category_for(path: Path) -> str:
    return _EXT_TO_CATEGORY.get(path.suffix.lower(), "Other")


def unique_destination(dest: Path) -> Path:
    """Return a path that does not exist yet, adding ' (1)', ' (2)', ... if needed."""
    if not dest.exists():
        return dest
    stem, suffix, parent = dest.stem, dest.suffix, dest.parent
    for n in range(1, 10_000):
        candidate = parent / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find a free name for {dest}")


def iter_files(root: Path, recursive: bool) -> list[Path]:
    walker = root.rglob("*") if recursive else root.glob("*")
    return [p for p in walker if p.is_file()]


def sort_folder(root: Path, *, by_date: bool, dry_run: bool, recursive: bool) -> None:
    if not root.is_dir():
        sys.exit(f"error: {root} is not a directory")

    managed = set(CATEGORIES) | {"Other"}
    planned: list[tuple[Path, Path]] = []

    for file in iter_files(root, recursive):
        # Skip files that already live in one of our category folders.
        if not recursive and file.parent != root:
            continue
        if any(part in managed for part in file.relative_to(root).parts[:-1]):
            continue

        category = category_for(file)
        target_dir = root / category
        if by_date:
            mtime = datetime.fromtimestamp(file.stat().st_mtime)
            target_dir = target_dir / mtime.strftime("%Y-%m")

        dest = unique_destination(target_dir / file.name)
        if dest.resolve() == file.resolve():
            continue
        planned.append((file, dest))

    if not planned:
        print("Nothing to do — folder is already tidy.")
        return

    width = max(len(str(src.relative_to(root))) for src, _ in planned)
    for src, dest in planned:
        rel_src = str(src.relative_to(root))
        rel_dest = str(dest.relative_to(root))
        print(f"  {rel_src:<{width}}  ->  {rel_dest}")
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))

    verb = "Would move" if dry_run else "Moved"
    print(f"\n{verb} {len(planned)} file(s).")
    if dry_run:
        print("Re-run without --dry-run to apply.")


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def find_duplicates(root: Path, *, delete: bool, dry_run: bool) -> None:
    if not root.is_dir():
        sys.exit(f"error: {root} is not a directory")

    # First bucket by size (cheap), then hash only the collisions.
    by_size: dict[int, list[Path]] = defaultdict(list)
    for file in iter_files(root, recursive=True):
        by_size[file.stat().st_size].append(file)

    groups: list[list[Path]] = []
    for size, files in by_size.items():
        if size == 0 or len(files) < 2:
            continue
        by_hash: dict[str, list[Path]] = defaultdict(list)
        for f in files:
            by_hash[sha256(f)].append(f)
        groups.extend(g for g in by_hash.values() if len(g) > 1)

    if not groups:
        print("No duplicate files found.")
        return

    reclaimable = 0
    for i, group in enumerate(sorted(groups, key=lambda g: -g[0].stat().st_size), 1):
        group.sort()
        size = group[0].stat().st_size
        reclaimable += size * (len(group) - 1)
        print(f"\n[{i}] {len(group)} copies, {size / 1024:.1f} KiB each")
        print(f"    keep:   {group[0].relative_to(root)}")
        for extra in group[1:]:
            print(f"    remove: {extra.relative_to(root)}")
            if delete and not dry_run:
                extra.unlink()

    print(f"\nReclaimable space: {reclaimable / 1_048_576:.2f} MiB")
    if delete and dry_run:
        print("Re-run with --delete and without --dry-run to remove the extra copies.")
    elif delete and not dry_run:
        print("Extra copies deleted.")
    else:
        print("Add --delete to remove the extra copies (keeps the first of each group).")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("sort", help="organize a folder into category sub-folders")
    s.add_argument("folder", type=Path)
    s.add_argument("--by-date", action="store_true", help="nest categories by YYYY-MM of modified time")
    s.add_argument("--recursive", action="store_true", help="also descend into sub-folders")
    s.add_argument("--dry-run", action="store_true", help="show the plan without moving anything")

    d = sub.add_parser("dupes", help="find (and optionally delete) duplicate files")
    d.add_argument("folder", type=Path)
    d.add_argument("--delete", action="store_true", help="delete all but the first copy of each group")
    d.add_argument("--dry-run", action="store_true", help="with --delete, only show what would go")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "sort":
        sort_folder(args.folder.expanduser(), by_date=args.by_date,
                    dry_run=args.dry_run, recursive=args.recursive)
    elif args.command == "dupes":
        find_duplicates(args.folder.expanduser(), delete=args.delete, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

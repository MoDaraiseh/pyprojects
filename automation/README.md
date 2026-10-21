# 1 · automation — file organizer & duplicate finder

A desktop-automation CLI. Standard library only, cross-platform.

## `sort` — tidy a folder into category sub-folders

```bash
uv run python automation/organize.py sort ~/Downloads --dry-run
uv run python automation/organize.py sort ~/Downloads
uv run python automation/organize.py sort ~/Downloads --by-date      # nest as Images/2026-09/
uv run python automation/organize.py sort ~/Downloads --recursive
```

Files are bucketed by extension into `Images/`, `Documents/`, `Audio/`,
`Video/`, `Archives/`, `Code/`, `Installers/`, or `Other/`. Name collisions get
` (1)`, ` (2)`, … suffixes, including two same-named files from different
sub-folders in a `--recursive` run, so no file is ever overwritten. Files already
inside a category folder are left alone, so re-running is safe. A file that can't
be moved (permissions, locked) is reported and skipped. **Nothing moves without a
real run**: `--dry-run` prints the plan only.

## `dupes` — find byte-identical files

```bash
uv run python automation/organize.py dupes ~/Pictures
uv run python automation/organize.py dupes ~/Pictures --delete --dry-run
uv run python automation/organize.py dupes ~/Pictures --delete
```

Buckets candidates by size first, then confirms with SHA-256. Groups are listed
with the first copy marked "keep"; `--delete` removes the rest. Symlinks are
ignored (a link only points at its target; deleting the target would lose the
real file), and unreadable files are reported and skipped.

## How it works

- `category_for()` maps a suffix via a flattened `{ext: category}` dict.
- `unique_destination()` guarantees a free target path.
- `find_duplicates()` does the cheap size-bucket pass before hashing, so a folder
  of thousands of differently-sized files barely touches the disk.

# Mac File Organizer

A small, safe command-line tool for macOS that:

1. **Detects duplicate files** — even if they have different names, by
   comparing file contents (SHA-256 hash). Duplicates are moved to a
   `Duplicates` folder — **nothing is ever deleted**.
2. **Names file versions** — files that are copies of each other by name
   (`report.pdf`, `report copy.pdf`, `report (2).pdf`) are renamed to
   `report_v1.pdf`, `report_v2.pdf`, … ordered oldest-to-newest.
3. **Sorts files into folders** — Images, Documents, Videos, Music,
   Archives, Code, and Other.

## Requirements

- macOS with Python 3. Check by opening **Terminal** and running:

  ```sh
  python3 --version
  ```

  If macOS offers to install the developer tools, accept — that installs
  Python 3. No other packages are needed.

## How to use

1. Download `organize_files.py` (or clone this repo).
2. Open **Terminal** (Cmd+Space, type "Terminal").
3. Preview what the tool would do — this changes **nothing**:

   ```sh
   python3 organize_files.py ~/Downloads
   ```

4. Happy with the preview? Run it for real:

   ```sh
   python3 organize_files.py ~/Downloads --apply
   ```

## Options

| Option        | What it does                                              |
|---------------|-----------------------------------------------------------|
| `--apply`     | Actually move/rename files. Without it, only a preview.   |
| `--dest PATH` | Put the organized folders somewhere else, e.g. `~/Sorted` |
| `--recursive` | Also scan subfolders                                      |
| `--no-rename` | Skip the version renaming step                            |
| `--no-sort`   | Keep files where they are; only handle duplicates/versions|
| `--find-similar` | Report images that *look* alike (report only, see below) |
| `--similar-threshold N` | How strict `--find-similar` is (0–64, default 8; lower = stricter) |

## Examples

```sh
# Organize the Desktop, sorting results into ~/Organized
python3 organize_files.py ~/Desktop --dest ~/Organized --apply

# Just find and quarantine duplicates in Documents, touch nothing else
python3 organize_files.py ~/Documents --no-rename --no-sort --apply

# Deep-clean Downloads including subfolders (preview first!)
python3 organize_files.py ~/Downloads --recursive
```

## Finding similar (not identical) images

Exact duplicate detection compares file *contents*, so a photo that was
re-compressed, resized, or lightly edited is **not** an exact duplicate —
its bytes differ even though it looks the same. For those cases:

```sh
python3 organize_files.py ~/Pictures --find-similar
```

This computes a *visual fingerprint* (a "difference hash") for each image
using macOS's built-in `sips` tool: the image is shrunk to a tiny 9×8
grayscale grid and each pixel is compared to its neighbor, giving a 64-bit
signature of the image's light/dark structure. Compression and resizing
barely change that structure, so lookalike images have nearly identical
fingerprints. Example output:

```
Found 2 pair(s) that look alike - review them yourself, nothing is moved:

  IMG_1204.jpg  ~=  IMG_1204 small.jpg   (distance 0/64, identical-looking)
  beach.png     ~=  beach.jpg            (distance 4/64, ~94% similar)
```

Unlike exact-duplicate detection, similarity is a judgment call, so this
mode **only reports** — it never moves or renames anything. Use
`--similar-threshold` to tune it: `0` reports only identical-looking
images, higher values (up to 64) report looser matches.

Supported formats: JPEG, PNG, GIF, TIFF, BMP, HEIC/HEIF, WebP.

## Safety notes

- **Dry run by default** — you always see the plan before anything moves.
- **No deletions** — exact duplicates go to a `Duplicates` folder you can
  review and empty yourself.
- **No overwrites** — if a name collision occurs, the tool appends `-1`,
  `-2`, … instead of replacing files.
- Re-running the tool is safe: it skips the folders it created.
- Hidden files (names starting with `.`) are left untouched.

> The first time you run it on protected folders like Desktop or
> Documents, macOS may ask you to give Terminal access to that folder —
> click **OK**.

#!/bin/bash
#
# Organize Files.command  -  the "button" for organize_files.py
# --------------------------------------------------------------
# Double-click this file in Finder. macOS opens a Terminal window and
# native dialogs walk you through the options; no typing needed.
#
# First time only: macOS's Gatekeeper may block a downloaded script.
# Right-click (or Ctrl-click) this file and choose "Open" instead of
# double-clicking, then confirm.
#
# Keep this file in the same folder as organize_files.py.

set -u
cd "$(dirname "$0")"
SCRIPT="$PWD/organize_files.py"

if ! command -v osascript >/dev/null 2>&1; then
    echo "This launcher uses macOS dialogs and only works on a Mac."
    echo "On other systems run:  python3 organize_files.py --help"
    exit 1
fi
if [ ! -f "$SCRIPT" ]; then
    osascript -e 'display alert "organize_files.py not found" message "Keep Organize Files.command in the same folder as organize_files.py."' >/dev/null
    exit 1
fi

# --- 1. which folder? ----------------------------------------------------
folder=$(osascript -e 'POSIX path of (choose folder with prompt "Which folder should Mac File Organizer work on?")' 2>/dev/null) || exit 0

# --- 2. what should happen? ----------------------------------------------
mode=$(osascript -e 'choose from list {"Preview - show what would happen, change nothing", "Organize - actually move and rename files", "Find similar images - report lookalike photos"} with title "Mac File Organizer" with prompt "What should I do?" default items {"Preview - show what would happen, change nothing"}')
[ "$mode" = "false" ] && exit 0

# --- 3. extra options ------------------------------------------------------
opts=$(osascript -e 'choose from list {"Include subfolders", "Skip version renaming", "Skip sorting into folders"} with title "Mac File Organizer" with prompt "Extra options - select any (Cmd-click for several) or just click OK:" with multiple selections allowed and empty selection allowed')
[ "$opts" = "false" ] && exit 0

# --- build the command line ------------------------------------------------
args=("$folder")
case "$mode" in
    Organize*)  args+=(--apply) ;;
    Find\ similar*) args+=(--find-similar) ;;
esac
case "$opts" in *"Include subfolders"*)        args+=(--recursive) ;; esac
case "$opts" in *"Skip version renaming"*)     args+=(--no-rename) ;; esac
case "$opts" in *"Skip sorting into folders"*) args+=(--no-sort)   ;; esac

# --- 4. last chance to back out before anything moves ----------------------
if [[ "$mode" == Organize* ]]; then
    osascript -e 'display dialog "Files in the chosen folder will be moved and renamed. Exact duplicates go to a Duplicates folder - nothing is deleted. Continue?" buttons {"Cancel", "Move files"} default button "Cancel" with icon caution' >/dev/null 2>&1 || exit 0
fi

echo "Running: python3 organize_files.py ${args[*]}"
echo "----------------------------------------------------------------"
python3 "$SCRIPT" "${args[@]}"
status=$?
echo "----------------------------------------------------------------"
if [ $status -eq 0 ]; then
    echo "Finished. You can close this window."
else
    echo "Something went wrong (exit code $status). The messages above say why."
fi
read -n 1 -s -r -p "Press any key to close..." || true
echo

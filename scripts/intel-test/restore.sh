#!/bin/bash
# Works from running macOS or Recovery; --volume names the macOS Data volume.
set -euo pipefail
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
KIT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
USB=$(CDPATH= cd -- "$KIT/.." && pwd -P)
. "$KIT/common.sh"
[ "$(uname -s)" = Darwin ] && [ "$(id -u)" = 0 ] || { echo 'Run as root from macOS or Recovery.'; exit 1; }
ROOT=''
case "${1:-}" in
    '') ;;
    --volume)
        [ $# = 2 ] && [ -d "$2/Library" ] || cug_die 'Provide the mounted macOS Data volume.'
        ROOT=$(CDPATH= cd -- "$2" && pwd -P)
        case "$ROOT" in /Volumes/*) ;; *) cug_die 'Recovery target must be a mounted volume under /Volumes.';; esac
        ;;
    *) cug_die 'Usage: restore.sh [--volume "/Volumes/Macintosh HD - Data"]';;
esac
LOCAL="$ROOT/Library/NullMoth/CoreUltraIntelTest"
S="$KIT/.state"
[ -f "$S/workingEFI/OC/config.plist" ] || cug_die 'USB working EFI backup is missing.'
[ "$(cug_sha "$S/workingEFI/OC/config.plist")" = "$(cat "$KIT/original-config.sha256")" ] || cug_die 'Backup checksum mismatch.'
if [ -f "$LOCAL/magic" ]; then
    WORK=$(mktemp -d /private/var/tmp/CoreUltraRestore.XXXXXX)
    trap 'case "$WORK" in /private/var/tmp/CoreUltraRestore.*) rm -rf -- "$WORK";; esac' EXIT
    if [ -z "$ROOT" ]; then diskutil info -plist /System/Volumes/Data > "$WORK/data.plist"
    else diskutil info -plist "$ROOT" > "$WORK/data.plist"; fi
    [ "$(cug_get "$WORK/data.plist" VolumeUUID)" = "$(cat "$LOCAL/data-uuid")" ] || cug_die 'Wrong macOS Data volume.'
    cug_restore_system "$ROOT" "$LOCAL"
fi
cug_atomic_copy "$S/workingEFI/OC/config.plist" "$USB/EFI/OC/config.plist"
printf 'restored\n' > "$S/phase"
sync
echo 'Original USB config, system driver state, and previous Auxiliary Kernel Collection restored.'
echo 'Reboot through the restored USB. Extra AMFIPass files are unreferenced and inactive.'

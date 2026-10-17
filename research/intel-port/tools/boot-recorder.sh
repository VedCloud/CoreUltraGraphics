#!/bin/bash
# Save current-boot evidence directly to the Data volume, independently of logd.
set -u
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
BASE=/Library/NullMoth/CoreUltraBootRecorder
LOGROOT=/Library/Logs/CoreUltraGraphics
[ "$(id -u)" = 0 ] || exit 1
BOOT=$(sysctl -n kern.bootsessionuuid 2>/dev/null || date +%Y%m%d-%H%M%S)
case "$BOOT" in *[!A-Za-z0-9-]*|'') exit 1;; esac
# A forced reboot must not leave a lock that disables the next boot's recorder.
LOCK="$BASE/running-$BOOT"
mkdir "$LOCK" 2>/dev/null || exit 0
cleanup() {
    trap - EXIT TERM INT
    [ -z "${WATCH:-}" ] || kill "$WATCH" 2>/dev/null || true
    [ -z "${CHILD:-}" ] || kill "$CHILD" 2>/dev/null || true
    rmdir "$LOCK" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 0' TERM INT
remaining=$(cat "$BASE/remaining" 2>/dev/null || echo 0)
case "$remaining" in 1|2|3) ;; *) exit 0;; esac
printf '%s\n' "$((remaining - 1))" > "$BASE/remaining"
OUT="$LOGROOT/Boot-$BOOT"
mkdir -p "$OUT"
chmod 700 "$OUT"
# The overall deadline also bounds a command that never returns to user space.
(sleep 360; kill -TERM "$$" 2>/dev/null || true) &
WATCH=$!
snapshot() {
    name=$1; shift
    (ulimit -f 512; "$@") > "$OUT/$name.txt" 2>&1 &
    CHILD=$!
    (sleep 4; kill -TERM "$CHILD" 2>/dev/null || true) &
    timer=$!
    wait "$CHILD" 2>/dev/null || true
    kill "$timer" 2>/dev/null || true
    wait "$timer" 2>/dev/null || true
    CHILD=
}
{
    echo recorder-version=1
    date -u
    sysctl kern.boottime kern.bootargs kern.bootsessionuuid
} > "$OUT/boot.txt" 2>&1
snapshot loaded-kexts kmutil showloaded
for tick in $(jot 24 1); do
    # Read the in-memory kernel buffer first, before any IOKit query can block.
    snapshot "dmesg-$tick" /sbin/dmesg
    snapshot "NMXGPU-$tick" ioreg -r -l -w 0 -c NMXGPU
    date -u > "$OUT/latest-snapshot.txt"
    sleep 5
done
echo completed > "$OUT/recorder-finished.txt"

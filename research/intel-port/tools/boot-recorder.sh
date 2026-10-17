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
    printf 'begin %s\n' "$name" >> "$OUT/progress.txt"
    (
        trap - EXIT TERM INT
        ulimit -f 512
        exec "$@"
    ) > "$OUT/$name.txt" 2>&1 &
    CHILD=$!
    # A signal cannot guarantee that a process blocked inside the kernel exits.
    # Poll liveness; only reap after the process is already gone.
    for second in 0 1 2 3 4; do
        if ! kill -0 "$CHILD" 2>/dev/null; then
            code=0
            wait "$CHILD" 2>/dev/null || code=$?
            printf '%s\n' "$code" > "$OUT/$name-exit.txt"
            printf 'completed %s\n' "$name" >> "$OUT/progress.txt"
            CHILD=
            return 0
        fi
        [ "$second" = 4 ] || sleep 1
    done
    printf 'timeout %s; no wait for blocked process\n' "$name" >> "$OUT/progress.txt"
    kill -TERM "$CHILD" 2>/dev/null || true
    kill -KILL "$CHILD" 2>/dev/null || true
    CHILD=
    return 1
}
{
    echo recorder-version=2
    date -u
    sysctl kern.boottime kern.bootargs kern.bootsessionuuid
} > "$OUT/boot.txt" 2>&1
REGISTRY_OK=1
for tick in $(jot 24 1); do
    # Read the in-memory kernel buffer first, before any IOKit query can block.
    if ! snapshot "dmesg-$tick" /sbin/dmesg; then
        echo 'kernel buffer query did not complete; stopping without spawning repeated blocked readers' > "$OUT/recorder-finished.txt"
        exit 0
    fi
    if [ "$REGISTRY_OK" = 1 ]; then
        snapshot "NMXGPU-$tick" ioreg -r -l -w 0 -c NMXGPU || REGISTRY_OK=0
    fi
    date -u > "$OUT/latest-snapshot.txt"
    sleep 5
done
echo completed > "$OUT/recorder-finished.txt"

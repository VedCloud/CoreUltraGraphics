#!/bin/bash
# Read-only system diagnostics, saved to this USB. Does not activate or remove drivers.
set -u
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
[ "$(uname -s)" = Darwin ] || exit 1
[ "$(id -u)" = 0 ] || { echo 'Run with sudo /bin/bash.'; exit 1; }
USB=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
OUT="$USB/CoreUltra-Reports/Intel-failed-boot-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
printf 'collector-version=5\n' > "$OUT/collector.txt"
date '+local=%Y-%m-%dT%H:%M:%S%z' >> "$OUT/collector.txt"
date -u '+utc=%Y-%m-%dT%H:%M:%SZ' >> "$OUT/collector.txt"
sysctl kern.boottime >> "$OUT/collector.txt"
sw_vers > "$OUT/macos.txt"
sysctl -n kern.bootargs > "$OUT/boot-args.txt"
csrutil status > "$OUT/sip-status.txt" 2>&1
csrutil authenticated-root status > "$OUT/authenticated-root-status.txt" 2>&1
ioreg -p IODeviceTree -r -n chosen -l -w 0 > "$OUT/boot-chosen.txt" 2>&1
kmutil showloaded > "$OUT/loaded-kexts.txt" 2>&1
for cls in NMXGPU NMXAccel CoreUltraGraphicsDriver IOFramebuffer; do
    ioreg -r -l -w 0 -c "$cls" > "$OUT/$cls.txt" 2>&1
done
ioreg -r -n GFX0 -l -w 0 > "$OUT/gfx0.txt" 2>&1
nvram nullmoth-gpu-attaching > "$OUT/attach-guard.txt" 2>&1 || true
# Record the firmware prerequisite even when collecting from the recovery SSD boot.
{
    ls -ld /Library/NullMoth/firmware /Library/NullMoth/firmware/i915
    for name in mtl_dmc.bin mtl_guc_70.bin mtl_huc_gsc.bin mtl_gsc_1.bin; do
        path="/Library/NullMoth/firmware/i915/$name"
        ls -l "$path"
        [ ! -f "$path" ] || shasum -a 256 "$path"
    done
} > "$OUT/intel-firmware-installed.txt" 2>&1

dmesg > "$OUT/dmesg.txt" 2>&1
# These files were written during the earlier boot, before its volatile buffer vanished.
mkdir -p "$OUT/live-boot-recordings"
find /Library/Logs/CoreUltraGraphics -type f -mtime -2 -name '*.txt' 2>/dev/null |
head -120 |
while IFS= read -r file; do
    boot=$(basename "$(dirname "$file")")
    case "$boot" in Boot-*) ;; *) continue;; esac
    head -c 524288 "$file" > "$OUT/live-boot-recordings/$boot-$(basename "$file")"
done
{ ls -l /Library/KernelCollections/AuxiliaryKernelExtensions.kc;
  shasum -a 256 /Library/KernelCollections/AuxiliaryKernelExtensions.kc;
} > "$OUT/current-auxiliary-collection-hash.txt" 2>&1

cat /Library/NullMoth/CoreUltraIntelTest/phase > "$OUT/transaction-phase.txt" 2>&1
bounded() {
    local name=$1; shift
    (ulimit -f 16384; "$@") > "$OUT/$name.txt" 2> "$OUT/$name.stderr.txt" &
    PID_LOG=$!
    (sleep 60; kill -TERM "$PID_LOG" 2>/dev/null || true) &
    PID_WATCH=$!
    trap 'kill "$PID_LOG" "$PID_WATCH" 2>/dev/null || true; exit 130' INT TERM HUP
    STATUS=0
    wait "$PID_LOG" || STATUS=$?
    kill "$PID_WATCH" 2>/dev/null || true
    wait "$PID_WATCH" 2>/dev/null || true
    trap - INT TERM HUP
    printf '%s\n' "$STATUS" > "$OUT/$name-exit.txt"
}
bounded auxiliary-collection kmutil inspect -a x86_64 -A /Library/KernelCollections/AuxiliaryKernelExtensions.kc
for kext in NMXGPU NMXAccel; do
    info="/Library/Extensions/$kext.kext/Contents/Info.plist"
    { ls -ld "/Library/Extensions/$kext.kext"; plutil -p "$info";
      shasum -a 256 "$info" "/Library/Extensions/$kext.kext/Contents/MacOS/$kext";
    } > "$OUT/$kext-installed.txt" 2>&1
done
echo 'Collecting recent graphics messages (last 30 minutes; time and size limits per query)...'
bounded persisted-graphics-log /usr/bin/log show --last 30m --style compact --info --debug \
  --predicate '(process == "kernel") AND (eventMessage CONTAINS[c] "NullMoth" OR eventMessage CONTAINS[c] "NMX" OR eventMessage CONTAINS[c] "i915" OR eventMessage CONTAINS[c] "[drm]" OR eventMessage CONTAINS[c] "GuC firmware" OR eventMessage CONTAINS[c] "HuC firmware" OR eventMessage CONTAINS[c] "GSC firmware" OR eventMessage CONTAINS[c] "framebuffer")'
bounded windowserver-log /usr/bin/log show --last 30m --style compact --info --debug \
  --predicate '(process == "WindowServer") AND (eventMessage CONTAINS[c] "assert" OR eventMessage CONTAINS[c] "framebuffer" OR eventMessage CONTAINS[c] "accelerator" OR eventMessage CONTAINS[c] "NVMTL" OR eventMessage CONTAINS[c] "failed" OR eventMessage CONTAINS[c] "abort")'
bounded driver-loading-log /usr/bin/log show --last 30m --style compact --info --debug \
  --predicate '(process == "kernel" OR process == "kernelmanagerd" OR process == "kernelmanager_helper" OR process == "syspolicyd" OR process == "amfid") AND (eventMessage CONTAINS[c] "NMXGPU" OR eventMessage CONTAINS[c] "NMXAccel" OR eventMessage CONTAINS[c] "NVMTL" OR eventMessage CONTAINS[c] "AMFIPass")'
mkdir -p "$OUT/diagnostic-reports"
find /Library/Logs/DiagnosticReports -type f -mtime -2 \
  \( -name '*.panic' -o -name '*panic*.ips' -o -name 'WindowServer*.ips' -o -name 'Kernel*.ips' \) 2>/dev/null |
while IFS= read -r file; do
    count=${count:-0}; count=$((count + 1)); [ "$count" -le 12 ] || break
    size=$(stat -f '%z' "$file")
    [ "$size" -gt 8388608 ] || cp "$file" "$OUT/diagnostic-reports/$(basename "$file")"
done
(cd "$OUT" && find . -type f ! -name '._*' ! -name SHA256SUMS.txt -exec shasum -a 256 {} \;) > "$OUT/SHA256SUMS.txt"
COPYFILE_DISABLE=1 tar --exclude='._*' -czf "$OUT.tar.gz" -C "$(dirname "$OUT")" "$(basename "$OUT")"
echo "Saved: $OUT.tar.gz"
echo 'Return this USB for analysis. Collection did not change driver activation or configuration.'

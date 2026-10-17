#!/bin/bash
# Intel 8086:7D45 experiment. Invoke again after each requested USB boot.
set -euo pipefail
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
KIT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
USB=$(CDPATH= cd -- "$KIT/.." && pwd -P)
. "$KIT/common.sh"
[ "$(uname -s)" = Darwin ] || { echo 'Run this from macOS on the Latitude 5350.'; exit 1; }
[ "$(id -u)" = 0 ] || { echo 'Run with sudo /bin/bash.'; exit 1; }
[ "$(uname -m)" = x86_64 ] && [ "$(sw_vers -buildVersion)" = 24H32 ] || {
    echo 'This test kit is pinned to x86_64 macOS 15.8.1 build 24H32.'; exit 1;
}
case "${1:-}" in ''|--check) ;; *) echo 'Usage: install.sh [--check]'; exit 1;; esac
mkdir /var/run/CoreUltraIntelTest.lock 2>/dev/null || { echo 'Another test operation is active.'; exit 1; }
WORK=$(mktemp -d /private/var/tmp/CoreUltraIntelTest.XXXXXX)
COMMITTING=0
VERIFY_PID=''
WATCH_PID=''
LOCAL=/Library/NullMoth/CoreUltraIntelTest
S="$KIT/.state"
CFG="$USB/EFI/OC/config.plist"
cleanup() {
    local result=$?
    trap - EXIT
    [ -z "$WATCH_PID" ] || kill "$WATCH_PID" 2>/dev/null || true
    [ -z "$VERIFY_PID" ] || kill -TERM "$VERIFY_PID" 2>/dev/null || true
    if [ "$COMMITTING" = 1 ]; then
        echo 'Installation failed; restoring the recorded system state and USB configuration.'
        if cug_restore_system '' "$LOCAL" && cug_atomic_copy "$S/workingEFI/OC/config.plist" "$CFG"; then
            printf 'restored\n' > "$S/phase"
        else
            echo "Automatic rollback needs attention. Run: sudo /bin/bash \"$KIT/restore.sh\"" >&2
        fi
    fi
    case "$WORK" in /private/var/tmp/CoreUltraIntelTest.*) rm -rf -- "$WORK";; esac
    rmdir /var/run/CoreUltraIntelTest.lock 2>/dev/null || true
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP
diskutil info -plist "$USB" > "$WORK/usb.plist"
[ "$(cug_get "$WORK/usb.plist" Internal)" = false ] || cug_die 'Kit must be on an external USB volume.'
[ -f "$CFG" ] && [ ! -L "$CFG" ] || cug_die 'USB OpenCore config missing or linked.'
USB_UUID=$(cug_get "$WORK/usb.plist" VolumeUUID)
diskutil info -plist /System/Volumes/Data > "$WORK/data.plist"
DATA_UUID=$(cug_get "$WORK/data.plist" VolumeUUID)
[ -n "$USB_UUID" ] && [ -n "$DATA_UUID" ] || cug_die 'Volume identity unavailable.'
DATA_FREE=$(df -Pk /System/Volumes/Data | awk 'NR==2 {print $4}')
USB_FREE=$(df -Pk "$USB" | awk 'NR==2 {print $4}')
[ "$DATA_FREE" -ge 4194304 ] && [ "$USB_FREE" -ge 131072 ] || cug_die 'Need 4 GiB free on macOS Data and 128 MiB on the USB for staging and rollback.'
ioreg -r -n GFX0 -l -w 0 > "$WORK/gfx.txt"
grep -q '"vendor-id" = <86800000>' "$WORK/gfx.txt" && grep -q '"device-id" = <457d0000>' "$WORK/gfx.txt" \
    || cug_die 'Expected Intel 8086:7D45 GPU was not found.'
echo 'Verifying the complete test kit...'
cug_verify_kit "$KIT" || cug_die 'Test kit checksum failed.'
for item in /Library/Extensions /Library/GPUBundles /Library/NullMoth /Library/KernelCollections; do
    [ ! -L "$item" ] || cug_die "System destination is linked: $item"
done
PHASE=new
[ ! -f "$S/phase" ] || PHASE=$(cat "$S/phase")
case "$PHASE" in new|prepared|active|restored) ;; *) cug_die 'Unknown transaction phase.';; esac
if [ "$PHASE" != new ]; then
    [ "$(cat "$S/usb-uuid")" = "$USB_UUID" ] && [ "$(cat "$S/data-uuid")" = "$DATA_UUID" ] \
        || cug_die 'This transaction belongs to different USB/macOS volumes.'
fi
echo 'Plan: Intel NMXGPU/NMXAccel + ANV + Metal plugin; no NVIDIA/NPU kernel driver.'
echo 'Staged security: csr-active-config 0x0A43, upstream AMFI boot arguments, AMFIPass.'
echo 'Activation exposes the GPU to the Intel driver; the prepared EFI controls the firmware framebuffer fallback.'
echo 'This is an unvalidated hardware experiment, not a guarantee of Metal acceleration.'
[ "${1:-}" != --check ] || { echo "Preflight checks passed. Phase: $PHASE. No configuration changed."; exit 0; }
chmod 755 "$KIT/verify-metal" 2>/dev/null || true
cp "$KIT/verify-metal" "$WORK/verify-metal"
chmod 755 "$WORK/verify-metal"
if [ "$PHASE" = new ] || [ "$PHASE" = restored ]; then
    [ "$(cug_sha "$CFG")" = "$(cat "$KIT/original-config.sha256")" ] || cug_die 'USB config changed since kit preparation.'
    cug_require_fresh_targets ''
    [ ! -e "$USB/EFI/OC/Kexts/AMFIPass.kext" ] || cug_die 'AMFIPass already exists; preserve it through a reviewed migration.'
    mkdir -p "$S"
    if [ ! -d "$S/workingEFI" ]; then
        ditto "$USB/EFI" "$S/workingEFI"
        [ "$(cug_sha "$S/workingEFI/OC/config.plist")" = "$(cat "$KIT/original-config.sha256")" ] || cug_die 'EFI backup failed.'
    fi
    (cd "$USB/EFI" && find . -type f -exec shasum -a 256 {} \;) > "$S/workingEFI.sha256"
    (cd "$S/workingEFI" && shasum -a 256 -c "$S/workingEFI.sha256" --quiet) || cug_die 'Full EFI backup did not verify.'
    printf '%s\n' "$USB_UUID" > "$S/usb-uuid"
    printf '%s\n' "$DATA_UUID" > "$S/data-uuid"
    ditto "$KIT/support/AMFIPass.kext" "$USB/EFI/OC/Kexts/AMFIPass.kext"
    if ! cug_atomic_copy "$KIT/configs/prepared.plist" "$CFG"; then
        cug_atomic_copy "$S/workingEFI/OC/config.plist" "$CFG" || true
        cug_die 'Could not publish prepared config.'
    fi
    printf 'prepared\n' > "$S/phase"
    sync
    echo 'Prepared. Reboot through THIS USB (F12), select installed macOS, then run the same command again.'
    echo 'No system driver has been installed yet; the working framebuffer remains active for this boot.'
    exit 0
fi
BOOT_ARGS=$(sysctl -n kern.bootargs)
if [ "$PHASE" = active ]; then
    case " $BOOT_ARGS " in *' cug_intel_test=active '*) ;; *) cug_die 'Boot this USB test configuration before testing Metal.';; esac
    OUT="$USB/CoreUltra-Reports/Metal-Intel-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$OUT"
    ioreg -l -r -c NMXGPU -w 0 > "$OUT/nmxgpu.txt"
    ioreg -l -r -c NMXAccel -w 0 > "$OUT/nmxaccel.txt"
    kmutil showloaded > "$OUT/loaded-kexts.txt" 2>&1
    /bin/bash "$KIT/collect-runtime.sh" "$OUT"
    "$WORK/verify-metal" > "$OUT/metal-execution.txt" 2>&1 &
    VERIFY_PID=$!
    (sleep 120; kill -TERM "$VERIFY_PID" 2>/dev/null || true) &
    WATCH_PID=$!
    VERIFY_RESULT=0
    wait "$VERIFY_PID" || VERIFY_RESULT=$?
    VERIFY_PID=''
    kill "$WATCH_PID" 2>/dev/null || true
    wait "$WATCH_PID" 2>/dev/null || true
    WATCH_PID=''
    [ "$VERIFY_RESULT" = 0 ] || {
        cat "$OUT/metal-execution.txt"; echo "Hardware test did not pass (exit $VERIFY_RESULT). Results: $OUT"; exit 1;
    }
    cat "$OUT/metal-execution.txt"
    echo "Results: $OUT"
    exit 0
fi
case " $BOOT_ARGS " in *' cug_intel_test=prepared '*) ;; *) cug_die 'Reboot this USB once to apply the prepared security configuration.';; esac
"$WORK/verify-metal" --check-csr
[ "$(cug_sha "$CFG")" = "$(cug_sha "$KIT/configs/prepared.plist")" ] || cug_die 'Prepared USB config changed.'
cug_require_fresh_targets ''
[ ! -e "$LOCAL" ] || cug_die 'Previous local transaction exists; run restore before reinstalling.'
# Build the candidate collection privately before changing /Library.
echo 'Building a test Auxiliary Kernel Collection against this macOS installation...'
mkdir -p "$WORK/repo"
for k in /Library/Extensions/*.kext; do [ ! -d "$k" ] || ditto "$k" "$WORK/repo/$(basename "$k")"; done
for k in NMXGPU NMXAccel; do ditto "$KIT/payload/Library/Extensions/$k.kext" "$WORK/repo/$k.kext"; done
chown -R root:wheel "$WORK/repo"
chmod -R go-w "$WORK/repo"
KARG=(--allow-missing-kdk)
[ ! -f /System/Library/Kernels/kernel ] || KARG+=(--kernel /System/Library/Kernels/kernel)
kmutil create -n aux --volume-root / "${KARG[@]}" \
    -B /System/Library/KernelCollections/BootKernelExtensions.kc \
    -S /System/Library/KernelCollections/SystemKernelExtensions.kc \
    --repository "$WORK/repo" -A "$WORK/test.kc" -z > "$S/kmutil-preflight.log" 2>&1 \
    || { tail -40 "$S/kmutil-preflight.log"; cug_die 'Test kernel collection failed; no system driver installed.'; }
[ -s "$WORK/test.kc" ] || cug_die 'Empty test kernel collection.'
kmutil inspect -a x86_64 -A "$WORK/test.kc" > "$S/kmutil-inspect.log"
for k in NMXGPU NMXAccel; do grep -Fq "com.nullmoth.$k" "$S/kmutil-inspect.log" || cug_die "Kernel collection omitted $k."; done
mkdir -p "$LOCAL"
chmod 700 "$LOCAL"
printf 'backing-up\n' > "$LOCAL/phase"
printf '%s\n' "$DATA_UUID" > "$LOCAL/data-uuid"
printf 'CoreUltraIntelTest-v1\n' > "$LOCAL/magic"
KC=/Library/KernelCollections/AuxiliaryKernelExtensions.kc
mkdir -p /Library/KernelCollections
if [ -f "$KC" ]; then
    cp -p "$KC" "$LOCAL/original-aux.kc"
    cug_sha "$LOCAL/original-aux.kc" > "$LOCAL/original-aux.sha256"
else
    touch "$LOCAL/no-original-aux"
fi
ditto "$S/workingEFI" "$LOCAL/workingEFI"
cp "$KIT/original-config.sha256" "$LOCAL/original-config.sha256"
printf 'installing\n' > "$LOCAL/phase"
COMMITTING=1
while IFS= read -r item; do
    mkdir -p "$(dirname "/$item")"
    ditto "$KIT/payload/$item" "/$item"
    chown -R root:wheel "/$item"
    chmod -R go-w,a+rX "/$item"
done < <(cug_targets)
chmod -R 755 /Library/Extensions/NMXGPU.kext /Library/Extensions/NMXAccel.kext
chmod 644 /Library/GPUBundles/nvmtl-allow.txt
sudo -u _windowserver /bin/test -r /Library/GPUBundles/nvmtl-allow.txt
# The preflight collection contains temporary repository paths. Build the
# published collection from permanent installed paths so kernelmanagerd can
# authenticate and locate the bundles after the staging directory is removed.
kmutil create -n aux --volume-root / "${KARG[@]}" \
    -B /System/Library/KernelCollections/BootKernelExtensions.kc \
    -S /System/Library/KernelCollections/SystemKernelExtensions.kc \
    --repository /Library/Extensions -A "$WORK/installed.kc" -z > "$S/kmutil-installed.log" 2>&1
kmutil inspect -a x86_64 -A "$WORK/installed.kc" > "$S/kmutil-installed-inspect.log"
for k in NMXGPU NMXAccel; do
    grep -F "com.nullmoth.$k" "$S/kmutil-installed-inspect.log" | grep -Fq "/Library/Extensions/$k.kext" \
        || cug_die "Installed collection has no permanent path for $k."
done
cug_atomic_copy "$WORK/installed.kc" "$KC"
mkdir -p /Library/GPUBundles/nvmtl/aircache /Library/GPUBundles/nvmtl/spvcache
chown _windowserver:wheel /Library/GPUBundles/nvmtl/aircache /Library/GPUBundles/nvmtl/spvcache
chmod 755 /Library/GPUBundles/nvmtl/aircache /Library/GPUBundles/nvmtl/spvcache
cug_atomic_copy "$KIT/configs/active.plist" "$CFG"
printf 'active\n' > "$LOCAL/phase"
printf 'active\n' > "$S/phase"
COMMITTING=0
sync
echo 'Installed the Intel test stack. Reboot through THIS USB, then run the same command to test GPU execution.'
echo "Rollback: sudo /bin/bash \"$KIT/restore.sh\""

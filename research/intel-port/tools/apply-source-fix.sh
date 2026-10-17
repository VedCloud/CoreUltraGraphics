#!/bin/bash
# Install the inspected Intel-only candidate into the existing USB test transaction.
# Run from the USB root after booting its parked (-nvoff) configuration.
set -euo pipefail
set -f
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
[ "$(uname -s)" = Darwin ] && [ "$(id -u)" = 0 ] || { echo 'Run on the Mac with sudo /bin/bash.'; exit 1; }
[ "$(sw_vers -buildVersion)" = 24H32 ] || { echo 'This candidate is prepared for macOS build 24H32.'; exit 1; }
USB=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
KIT="$USB/CoreUltra-Metal-Test"
PACKAGE="$USB/Intel-Source-Fix"
. "$KIT/common.sh"
cug_verify_kit "$KIT"
[ "$(cat "$KIT/.state/phase")" = active ] || cug_die 'The existing installed test transaction is required.'
ARGS=" $(sysctl -n kern.bootargs) "
case "$ARGS" in *' cug_intel_test=active '*) ;; *) cug_die 'Boot the prepared USB first.';; esac
case "$ARGS" in *' -nvoff '*) ;; *) cug_die 'Use the parked USB boot; the previous graphics driver must stay disabled during installation.';; esac
case "$ARGS" in *' nmxguc=2 '*) ;; *) cug_die 'The parked USB must include nmxguc=2.';; esac
mkdir /var/run/CoreUltraIntelTest.lock 2>/dev/null || cug_die 'Another test operation is active.'
WORK=$(mktemp -d /private/var/tmp/CoreUltraSourceFix.XXXXXX)
PENDING=0
cleanup() {
    result=$?
    trap - EXIT
    if [ "$PENDING" = 1 ]; then
        echo 'Restoring the previous driver, collection and parked USB configuration.' >&2
        cug_atomic_copy "$OUT/previous-NMXGPU" "$LIVE" || result=1
        cug_atomic_copy "$OUT/previous-Info.plist" "$LINFO" || result=1
        chown root:wheel "$LIVE" "$LINFO"; chmod 755 "$LIVE"; chmod 644 "$LINFO"
        cug_atomic_copy "$OUT/previous-aux.kc" "$KC" || result=1
        cug_atomic_copy "$OUT/previous-usb-config.plist" "$CFG" || result=1
    fi
    case "$WORK" in /private/var/tmp/CoreUltraSourceFix.*) rm -rf -- "$WORK";; esac
    rmdir /var/run/CoreUltraIntelTest.lock
    exit "$result"
}
trap cleanup EXIT
cp "$KIT/verify-metal" "$WORK/verify-metal"
chmod 755 "$WORK/verify-metal"
"$WORK/verify-metal" --check-csr
diskutil info -plist /System/Volumes/Data > "$WORK/data.plist"
diskutil info -plist "$USB" > "$WORK/usb.plist"
[ "$(cug_get "$WORK/data.plist" VolumeUUID)" = "$(cat "$KIT/.state/data-uuid")" ] || cug_die 'Wrong macOS Data volume.'
[ "$(cug_get "$WORK/usb.plist" VolumeUUID)" = "$(cat "$KIT/.state/usb-uuid")" ] || cug_die 'Wrong USB volume.'
CANDIDATE="$PACKAGE/NMXGPU.kext/Contents/MacOS/NMXGPU"
CINFO="$PACKAGE/NMXGPU.kext/Contents/Info.plist"
[ "$(cug_sha "$CANDIDATE")" = 3ed1770f0e61945c4501459b44ed49e3cfcacde3e861b78f69a70fa160825df9 ] || cug_die 'Candidate executable checksum failed.'
[ "$(cug_sha "$CINFO")" = 029f40150f9f34ee67d1dee482c59f7cdd1b7d08c606cc12a99e67eee357afdc ] || cug_die 'Candidate metadata checksum failed.'
[ "$(cug_get "$CINFO" IOKitPersonalities:NMXGPUIntel:IOPCIPrimaryMatch)" = 0x7d458086 ] || cug_die 'Wrong candidate match scope.'
CFG="$USB/EFI/OC/config.plist"
[ -f "$CFG" ] && [ ! -L "$CFG" ] || cug_die 'Missing or linked USB configuration.'
[ "$(cug_sha "$CFG")" = "$(cug_sha "$PACKAGE/parked.plist")" ] || cug_die 'USB parked configuration changed.'
[ "$(cug_sha "$PACKAGE/parked.plist")" = fbe4d026822fbd843013c79eee00ba7bb7f9d598750252207fea2e78207149d9 ] || cug_die 'Parked configuration checksum failed.'
[ "$(cug_sha "$PACKAGE/active.plist")" = 361281606a1ab0ddb6fda6bc968e5a818dac66de208a6fdea6328f692e7064c7 ] || cug_die 'Active configuration checksum failed.'
LIVE=/Library/Extensions/NMXGPU.kext/Contents/MacOS/NMXGPU
LINFO=/Library/Extensions/NMXGPU.kext/Contents/Info.plist
KC=/Library/KernelCollections/AuxiliaryKernelExtensions.kc
for path in "$LIVE" "$LINFO" "$KC" /Library/Extensions/NMXGPU.kext; do
    [ -e "$path" ] && [ ! -L "$path" ] || cug_die 'Missing or linked installation target.'
done
old=$(cug_sha "$LIVE")
case "$old" in
    0f9108a814acb480ba1859bf13f1d01ac948039f0e3158bf45ea1850012c181c|9f903b7ed5b007ca12c3e23094137f771070b45f4fbee4aab9d85615f78d31f5|a931d61b2082108f1cb968fc14e0f6a9cfaeaeb961646909db40e3316edfa315)
        [ "$(cug_sha "$LINFO")" = "$(cug_sha "$KIT/payload/Library/Extensions/NMXGPU.kext/Contents/Info.plist")" ] || cug_die 'Unknown previous metadata.';;
    3ed1770f0e61945c4501459b44ed49e3cfcacde3e861b78f69a70fa160825df9)
        [ "$(cug_sha "$LINFO")" = "$(cug_sha "$CINFO")" ] || cug_die 'Source candidate metadata differs.';;
    *) cug_die 'Unknown installed NMXGPU executable.';;
esac
for file in Contents/Info.plist Contents/MacOS/NMXAccel; do
    [ "$(cug_sha "/Library/Extensions/NMXAccel.kext/$file")" = "$(cug_sha "$KIT/payload/Library/Extensions/NMXAccel.kext/$file")" ] || cug_die 'NMXAccel differs from the audited test kit.'
done
OUT="$USB/CoreUltra-Reports/Intel-Source-Fix-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
# FAT32 backup: copy bytes, not APFS flags or extended attributes.
cat "$LIVE" > "$OUT/previous-NMXGPU"
cat "$LINFO" > "$OUT/previous-Info.plist"
cat "$KC" > "$OUT/previous-aux.kc"
cat "$CFG" > "$OUT/previous-usb-config.plist"
for pair in "$LIVE|previous-NMXGPU" "$LINFO|previous-Info.plist" "$KC|previous-aux.kc" "$CFG|previous-usb-config.plist"; do
    [ "$(cug_sha "${pair%%|*}")" = "$(cug_sha "$OUT/${pair#*|}")" ] || cug_die 'Backup checksum failed.'
done
PENDING=1
cug_atomic_copy "$CANDIDATE" "$LIVE"
cug_atomic_copy "$CINFO" "$LINFO"
chown root:wheel "$LIVE" "$LINFO"; chmod 755 "$LIVE"; chmod 644 "$LINFO"
KARG=(--allow-missing-kdk)
[ ! -f /System/Library/Kernels/kernel ] || KARG+=(--kernel /System/Library/Kernels/kernel)
echo 'Building the auxiliary collection from permanent installed paths...'
kmutil create -n aux --volume-root / "${KARG[@]}" \
    -B /System/Library/KernelCollections/BootKernelExtensions.kc \
    -S /System/Library/KernelCollections/SystemKernelExtensions.kc \
    --repository /Library/Extensions -A "$WORK/installed.kc" -z > "$OUT/build.log" 2>&1 \
    || { tail -40 "$OUT/build.log"; cug_die 'Kernel collection build failed.'; }
kmutil inspect -a x86_64 -A "$WORK/installed.kc" > "$OUT/inspect.txt"
for k in NMXGPU NMXAccel; do
    grep -F "com.nullmoth.$k" "$OUT/inspect.txt" | grep -Fq "/Library/Extensions/$k.kext" || cug_die 'Collection does not contain permanent driver paths.'
done
cug_atomic_copy "$WORK/installed.kc" "$KC"
# Clear only this driver's attach marker for this new controlled build.
if nvram nullmoth-gpu-attaching > "$OUT/boot-guard-before.txt" 2>/dev/null; then
    nvram -d nullmoth-gpu-attaching || cug_die 'Could not clear the old attach marker.'
fi
# Activation is last. On any earlier error the USB stays parked.
cug_atomic_copy "$PACKAGE/active.plist" "$CFG"
cug_sha "$LIVE" > "$OUT/installed-NMXGPU.sha256"
cug_sha "$KC" > "$OUT/published-aux.sha256"
cug_sha "$CFG" > "$OUT/active-config.sha256"
sync
PENDING=0
echo "Installed source candidate and permanent-path collection. Report: $OUT"
echo 'Reboot through this USB to test the new driver with nmxguc=2.'
echo 'After reaching the desktop, run test-intel-metal.sh. If the display fails, boot the working SSD and collect the failure report.'
echo 'Metal acceleration remains unverified until the native checker completes and validates GPU output.'

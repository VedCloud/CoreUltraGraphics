#!/bin/bash
# Shared transaction operations; no automatic action when sourced.
cug_die() { printf 'STOP: %s\n' "$*" >&2; return 1; }
cug_sha() {
    if [ -x /usr/bin/shasum ]; then /usr/bin/shasum -a 256 "$1" | /usr/bin/awk '{print $1}'
    elif [ -x /usr/bin/openssl ]; then /usr/bin/openssl dgst -sha256 "$1" | /usr/bin/awk '{print $NF}'
    else cug_die 'No SHA256 utility available.'; fi
}
cug_get() { /usr/libexec/PlistBuddy -c "Print :$2" "$1"; }
cug_verify_kit() { (cd "$1" && /usr/bin/shasum -a 256 -c SHA256SUMS --quiet); }
cug_atomic_copy() {
    local source=$1 destination=$2
    /bin/cp "$source" "$destination.cug-new" || return 1
    [ "$(cug_sha "$source")" = "$(cug_sha "$destination.cug-new")" ] || return 1
    /bin/mv -f "$destination.cug-new" "$destination"
}
cug_targets() {
    printf '%s\n' Library/Extensions/NMXGPU.kext Library/Extensions/NMXAccel.kext \
        Library/GPUBundles/NVMTLDriver.bundle Library/GPUBundles/NVIDIAShared.bundle \
        Library/GPUBundles/nvmtl Library/GPUBundles/nvmtl-allow.txt \
        Library/NullMoth/firmware
}
cug_require_fresh_targets() {
    local root=$1 item
    while IFS= read -r item; do
        [ ! -e "$root/$item" ] && [ ! -L "$root/$item" ] || {
            cug_die "Existing $item requires a migration; this installer only handles a fresh Intel test."; return 1;
        }
    done < <(cug_targets)
}
cug_restore_system() {
    local root=$1 state=$2 item live
    [ "$(/bin/cat "$state/magic")" = CoreUltraIntelTest-v1 ] || return 1
    case "$(/bin/cat "$state/phase")" in
        restored) return 0;;
        backing-up) printf 'restored\n' > "$state/phase"; return 0;;
        installing|active) ;;
        *) return 1;;
    esac
    if [ -f "$state/original-aux.kc" ]; then
        [ "$(cug_sha "$state/original-aux.kc")" = "$(/bin/cat "$state/original-aux.sha256")" ] || return 1
    elif [ ! -f "$state/no-original-aux" ]; then
        return 1
    fi
    # Only fixed, previously absent targets can be removed. Never delete a supplied path.
    while IFS= read -r item; do
        case "$item" in Library/Extensions/NMX*.kext|Library/GPUBundles/NVMTLDriver.bundle|Library/GPUBundles/NVIDIAShared.bundle|Library/GPUBundles/nvmtl|Library/GPUBundles/nvmtl-allow.txt|Library/NullMoth/firmware) ;;
            *) return 1;; esac
        /bin/rm -rf -- "$root/$item" || return 1
    done < <(cug_targets)
    live="$root/Library/KernelCollections/AuxiliaryKernelExtensions.kc"
    if [ -f "$state/original-aux.kc" ]; then
        cug_atomic_copy "$state/original-aux.kc" "$live" || return 1
    elif [ -f "$state/no-original-aux" ]; then
        /bin/rm -f -- "$live" || return 1
    else
        return 1
    fi
    printf 'restored\n' > "$state/phase"
}

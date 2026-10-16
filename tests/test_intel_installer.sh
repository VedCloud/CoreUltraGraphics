#!/bin/bash
# Exercises transaction invariants using real macOS plist/hash/filesystem tools.
set -euo pipefail
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
. "$ROOT/scripts/intel-test/common.sh"
T=$(mktemp -d)
trap 'rm -rf -- "$T"' EXIT
mkdir -p "$T/fresh" "$T/state" "$T/kit"
cug_require_fresh_targets "$T/fresh"
mkdir -p "$T/fresh/Library/Extensions/NMXGPU.kext"
if cug_require_fresh_targets "$T/fresh" 2>/dev/null; then echo 'FAIL: accepted an existing target'; exit 1; fi
printf 'existing-collection\n' > "$T/state/original-aux.kc"
cug_sha "$T/state/original-aux.kc" > "$T/state/original-aux.sha256"
printf 'CoreUltraIntelTest-v1\n' > "$T/state/magic"
printf 'backing-up\n' > "$T/state/phase"
# An interrupted backup must not remove any payload paths or need a complete KC.
mv "$T/state/original-aux.kc" "$T/held-aux.kc"
cug_restore_system "$T/fresh" "$T/state"
[ -d "$T/fresh/Library/Extensions/NMXGPU.kext" ]
mv "$T/held-aux.kc" "$T/state/original-aux.kc"
printf 'installing\n' > "$T/state/phase"
mkdir -p "$T/fresh/Library/KernelCollections" "$T/fresh/Library/Extensions/Unrelated.kext"
printf 'keep\n' > "$T/fresh/Library/Extensions/Unrelated.kext/keep"
cp "$T/state/original-aux.kc" "$T/saved"
printf 'corrupt\n' >> "$T/state/original-aux.kc"
if cug_restore_system "$T/fresh" "$T/state"; then echo 'FAIL: accepted corrupt rollback collection'; exit 1; fi
[ -d "$T/fresh/Library/Extensions/NMXGPU.kext" ]
cp "$T/saved" "$T/state/original-aux.kc"
cug_restore_system "$T/fresh" "$T/state"
[ ! -e "$T/fresh/Library/Extensions/NMXGPU.kext" ]
[ -f "$T/fresh/Library/Extensions/Unrelated.kext/keep" ]
cmp "$T/state/original-aux.kc" "$T/fresh/Library/KernelCollections/AuxiliaryKernelExtensions.kc"
printf 'payload\n' > "$T/kit/file"
(cd "$T/kit" && shasum -a 256 file > SHA256SUMS)
cug_verify_kit "$T/kit"
printf 'changed\n' >> "$T/kit/file"
if cug_verify_kit "$T/kit" >/dev/null 2>&1; then echo 'FAIL: accepted corrupted payload'; exit 1; fi
printf 'original\n' > "$T/original"
printf 'old\n' > "$T/live"
cug_atomic_copy "$T/original" "$T/live"
cmp "$T/original" "$T/live"
for f in "$ROOT"/scripts/intel-test/*.sh; do bash -n "$f"; done
echo 'Intel installer transaction checks passed.'

#!/usr/bin/env python3
"""Non-destructive OpenCore config.plist injector for SSDT-GFX0 + CoreUltraGraphics."""
import argparse
import plistlib
import sys
from pathlib import Path

ACPI_ENTRY = {
    "Comment": "Inject Intel Arc Graphics Meteor Lake Hardware Topology Overlays",
    "Enabled": True,
    "Path": "SSDT-GFX0.aml",
}

KEXT_ENTRY = {
    "Arch": "x86_64",
    "BundlePath": "CoreUltraGraphics.kext",
    "Comment": "Core Ultra Integrated Graphics Custom Driver Substrate Interface",
    "Enabled": True,
    "ExecutablePath": "Contents/MacOS/CoreUltraGraphics",
    "MaxKernel": "",
    "MinKernel": "20.0.0",
    "PlistPath": "Contents/Info.plist",
}

def ensure_path(d: dict, *keys):
    cur = d
    for k in keys:
        if not isinstance(cur.get(k), dict):
            cur[k] = {}
        cur = cur[k]
    return cur

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", help="Path to OpenCore config.plist")
    args = ap.parse_args()
    cfg_path = Path(args.config)
    if not cfg_path.is_file():
        print(f"config.plist not found: {cfg_path}", file=sys.stderr)
        sys.exit(1)

    with cfg_path.open("rb") as f:
        data = plistlib.load(f)

    # 1. ACPI -> Add
    acpi = ensure_path(data, "ACPI")
    add = acpi.get("Add")
    if not isinstance(add, list):
        add = []
        acpi["Add"] = add
    if not any(isinstance(e, dict) and e.get("Path") == "SSDT-GFX0.aml" for e in add):
        add.append(dict(ACPI_ENTRY))
        print("Added ACPI SSDT-GFX0.aml")
    else:
        print("ACPI SSDT-GFX0.aml already present")

    # 2. Kernel -> Add (ensure Lilu first)
    kernel = ensure_path(data, "Kernel")
    kadd = kernel.get("Add")
    if not isinstance(kadd, list):
        kadd = []
        kernel["Add"] = kadd

    def idx_of(bundle: str):
        for i, e in enumerate(kadd):
            if isinstance(e, dict) and e.get("BundlePath") == bundle:
                return i
        return None

    if idx_of("CoreUltraGraphics.kext") is None:
        entry = dict(KEXT_ENTRY)
        lilu_idx = idx_of("Lilu.kext")
        if lilu_idx is not None:
            kadd.insert(lilu_idx + 1, entry)
        else:
            print("Warning: Lilu.kext not found, appending at end", file=sys.stderr)
            kadd.append(entry)
        print("Added Kernel CoreUltraGraphics.kext")
    else:
        print("Kernel CoreUltraGraphics.kext already present")

    with cfg_path.open("wb") as f:
        plistlib.dump(data, f, fmt=plistlib.FMT_XML, sort_keys=False)

    print(f"Wrote {cfg_path}")

if __name__ == "__main__":
    main()

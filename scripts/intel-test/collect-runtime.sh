#!/bin/bash
set -u
OUT=$1
sw_vers > "$OUT/macos.txt"
sysctl -n kern.bootargs > "$OUT/boot-args.txt"
ioreg -l -r -c IOFramebuffer -w 0 > "$OUT/framebuffers.txt"
ioreg -l -r -c IOAccelerator -w 0 > "$OUT/accelerators.txt"
ls -l /dev/dri > "$OUT/drm-nodes.txt" 2>&1
dmesg > "$OUT/dmesg.txt" 2>&1
exit 0

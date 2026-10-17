#!/bin/bash
set -euo pipefail
USB=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
/bin/bash "$USB/install-intel-boot-recorder.sh"
/bin/bash "$USB/apply-intel-worker-checkpoint.sh"
echo 'Live boot recorder is ready. Reboot through this USB, wait six minutes if stuck, then recover via SSD and collect-intel-failure.sh.'

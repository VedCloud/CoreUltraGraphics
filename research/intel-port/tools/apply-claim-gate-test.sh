#!/bin/bash
set -euo pipefail
USB=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
/bin/bash "$USB/install-intel-boot-recorder.sh"
/bin/bash "$USB/apply-intel-claim-gate.sh"

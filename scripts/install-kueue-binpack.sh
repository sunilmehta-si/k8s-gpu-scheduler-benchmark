#!/usr/bin/env bash
# kueue-binpack: Kueue for admission and quotas, with pods placed by the GPU bin-packing kube-scheduler.
set -euo pipefail
here="$(dirname "$0")"
"$here/install-kueue.sh"
"$here/install-kube-binpack-scheduler.sh"

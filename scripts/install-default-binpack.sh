#!/usr/bin/env bash
# default-binpack: kube-scheduler configured to bin-pack GPUs, as a second scheduler next to the default one.
set -euo pipefail
exec "$(dirname "$0")/install-kube-binpack-scheduler.sh"

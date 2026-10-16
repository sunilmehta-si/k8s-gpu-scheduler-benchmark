#!/usr/bin/env bash
# volcano-binpack: Volcano with its default plugins, and binpack told to score nvidia.com/gpu.
set -euo pipefail
GSB="${GSB:-gsb}"
here="$(dirname "$0")"
"$here/install-volcano.sh"
cd "$here/.."
$GSB manifests --stack volcano-binpack --part scheduler --fleet fleets/lab-32.yaml --trace traces/lab-32-smoke.jsonl \
  | kubectl apply -f -
kubectl -n volcano-system rollout restart deployment/volcano-scheduler    # read the new configuration now
kubectl -n volcano-system rollout status deployment/volcano-scheduler --timeout=180s
echo "volcano scheduler now bin-packs nvidia.com/gpu"

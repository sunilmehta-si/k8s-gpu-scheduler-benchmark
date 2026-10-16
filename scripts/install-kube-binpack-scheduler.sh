#!/usr/bin/env bash
# Run a second kube-scheduler, gsb-binpack, whose profile bin-packs GPUs (NodeResourcesFit MostAllocated scoring
# nvidia.com/gpu). Its image matches the cluster's version. Used by the default-binpack and kueue-binpack variants.
set -euo pipefail
GSB="${GSB:-gsb}"
cd "$(dirname "$0")/.."
version="$(kubectl version -o json | python3 -c 'import json, sys; print(json.load(sys.stdin)["serverVersion"]["gitVersion"])')"
$GSB manifests --stack default-binpack --part scheduler --kube-version "$version" \
  --fleet fleets/lab-32.yaml --trace traces/lab-32-smoke.jsonl | kubectl apply -f -
kubectl -n kube-system rollout status deployment/gsb-binpack --timeout=180s
echo "gsb-binpack scheduler $version ready"

#!/usr/bin/env bash
# Download the cluster results of every successful `cluster` workflow run on main into OUT/<run id>/, for
# `gsb repeats`. Runs before SINCE are left out: 38889757797 is the first run after both kwok fixes
# (docs/cluster-runs.md#how-a-run-is-checked). Runs already downloaded are kept. Needs an authenticated gh.
# GitHub keeps workflow artifacts for 90 days, which is why results/cluster/repeats.json keeps every run's numbers.
set -euo pipefail
out="${1:-cluster-runs}"
since="${2:-38889757797}"
repo="${GSB_REPO:-sunilmehta-si/k8s-gpu-scheduler-benchmark}"
mkdir -p "$out"
ids=$(gh run list --repo "$repo" --workflow cluster --branch main --status success --limit 500 \
  --json databaseId --jq ".[] | select(.databaseId >= $since) | .databaseId")
for id in $ids; do
  [ -d "$out/$id" ] && continue
  echo "fetching run $id" >&2
  gh run download "$id" --repo "$repo" --dir "$out/$id.partial" --pattern 'cluster-*'
  mv "$out/$id.partial" "$out/$id"
done

#!/usr/bin/env bash
# Install KAI Scheduler from its OCI Helm chart (chart tags have no leading v) and wait for its components.
set -euo pipefail
KAI_VERSION="${KAI_VERSION:-0.18.6}"
helm upgrade -i kai-scheduler oci://ghcr.io/kai-scheduler/kai-scheduler/kai-scheduler \
  -n kai-scheduler --create-namespace --version "$KAI_VERSION" --wait --timeout 5m
kubectl -n kai-scheduler wait --for=condition=Available deployment --all --timeout=300s
echo "kai-scheduler $KAI_VERSION ready"

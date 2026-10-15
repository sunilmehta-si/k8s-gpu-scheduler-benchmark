#!/usr/bin/env bash
# Install Kueue from its release manifest and wait for the controller (and its webhook) to be ready.
set -euo pipefail
KUEUE_VERSION="${KUEUE_VERSION:-v0.20.1}"
kubectl apply --server-side -f "https://github.com/kubernetes-sigs/kueue/releases/download/$KUEUE_VERSION/manifests.yaml"
kubectl -n kueue-system wait --for=condition=Available deployment/kueue-controller-manager --timeout=300s
echo "kueue $KUEUE_VERSION ready"

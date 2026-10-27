#!/usr/bin/env bash
# Create (or reuse) a kind cluster and install kwok with the stages the benchmark relies on:
#   node/fast + node/heartbeat-with-lease  -> fake nodes become Ready and stay Ready
#   pod/general                            -> pods become Ready, then complete after the
#                                             pod-complete.stage.kwok.x-k8s.io/delay annotation
# Usage: scripts/cluster-up.sh        (CLUSTER, and any pin in cluster/versions.env, can be overridden)
set -euo pipefail
. "$(dirname "$0")/lib.sh"
CLUSTER="${CLUSTER:-gsb}"
cd "$(dirname "$0")/.."

if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  kind create cluster --name "$CLUSTER" --config cluster/kind.yaml --wait 120s
fi
kubectl config use-context "kind-$CLUSTER" >/dev/null

base="https://github.com/kubernetes-sigs/kwok"
kubectl apply -f "$base/releases/download/$KWOK_VERSION/kwok.yaml"
for stage in node/fast node/heartbeat-with-lease pod/general; do
  kubectl apply -k "$base/kustomize/stage/$stage?ref=$KWOK_VERSION"
done
kubectl -n kube-system rollout status deployment/kwok-controller --timeout=180s
echo "cluster $CLUSTER ready with kwok $KWOK_VERSION"

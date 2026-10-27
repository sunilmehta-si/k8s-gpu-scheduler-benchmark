#!/usr/bin/env bash
# Install Volcano from its release installer and wait for the scheduler, controllers and admission webhook.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
kubectl apply -f "https://raw.githubusercontent.com/volcano-sh/volcano/$VOLCANO_VERSION/installer/volcano-development.yaml"
kubectl -n volcano-system wait --for=condition=Available deployment --all --timeout=300s
echo "volcano $VOLCANO_VERSION ready"

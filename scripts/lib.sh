#!/usr/bin/env bash
# Sourced by the other scripts: export each pin in cluster/versions.env unless the environment already sets it.
set -euo pipefail
while IFS='=' read -r key value; do
  [[ -z "$key" || "$key" == \#* ]] && continue
  [ -n "${!key:-}" ] || export "$key=$value"
done < "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/cluster/versions.env"

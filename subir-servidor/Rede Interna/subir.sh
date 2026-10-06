#!/usr/bin/env bash
set -Eeuo pipefail
DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_AREA=interna
source "$DEPLOY_DIR/../common.sh"

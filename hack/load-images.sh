#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGES_FILE="$SCRIPT_DIR/images.list"
KIND_CLUSTER_NAME="evil-genius-cupcakes"

if [[ ! -f "$IMAGES_FILE" ]]; then
  echo "ERROR: Image list file '$IMAGES_FILE' not found."
  exit 1
fi

while IFS= read -r image || [[ -n "$image" ]]; do
  image="$(echo "$image" | xargs)"
  if [[ -z "$image" ]]; then
    continue
  fi
  echo "🔄 Loading image: $image"
  podman pull "$image" &>/dev/null
  TMP_TAR="$(mktemp).tar"
  podman save -o "$TMP_TAR" "$image" &>/dev/null
  kind load image-archive "$TMP_TAR" --name "$KIND_CLUSTER_NAME" 2> >(grep -v 'enabling experimental podman provider' >&2)
  rm -f "$TMP_TAR"
done < "$IMAGES_FILE"

echo "✅ All images loaded into kind cluster '$KIND_CLUSTER_NAME'."

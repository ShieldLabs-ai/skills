#!/usr/bin/env bash
# Compile the public framework result types and run the documented Node/JS examples.
set -euo pipefail
repository_root=$(cd "$(dirname "$0")/.." && pwd)
qa_directory=$(mktemp -d "${TMPDIR:-/tmp}/shieldlabs-skills-sdk.XXXXXX")
trap 'rm -rf "$qa_directory"' EXIT
# These tests use the wrappers' types and a controlled agent module, not full framework builds.
# Install peers explicitly; Next's runtime is unnecessary for its browser re-export types.
npm install --prefix "$qa_directory" --ignore-scripts --no-audit --no-fund --legacy-peer-deps \
  @shieldlabs-ai/node@1.3.0 @shieldlabs-ai/js@1.1.0 \
  @shieldlabs-ai/react@1.0.0 @shieldlabs-ai/next@1.0.0 @shieldlabs-ai/vue@1.0.0 \
  @shieldlabs-ai/angular@1.0.0 @shieldlabs-ai/svelte@1.0.0 \
  react@19 @types/react@19 vue@3 svelte@5 @angular/core@22 @angular/common@22 rxjs@7 \
  typescript@5.9.3 @types/node@24
cp "$repository_root/tests/sdk_current_types.ts" "$qa_directory/sdk_current_types.ts"
"$qa_directory/node_modules/.bin/tsc" --noEmit --strict --skipLibCheck --target ES2022 \
  --module NodeNext --moduleResolution NodeNext "$qa_directory/sdk_current_types.ts"
SHIELDLABS_SDK_QA_DIR="$qa_directory" node --experimental-vm-modules "$repository_root/tests/sdk_current_examples.mjs"

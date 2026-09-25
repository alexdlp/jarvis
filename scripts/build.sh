#!/usr/bin/env bash
set -euo pipefail

# Assemble the Lambda deployment package for its Linux ARM64 runtime. Some
# dependencies contain compiled extensions, so installing packages for the
# developer's macOS platform would create an archive Lambda cannot import.

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
build_dir="$repo_root/build"

cd "$repo_root"
rm -rf "$build_dir"
mkdir -p "$build_dir"

# Export only locked runtime dependencies and verify their hashes. The Python
# version and platform must continue to match infra/lambda.tf.
uv export --locked --no-dev --no-emit-project --format requirements.txt | \
    uv pip install --quiet --require-hashes \
        --python-platform aarch64-manylinux_2_17 \
        --python-version 3.13 \
        --target "$build_dir" \
        -r -

# The project itself is excluded from uv's dependency export and copied after
# its third-party dependencies.
cp -R src/jarvis "$build_dir/jarvis"

package_size="$(du -sh "$build_dir" | cut -f1)"
printf '  package ready %s\n' "$package_size"

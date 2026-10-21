#!/usr/bin/env bash
# Adapter for the Wine runner; the NDK/CMake recipe is shared with Windows.
set -euo pipefail
ROOT="$(cd "$1" && pwd)"
key="$2"
component="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/tools/build/ndk-env.sh"
work="${ARLINUX_PULSE_WORK:-$ROOT/build/pulseaudio-work/$key}"
out="${ARLINUX_PULSE_OUTPUT:-$ROOT/build/pulseaudio}"
exec python3 "$component/arlinux/build.py" --ndk "$NDK" --api "$ANDROID_API" \
    --cmake "$(command -v cmake)" --ninja "$(command -v ninja)" \
    --work "$work" --output "$out"

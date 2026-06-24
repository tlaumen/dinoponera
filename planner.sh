#!/usr/bin/env bash
set -euo pipefail

pi --system-prompt "$(cat .pi/agent/planner.md)" "$@"

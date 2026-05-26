#!/usr/bin/env bash
exec "$(cd "$(dirname "$0")" && pwd)/scripts/deploy/update.sh" "$@"

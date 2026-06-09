#!/usr/bin/env bash
# Merge Gantt + user data from evohome → crc on the same MongoDB cluster.
# Preserves existing crc documents (no --drop-target).
set -euo pipefail

if [[ -z "${MONGO_URL:-}" ]]; then
  echo "Set MONGO_URL to your DigitalOcean Mongo connection string." >&2
  exit 1
fi

export SOURCE_MONGO_URL="$MONGO_URL"
export TARGET_MONGO_URL="$MONGO_URL"
export SOURCE_DB_NAME="${SOURCE_DB_NAME:-evohome}"
export TARGET_DB_NAME="${TARGET_DB_NAME:-crc}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "Source DB: $SOURCE_DB_NAME"
echo "Target DB: $TARGET_DB_NAME"
echo ""

python3 backend/scripts/migrate_mongo.py --profile crc --dry-run "$@"
echo ""
read -r -p "Dry run above. Copy evohome → crc? Type yes: " confirm
if [[ "$confirm" != "yes" ]]; then
  echo "Aborted."
  exit 0
fi

export CONFIRM_TARGET=yes
python3 backend/scripts/migrate_mongo.py --profile crc "$@"

#!/usr/bin/env bash
# Full-database copy via mongodump / mongorestore (requires MongoDB Database Tools).
#
#   export SOURCE_MONGO_URL='mongodb+srv://...'
#   export SOURCE_DB_NAME='evohome'
#   export TARGET_MONGO_URL='mongodb+srv://...'
#   export TARGET_DB_NAME='evohome'
#   export CONFIRM_TARGET='yes'
#   ./scripts/mongo_migrate.sh

set -euo pipefail

: "${SOURCE_MONGO_URL:?SOURCE_MONGO_URL required}"
: "${SOURCE_DB_NAME:?SOURCE_DB_NAME required}"
: "${TARGET_MONGO_URL:?TARGET_MONGO_URL required}"
: "${TARGET_DB_NAME:?TARGET_DB_NAME required}"

if [[ "${CONFIRM_TARGET:-}" != "yes" ]]; then
  echo "Set CONFIRM_TARGET=yes to write to target" >&2
  exit 1
fi

if ! command -v mongodump >/dev/null || ! command -v mongorestore >/dev/null; then
  echo "Install MongoDB Database Tools: https://www.mongodb.com/docs/database-tools/" >&2
  exit 1
fi

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

echo "Dumping ${SOURCE_DB_NAME}..."
mongodump --uri="${SOURCE_MONGO_URL}" --db="${SOURCE_DB_NAME}" --out="${TMPDIR}/dump"

echo "Restoring into ${TARGET_DB_NAME}..."
mongorestore \
  --uri="${TARGET_MONGO_URL}" \
  --nsFrom="${SOURCE_DB_NAME}.*" \
  --nsTo="${TARGET_DB_NAME}.*" \
  --drop \
  "${TMPDIR}/dump"

echo "Done. Verify counts in Atlas / DO MongoDB UI."

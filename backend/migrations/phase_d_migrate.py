"""
Phase D: Data Migration Script
===============================
Migrates data from deprecated collections to canonical collections.
All operations are idempotent (safe to run multiple times).

Usage:
    python migrations/phase_d_migrate.py --dry-run     # Preview changes
    python migrations/phase_d_migrate.py --backup       # Backup only
    python migrations/phase_d_migrate.py --execute      # Run migration
    python migrations/phase_d_migrate.py --verify       # Verify integrity
    python migrations/phase_d_migrate.py --full         # Backup + Execute + Verify + Report
"""

import asyncio
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

BACKUP_DIR = Path(__file__).parent / "backup"
REPORT_PATH = Path(__file__).parent / "MIGRATION_REPORT.md"

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "evohome")

# Migration definitions
MIGRATIONS = [
    {
        "id": "M1",
        "name": "project_units → units",
        "source": "project_units",
        "target": "units",
        "primary_key": "unit_id",
        "field_renames": {},
    },
    {
        "id": "M2",
        "name": "project_timelines → timelines",
        "source": "project_timelines",
        "target": "timelines",
        "primary_key": "timeline_id",
        "field_renames": {"project_timeline_id": "timeline_id"},
    },
    {
        "id": "M3",
        "name": "timeline_steps field normalization",
        "source": "timeline_steps",
        "target": "timeline_steps",
        "primary_key": "step_id",
        "field_renames": {},
        "field_additions": {"project_timeline_id": "timeline_id"},
    },
]


class MigrationRunner:
    def __init__(self, db):
        self.db = db
        self.log = []
        self.stats = {
            "backup": {},
            "migrations": {},
            "verification": {},
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

    def _log(self, msg):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        self.log.append(line)

    # ==================================================================
    # BACKUP
    # ==================================================================

    async def backup(self):
        self._log("=" * 60)
        self._log("PHASE D BACKUP")
        self._log("=" * 60)

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_subdir = BACKUP_DIR / timestamp
        backup_subdir.mkdir(exist_ok=True)

        collections_to_backup = [
            "project_units",
            "project_timelines",
            "project_stages",
            "timeline_steps",
            "units",
            "timelines",
        ]

        summary = {}
        for coll_name in collections_to_backup:
            coll = self.db[coll_name]
            count = await coll.count_documents({})
            docs = await coll.find({}).to_list(None)

            # Serialize ObjectId to string for JSON
            for doc in docs:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])

            backup_file = backup_subdir / f"{coll_name}.json"
            backup_file.write_text(json.dumps(docs, indent=2, default=str))

            summary[coll_name] = count
            self._log(f"  Backed up {coll_name}: {count} docs → {backup_file.name}")

        self.stats["backup"] = {
            "timestamp": timestamp,
            "directory": str(backup_subdir),
            "collections": summary,
        }

        self._log(f"  Backup complete → {backup_subdir}")
        return backup_subdir

    # ==================================================================
    # DRY RUN
    # ==================================================================

    async def dry_run(self):
        self._log("=" * 60)
        self._log("PHASE D DRY RUN (no writes)")
        self._log("=" * 60)

        for m in MIGRATIONS:
            await self._dry_run_migration(m)

    async def _dry_run_migration(self, m):
        mid = m["id"]
        self._log(f"\n--- {mid}: {m['name']} ---")

        source_coll = self.db[m["source"]]
        target_coll = self.db[m["target"]]
        pk = m["primary_key"]

        source_count = await source_coll.count_documents({})
        target_count = await target_coll.count_documents({})

        if m["source"] == m["target"]:
            # Field normalization (M3)
            field_adds = m.get("field_additions", {})
            for old_field, new_field in field_adds.items():
                needs_add = await source_coll.count_documents(
                    {old_field: {"$exists": True}, new_field: {"$exists": False}}
                )
                self._log(
                    f"  {source_count} docs in {m['source']}, "
                    f"{needs_add} need {new_field} field added from {old_field}"
                )
        else:
            # Collection copy (M1, M2)
            would_insert = 0
            would_skip = 0
            docs = await source_coll.find({}, {"_id": 0}).to_list(None)
            for doc in docs:
                pk_value = doc.get(pk)
                if not pk_value:
                    # For M2: source may use project_timeline_id instead
                    renames = m.get("field_renames", {})
                    for old_name, new_name in renames.items():
                        if old_name in doc and new_name == pk:
                            pk_value = doc[old_name]
                            break

                if pk_value:
                    existing = await target_coll.find_one({pk: pk_value})
                    if existing:
                        would_skip += 1
                    else:
                        would_insert += 1
                else:
                    self._log(f"  WARNING: doc missing primary key {pk}: {list(doc.keys())}")

            self._log(
                f"  {m['source']}: {source_count} docs → "
                f"{m['target']}: {target_count} existing | "
                f"Would insert: {would_insert}, Would skip: {would_skip}"
            )

    # ==================================================================
    # EXECUTE
    # ==================================================================

    async def execute(self):
        self._log("=" * 60)
        self._log("PHASE D MIGRATION EXECUTE")
        self._log("=" * 60)

        for m in MIGRATIONS:
            result = await self._execute_migration(m)
            self.stats["migrations"][m["id"]] = result

    async def _execute_migration(self, m):
        mid = m["id"]
        self._log(f"\n--- {mid}: {m['name']} ---")

        source_coll = self.db[m["source"]]
        target_coll = self.db[m["target"]]
        pk = m["primary_key"]

        result = {"inserted": 0, "skipped": 0, "updated": 0, "errors": []}

        if m["source"] == m["target"]:
            # Field normalization (M3: timeline_steps)
            field_adds = m.get("field_additions", {})
            for old_field, new_field in field_adds.items():
                # Find docs that have old_field but not new_field
                cursor = source_coll.find(
                    {old_field: {"$exists": True}, new_field: {"$exists": False}}
                )
                async for doc in cursor:
                    try:
                        await source_coll.update_one(
                            {"_id": doc["_id"]},
                            {"$set": {new_field: doc[old_field]}},
                        )
                        result["updated"] += 1
                    except Exception as e:
                        result["errors"].append(
                            f"Failed to add {new_field} to {doc.get(pk)}: {e}"
                        )

                self._log(
                    f"  Added {new_field} to {result['updated']} docs "
                    f"(from {old_field})"
                )
        else:
            # Collection migration (M1, M2)
            docs = await source_coll.find({}, {"_id": 0}).to_list(None)
            renames = m.get("field_renames", {})

            for doc in docs:
                # Apply field renames
                for old_name, new_name in renames.items():
                    if old_name in doc:
                        if new_name not in doc:
                            doc[new_name] = doc[old_name]
                        del doc[old_name]

                pk_value = doc.get(pk)
                if not pk_value:
                    result["errors"].append(
                        f"Doc missing primary key {pk}: {list(doc.keys())}"
                    )
                    continue

                # Idempotent upsert
                existing = await target_coll.find_one({pk: pk_value})
                if existing:
                    result["skipped"] += 1
                else:
                    try:
                        await target_coll.insert_one(doc)
                        result["inserted"] += 1
                    except Exception as e:
                        result["errors"].append(f"Failed to insert {pk_value}: {e}")

            self._log(
                f"  {m['source']} → {m['target']}: "
                f"inserted={result['inserted']}, "
                f"skipped={result['skipped']}, "
                f"errors={len(result['errors'])}"
            )

        if result["errors"]:
            for err in result["errors"]:
                self._log(f"  ERROR: {err}")

        return result

    # ==================================================================
    # VERIFY
    # ==================================================================

    async def verify(self):
        self._log("=" * 60)
        self._log("PHASE D INTEGRITY VERIFICATION")
        self._log("=" * 60)

        checks = []

        # Check 1: units collection has all data from project_units
        c1 = await self._verify_collection_migration(
            "project_units", "units", "unit_id"
        )
        checks.append(c1)

        # Check 2: timelines collection has all data from project_timelines
        c2 = await self._verify_collection_migration(
            "project_timelines", "timelines", "timeline_id", {"project_timeline_id": "timeline_id"}
        )
        checks.append(c2)

        # Check 3: timeline_steps all have timeline_id field
        c3 = await self._verify_field_normalization(
            "timeline_steps", "timeline_id"
        )
        checks.append(c3)

        # Check 4: Referential integrity — timeline_steps reference valid timelines
        c4 = await self._verify_referential_integrity()
        checks.append(c4)

        # Check 5: No orphaned data
        c5 = await self._verify_no_orphans()
        checks.append(c5)

        self.stats["verification"] = {
            "checks": checks,
            "all_passed": all(c["passed"] for c in checks),
        }

        self._log(f"\n  RESULT: {'ALL PASSED' if self.stats['verification']['all_passed'] else 'SOME FAILED'}")
        return self.stats["verification"]["all_passed"]

    async def _verify_collection_migration(self, source_name, target_name, pk, field_renames=None):
        source = self.db[source_name]
        target = self.db[target_name]

        source_count = await source.count_documents({})
        target_count = await target.count_documents({})

        # For each doc in source, check it exists in target
        missing = []
        source_docs = await source.find({}, {"_id": 0}).to_list(None)
        for doc in source_docs:
            pk_value = doc.get(pk)
            if not pk_value and field_renames:
                for old_name, new_name in field_renames.items():
                    if old_name in doc and new_name == pk:
                        pk_value = doc[old_name]
                        break
            if pk_value:
                exists = await target.find_one({pk: pk_value})
                if not exists:
                    missing.append(pk_value)

        passed = len(missing) == 0
        check = {
            "name": f"{source_name} → {target_name}",
            "source_count": source_count,
            "target_count": target_count,
            "missing": missing,
            "passed": passed,
        }

        status = "PASS" if passed else "FAIL"
        self._log(
            f"  [{status}] {source_name} ({source_count}) → "
            f"{target_name} ({target_count}) | missing: {len(missing)}"
        )
        return check

    async def _verify_field_normalization(self, coll_name, required_field):
        coll = self.db[coll_name]
        total = await coll.count_documents({})
        with_field = await coll.count_documents({required_field: {"$exists": True}})
        without_field = total - with_field

        passed = without_field == 0
        check = {
            "name": f"{coll_name}.{required_field} normalization",
            "total": total,
            "with_field": with_field,
            "without_field": without_field,
            "passed": passed,
        }

        status = "PASS" if passed else "FAIL"
        self._log(
            f"  [{status}] {coll_name}.{required_field}: "
            f"{with_field}/{total} have field"
        )
        return check

    async def _verify_referential_integrity(self):
        steps_coll = self.db["timeline_steps"]
        timelines_coll = self.db["timelines"]

        orphaned = []
        steps = await steps_coll.find({}, {"_id": 0, "step_id": 1, "timeline_id": 1, "project_timeline_id": 1}).to_list(None)

        for step in steps:
            tl_id = step.get("timeline_id") or step.get("project_timeline_id")
            if tl_id:
                exists = await timelines_coll.find_one(
                    {"$or": [{"timeline_id": tl_id}, {"project_timeline_id": tl_id}]}
                )
                if not exists:
                    orphaned.append({"step_id": step.get("step_id"), "references": tl_id})

        passed = len(orphaned) == 0
        check = {
            "name": "timeline_steps → timelines referential integrity",
            "total_steps": len(steps),
            "orphaned": orphaned,
            "passed": passed,
        }

        status = "PASS" if passed else f"FAIL ({len(orphaned)} orphans)"
        self._log(f"  [{status}] timeline_steps → timelines: {len(steps)} steps checked")
        return check

    async def _verify_no_orphans(self):
        units_coll = self.db["units"]
        projects_coll = self.db["projects"]

        orphaned = []
        units = await units_coll.find({}, {"_id": 0, "unit_id": 1, "project_id": 1}).to_list(None)
        for unit in units:
            pid = unit.get("project_id")
            if pid:
                exists = await projects_coll.find_one({"project_id": pid})
                if not exists:
                    orphaned.append({"unit_id": unit.get("unit_id"), "project_id": pid})

        passed = len(orphaned) == 0
        check = {
            "name": "units → projects referential integrity",
            "total_units": len(units),
            "orphaned": orphaned,
            "passed": passed,
        }

        status = "PASS" if passed else f"FAIL ({len(orphaned)} orphans)"
        self._log(f"  [{status}] units → projects: {len(units)} units checked")
        return check

    # ==================================================================
    # REPORT
    # ==================================================================

    def generate_report(self):
        self.stats["completed_at"] = datetime.now(timezone.utc).isoformat()

        lines = [
            "# Phase D: Data Migration Report",
            f"**Generated**: {self.stats['completed_at']}",
            f"**Database**: {DB_NAME}",
            "",
            "---",
            "",
            "## Backup",
        ]

        backup = self.stats.get("backup", {})
        if backup:
            lines.append(f"**Timestamp**: {backup.get('timestamp', 'N/A')}")
            lines.append(f"**Directory**: `{backup.get('directory', 'N/A')}`")
            lines.append("")
            lines.append("| Collection | Documents Backed Up |")
            lines.append("|---|---|")
            for coll, count in backup.get("collections", {}).items():
                lines.append(f"| `{coll}` | {count} |")
        else:
            lines.append("Backup was not run in this execution.")

        lines.extend(["", "---", "", "## Migrations"])

        migrations = self.stats.get("migrations", {})
        if migrations:
            lines.append("")
            lines.append("| Migration | Inserted | Skipped | Updated | Errors |")
            lines.append("|---|---|---|---|---|")
            for mid, result in migrations.items():
                name = next((m["name"] for m in MIGRATIONS if m["id"] == mid), mid)
                lines.append(
                    f"| {mid}: {name} | {result.get('inserted', 0)} | "
                    f"{result.get('skipped', 0)} | {result.get('updated', 0)} | "
                    f"{len(result.get('errors', []))} |"
                )

            for mid, result in migrations.items():
                if result.get("errors"):
                    lines.append(f"\n### {mid} Errors")
                    for err in result["errors"]:
                        lines.append(f"- {err}")
        else:
            lines.append("No migrations were executed.")

        lines.extend(["", "---", "", "## Verification"])

        verification = self.stats.get("verification", {})
        if verification:
            all_passed = verification.get("all_passed", False)
            lines.append(f"\n**Overall**: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
            lines.append("")
            lines.append("| Check | Result | Details |")
            lines.append("|---|---|---|")
            for check in verification.get("checks", []):
                status = "PASS" if check["passed"] else "FAIL"
                details = ""
                if "source_count" in check:
                    details = f"source={check['source_count']}, target={check['target_count']}, missing={len(check.get('missing', []))}"
                elif "total" in check:
                    details = f"{check.get('with_field', 0)}/{check['total']} have field"
                elif "total_steps" in check:
                    details = f"{check['total_steps']} checked, {len(check.get('orphaned', []))} orphans"
                elif "total_units" in check:
                    details = f"{check['total_units']} checked, {len(check.get('orphaned', []))} orphans"
                lines.append(f"| {check['name']} | {status} | {details} |")
        else:
            lines.append("Verification was not run.")

        lines.extend(["", "---", "", "## Execution Log", "```"])
        lines.extend(self.log)
        lines.extend(["```", "", "---", f"*Report generated: {self.stats['completed_at']}*", ""])

        report_text = "\n".join(lines)
        REPORT_PATH.write_text(report_text)
        self._log(f"\nReport written to {REPORT_PATH}")
        return report_text


async def main():
    parser = argparse.ArgumentParser(description="Phase D Data Migration")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--backup", action="store_true", help="Backup only")
    parser.add_argument("--execute", action="store_true", help="Run migration")
    parser.add_argument("--verify", action="store_true", help="Verify integrity only")
    parser.add_argument("--full", action="store_true", help="Backup + Execute + Verify + Report")
    args = parser.parse_args()

    if not any([args.dry_run, args.backup, args.execute, args.verify, args.full]):
        parser.print_help()
        sys.exit(1)

    if not MONGO_URL:
        print("ERROR: MONGO_URL not set")
        sys.exit(1)

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    runner = MigrationRunner(db)

    try:
        if args.dry_run:
            await runner.dry_run()

        elif args.backup:
            await runner.backup()

        elif args.execute:
            await runner.execute()
            runner.generate_report()

        elif args.verify:
            passed = await runner.verify()
            runner.generate_report()
            if not passed:
                sys.exit(1)

        elif args.full:
            # Step 1: Backup
            await runner.backup()

            # Step 2: Dry run
            await runner.dry_run()

            # Step 3: Execute
            await runner.execute()

            # Step 4: Verify
            passed = await runner.verify()

            # Step 5: Report
            runner.generate_report()

            if not passed:
                runner._log("MIGRATION COMPLETED WITH VERIFICATION FAILURES")
                sys.exit(1)
            else:
                runner._log("MIGRATION COMPLETED SUCCESSFULLY")

    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())

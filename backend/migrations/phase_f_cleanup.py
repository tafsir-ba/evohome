"""
Phase F: Deprecation Cleanup — DB Operations
=============================================
1. $unset project_timeline_id from timelines and timeline_steps
2. Drop deprecated collections (project_timelines, project_units, project_stages)

Idempotent. Safe to run multiple times.

Usage:
    python migrations/phase_f_cleanup.py --dry-run
    python migrations/phase_f_cleanup.py --execute
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
REPORT_PATH = Path(__file__).parent / "PHASE_F_CLEANUP_REPORT.md"

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "evohome")

DEPRECATED_COLLECTIONS = ["project_timelines", "project_units", "project_stages"]


class CleanupRunner:
    def __init__(self, db):
        self.db = db
        self.log = []
        self.stats = {"started_at": datetime.now(timezone.utc).isoformat()}

    def _log(self, msg):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        self.log.append(line)

    async def backup(self):
        self._log("=== PRE-CLEANUP BACKUP ===")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_subdir = BACKUP_DIR / f"{timestamp}_phase_f"
        backup_subdir.mkdir(exist_ok=True)

        for coll_name in DEPRECATED_COLLECTIONS + ["timelines", "timeline_steps"]:
            coll = self.db[coll_name]
            count = await coll.count_documents({})
            docs = await coll.find({}).to_list(None)
            for doc in docs:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
            (backup_subdir / f"{coll_name}.json").write_text(
                json.dumps(docs, indent=2, default=str)
            )
            self._log(f"  Backed up {coll_name}: {count} docs")

        self.stats["backup_dir"] = str(backup_subdir)
        self._log(f"  Backup → {backup_subdir}")

    async def dry_run(self):
        self._log("=== DRY RUN (no writes) ===")

        # Field cleanup
        for coll_name in ["timelines", "timeline_steps"]:
            coll = self.db[coll_name]
            has_field = await coll.count_documents({"project_timeline_id": {"$exists": True}})
            total = await coll.count_documents({})
            self._log(f"  {coll_name}: {has_field}/{total} docs have project_timeline_id → would $unset")

        # Collection drops
        existing = await self.db.list_collection_names()
        for coll_name in DEPRECATED_COLLECTIONS:
            if coll_name in existing:
                count = await self.db[coll_name].count_documents({})
                self._log(f"  {coll_name}: {count} docs → would DROP")
            else:
                self._log(f"  {coll_name}: does not exist (already dropped)")

    async def execute(self):
        self._log("=== EXECUTING CLEANUP ===")
        self.stats["operations"] = {}

        # Step 1: $unset project_timeline_id
        for coll_name in ["timelines", "timeline_steps"]:
            coll = self.db[coll_name]
            before = await coll.count_documents({"project_timeline_id": {"$exists": True}})
            result = await coll.update_many(
                {"project_timeline_id": {"$exists": True}},
                {"$unset": {"project_timeline_id": ""}}
            )
            self.stats["operations"][f"unset_{coll_name}"] = {
                "before": before, "modified": result.modified_count
            }
            self._log(f"  $unset project_timeline_id from {coll_name}: {result.modified_count} modified")

        # Step 2: Drop deprecated collections
        existing = await self.db.list_collection_names()
        for coll_name in DEPRECATED_COLLECTIONS:
            if coll_name in existing:
                count = await self.db[coll_name].count_documents({})
                await self.db.drop_collection(coll_name)
                self.stats["operations"][f"drop_{coll_name}"] = {"count": count, "dropped": True}
                self._log(f"  Dropped {coll_name} ({count} docs)")
            else:
                self.stats["operations"][f"drop_{coll_name}"] = {"dropped": False, "reason": "not found"}
                self._log(f"  {coll_name}: already absent")

    async def verify(self):
        self._log("=== VERIFICATION ===")
        checks = []

        # Check 1: No project_timeline_id in canonical collections
        for coll_name in ["timelines", "timeline_steps"]:
            remaining = await self.db[coll_name].count_documents({"project_timeline_id": {"$exists": True}})
            passed = remaining == 0
            checks.append({"name": f"{coll_name} has no project_timeline_id", "passed": passed, "remaining": remaining})
            self._log(f"  [{'PASS' if passed else 'FAIL'}] {coll_name}.project_timeline_id: {remaining} remaining")

        # Check 2: Deprecated collections gone
        existing = await self.db.list_collection_names()
        for coll_name in DEPRECATED_COLLECTIONS:
            gone = coll_name not in existing
            checks.append({"name": f"{coll_name} dropped", "passed": gone})
            self._log(f"  [{'PASS' if gone else 'FAIL'}] {coll_name}: {'dropped' if gone else 'STILL EXISTS'}")

        # Check 3: Canonical data intact
        for coll_name in ["timelines", "timeline_steps", "units"]:
            count = await self.db[coll_name].count_documents({})
            passed = count > 0
            checks.append({"name": f"{coll_name} has data", "passed": passed, "count": count})
            self._log(f"  [{'PASS' if passed else 'FAIL'}] {coll_name}: {count} docs")

        all_passed = all(c["passed"] for c in checks)
        self.stats["verification"] = {"checks": checks, "all_passed": all_passed}
        self._log(f"  RESULT: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
        return all_passed

    def generate_report(self):
        self.stats["completed_at"] = datetime.now(timezone.utc).isoformat()
        lines = [
            "# Phase F: Deprecation Cleanup Report",
            f"**Generated**: {self.stats['completed_at']}",
            f"**Database**: {DB_NAME}",
            "",
        ]

        if "operations" in self.stats:
            lines.extend(["## Operations", "", "| Operation | Details |", "|---|---|"])
            for op, detail in self.stats["operations"].items():
                lines.append(f"| {op} | {json.dumps(detail)} |")

        if "verification" in self.stats:
            v = self.stats["verification"]
            lines.extend(["", f"## Verification: {'ALL PASSED' if v['all_passed'] else 'FAILURES'}", "",
                          "| Check | Result |", "|---|---|"])
            for c in v["checks"]:
                lines.append(f"| {c['name']} | {'PASS' if c['passed'] else 'FAIL'} |")

        lines.extend(["", "## Log", "```"] + self.log + ["```", ""])
        REPORT_PATH.write_text("\n".join(lines))
        self._log(f"Report → {REPORT_PATH}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if not any([args.dry_run, args.execute]):
        parser.print_help()
        sys.exit(1)

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    runner = CleanupRunner(db)

    try:
        if args.dry_run:
            await runner.dry_run()
        elif args.execute:
            await runner.backup()
            await runner.execute()
            passed = await runner.verify()
            runner.generate_report()
            if not passed:
                sys.exit(1)
            runner._log("CLEANUP COMPLETED SUCCESSFULLY")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())

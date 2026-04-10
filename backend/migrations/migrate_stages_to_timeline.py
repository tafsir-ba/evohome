"""
Migration Script: project_stages → timeline_steps
Phase 1 of Architecture Reset

This script:
1. Captures BEFORE state (project_stages count and sample)
2. Creates project_timelines for projects that don't have one
3. Migrates project_stages to timeline_steps with field mapping
4. Captures AFTER state (timeline_steps count and sample)
5. Verifies data integrity (before/after payload parity)

Run with: python migrations/migrate_stages_to_timeline.py
"""

import asyncio
import json
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os
import uuid

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'evohome')

# Status mapping: ProjectStage → TimelineStep
STATUS_MAP = {
    'upcoming': 'pending',
    'in_progress': 'in_progress',
    'completed': 'completed',
    'delayed': 'in_progress',  # Will add delayed flag if needed
    'on_hold': 'pending',       # Will add on_hold flag if needed
}


async def run_migration():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("=" * 60)
    print("PHASE 1 MIGRATION: project_stages → timeline_steps")
    print("=" * 60)
    
    # ========== BEFORE STATE ==========
    print("\n[1/5] Capturing BEFORE state...")
    
    stages_count = await db.project_stages.count_documents({})
    stages_sample = await db.project_stages.find({}, {"_id": 0}).limit(3).to_list(3)
    
    print(f"  - project_stages count: {stages_count}")
    if stages_sample:
        print(f"  - Sample stage: {json.dumps(stages_sample[0], indent=2, default=str)}")
    
    if stages_count == 0:
        print("\n[SKIP] No project_stages to migrate.")
        return
    
    # Get unique project_ids from stages
    pipeline = [{"$group": {"_id": "$project_id"}}]
    project_ids = [doc['_id'] for doc in await db.project_stages.aggregate(pipeline).to_list(100)]
    print(f"  - Projects with stages: {len(project_ids)}")
    
    # ========== CREATE MISSING TIMELINES ==========
    print("\n[2/5] Creating project_timelines for projects without one...")
    
    timelines_created = 0
    for project_id in project_ids:
        existing = await db.project_timelines.find_one({"project_id": project_id})
        if not existing:
            # Get project to find agent_id
            project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
            if project:
                timeline_id = f"timeline_{uuid.uuid4().hex[:12]}"
                timeline_doc = {
                    "timeline_id": timeline_id,
                    "project_timeline_id": timeline_id,  # Dual ID for compatibility
                    "project_id": project_id,
                    "template_id": None,
                    "template_name": "Migrated from Stages",
                    "is_demo": project.get('is_demo', False),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "migrated_from_stages": True
                }
                await db.project_timelines.insert_one(timeline_doc)
                timelines_created += 1
                print(f"    Created timeline {timeline_id} for project {project_id}")
    
    print(f"  - Timelines created: {timelines_created}")
    
    # ========== MIGRATE STAGES TO STEPS ==========
    print("\n[3/5] Migrating project_stages → timeline_steps...")
    
    migrated = 0
    skipped = 0
    errors = []
    
    async for stage in db.project_stages.find({}, {"_id": 0}):
        try:
            # Find the timeline for this project
            timeline = await db.project_timelines.find_one(
                {"project_id": stage['project_id']},
                {"_id": 0}
            )
            
            if not timeline:
                errors.append(f"No timeline for project {stage['project_id']}")
                skipped += 1
                continue
            
            # Check if already migrated (by stage_id)
            existing_step = await db.timeline_steps.find_one(
                {"step_id": stage['stage_id']},
                {"_id": 0}
            )
            if existing_step:
                skipped += 1
                continue
            
            # Map status
            original_status = stage.get('status', 'upcoming')
            mapped_status = STATUS_MAP.get(original_status, 'pending')
            
            # Create timeline_step document
            step_doc = {
                "step_id": stage['stage_id'],  # Preserve original ID
                "project_timeline_id": timeline.get('timeline_id') or timeline.get('project_timeline_id'),
                "title": stage['name'],
                "description": stage.get('description'),
                "status": mapped_status,
                "order_index": stage.get('order', 0),
                "planned_date": stage.get('planned_start'),  # Use start as planned_date
                "completed_at": stage.get('actual_end'),
                "created_at": stage.get('created_at', datetime.now(timezone.utc)).isoformat() if isinstance(stage.get('created_at'), datetime) else stage.get('created_at', datetime.now(timezone.utc).isoformat()),
                "updated_at": stage.get('updated_at', datetime.now(timezone.utc)).isoformat() if isinstance(stage.get('updated_at'), datetime) else stage.get('updated_at', datetime.now(timezone.utc).isoformat()),
                # Extended fields (preserving full data)
                "planned_start": stage.get('planned_start'),
                "planned_end": stage.get('planned_end'),
                "actual_start": stage.get('actual_start'),
                "progress_percent": stage.get('progress_percent', 0),
                "notes": stage.get('notes'),
                "dependencies": stage.get('dependencies', []),
                # Migration metadata
                "migrated_from_stage": True,
                "original_status": original_status,
                "is_demo": stage.get('is_demo', False)
            }
            
            await db.timeline_steps.insert_one(step_doc)
            migrated += 1
            
        except Exception as e:
            errors.append(f"Error migrating stage {stage.get('stage_id')}: {str(e)}")
    
    print(f"  - Migrated: {migrated}")
    print(f"  - Skipped (already exists): {skipped}")
    print(f"  - Errors: {len(errors)}")
    
    if errors:
        print("  - Error details:")
        for err in errors[:5]:
            print(f"    - {err}")
    
    # ========== AFTER STATE ==========
    print("\n[4/5] Capturing AFTER state...")
    
    steps_count = await db.timeline_steps.count_documents({})
    migrated_steps = await db.timeline_steps.find(
        {"migrated_from_stage": True},
        {"_id": 0}
    ).limit(3).to_list(3)
    
    print(f"  - timeline_steps count: {steps_count}")
    print(f"  - Migrated steps: {await db.timeline_steps.count_documents({'migrated_from_stage': True})}")
    if migrated_steps:
        print(f"  - Sample migrated step: {json.dumps(migrated_steps[0], indent=2, default=str)}")
    
    # ========== VERIFICATION ==========
    print("\n[5/5] Verifying data integrity...")
    
    # Count comparison
    migrated_count = await db.timeline_steps.count_documents({"migrated_from_stage": True})
    
    print(f"  - Original stages: {stages_count}")
    print(f"  - Migrated steps: {migrated_count}")
    print(f"  - Skipped: {skipped}")
    print(f"  - Expected: {stages_count} = {migrated_count} + {skipped}")
    
    if stages_count == migrated_count + skipped:
        print("\n✅ MIGRATION VERIFIED: All stages accounted for")
    else:
        print(f"\n❌ MIGRATION MISMATCH: {stages_count} stages, but {migrated_count + skipped} accounted for")
    
    # Field preservation check
    print("\n  Field preservation check:")
    sample_stage = stages_sample[0] if stages_sample else None
    if sample_stage:
        sample_step = await db.timeline_steps.find_one(
            {"step_id": sample_stage['stage_id']},
            {"_id": 0}
        )
        if sample_step:
            checks = [
                ("name → title", sample_stage.get('name') == sample_step.get('title')),
                ("description", sample_stage.get('description') == sample_step.get('description')),
                ("order → order_index", sample_stage.get('order') == sample_step.get('order_index')),
                ("planned_start", sample_stage.get('planned_start') == sample_step.get('planned_start')),
                ("planned_end", sample_stage.get('planned_end') == sample_step.get('planned_end')),
                ("progress_percent", sample_stage.get('progress_percent') == sample_step.get('progress_percent')),
                ("notes", sample_stage.get('notes') == sample_step.get('notes')),
            ]
            for field, passed in checks:
                status = "✅" if passed else "❌"
                print(f"    {status} {field}")
    
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print("\nNOTE: project_stages collection NOT deleted yet.")
    print("Delete will happen in Phase 5 after full validation.")


if __name__ == "__main__":
    asyncio.run(run_migration())

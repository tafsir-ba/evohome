"""
Database Compatibility Layer

This module provides backward-compatible access to collections during
the data model normalization migration (Phases C-E).

TEMPORARY CODE - To be removed in Phase F after migration complete.

Rules:
- Reads: Try canonical collection first, fallback to deprecated
- Writes: Always to canonical collection only
- No new features, normalization only

Collections being migrated:
- project_units → units
- project_timelines → timelines
- project_stages → timeline_steps (merge)

Fields being normalized:
- project_timeline_id → timeline_id
"""

import logging
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("evohome.db_compat")

# Flag to track if we're in compatibility mode
COMPAT_MODE = False  # Phase E: data migrated, canonical reads only. Remove in Phase F.


class DatabaseCompat:
    """
    Compatibility layer for database operations during migration.
    
    Usage:
        compat = DatabaseCompat(db)
        units = await compat.get_units(project_id)
        timeline = await compat.get_timeline(project_id)
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._conflict_log = []
    
    # =========================================================================
    # UNITS COMPATIBILITY
    # =========================================================================
    
    async def get_units(self, project_id: str, **filters) -> List[Dict]:
        """
        Get units for a project with backward compatibility.
        
        Reads from:
        1. units (canonical) - primary
        2. project_units (deprecated) - fallback during migration
        """
        query = {"project_id": project_id, **filters}
        
        # Try canonical collection first
        units = await self.db.units.find(query, {"_id": 0}).to_list(500)
        
        if units:
            return units
        
        # Fallback to deprecated collection during migration
        if COMPAT_MODE:
            units = await self.db.project_units.find(query, {"_id": 0}).to_list(500)
            if units:
                self._log_conflict("get_units", "Data found in project_units, not units")
            return units
        
        return []
    
    async def get_unit(self, unit_id: str) -> Optional[Dict]:
        """Get single unit by ID."""
        # Try canonical first
        unit = await self.db.units.find_one({"unit_id": unit_id}, {"_id": 0})
        
        if unit:
            return unit
        
        # Fallback during migration
        if COMPAT_MODE:
            unit = await self.db.project_units.find_one({"unit_id": unit_id}, {"_id": 0})
            if unit:
                self._log_conflict("get_unit", f"Unit {unit_id} found in project_units")
            return unit
        
        return None
    
    async def create_unit(self, unit_doc: Dict) -> Dict:
        """
        Create unit - ALWAYS writes to canonical collection.
        """
        await self.db.units.insert_one(unit_doc)
        return await self.db.units.find_one({"unit_id": unit_doc["unit_id"]}, {"_id": 0})
    
    async def update_unit(self, unit_id: str, update_data: Dict) -> Optional[Dict]:
        """Update unit in canonical collection."""
        await self.db.units.update_one({"unit_id": unit_id}, {"$set": update_data})
        return await self.get_unit(unit_id)
    
    async def delete_unit(self, unit_id: str) -> bool:
        """Delete unit from canonical collection."""
        result = await self.db.units.delete_one({"unit_id": unit_id})
        
        # Also delete from deprecated if exists (cleanup)
        if COMPAT_MODE:
            await self.db.project_units.delete_one({"unit_id": unit_id})
        
        return result.deleted_count > 0
    
    async def count_units(self, project_id: str) -> int:
        """Count units for a project."""
        count = await self.db.units.count_documents({"project_id": project_id})
        
        if count == 0 and COMPAT_MODE:
            count = await self.db.project_units.count_documents({"project_id": project_id})
            if count > 0:
                self._log_conflict("count_units", f"Units for {project_id} in deprecated collection")
        
        return count
    
    # =========================================================================
    # TIMELINE COMPATIBILITY
    # =========================================================================
    
    async def get_timeline(self, project_id: str) -> Optional[Dict]:
        """
        Get timeline for a project with backward compatibility.
        
        Reads from:
        1. timelines (canonical) - primary
        2. project_timelines (deprecated) - fallback
        
        Also normalizes timeline_id field.
        """
        # Try canonical first
        timeline = await self.db.timelines.find_one({"project_id": project_id}, {"_id": 0})
        
        if timeline:
            return self._normalize_timeline_id(timeline)
        
        # Fallback during migration
        if COMPAT_MODE:
            timeline = await self.db.project_timelines.find_one({"project_id": project_id}, {"_id": 0})
            if timeline:
                self._log_conflict("get_timeline", f"Timeline for {project_id} in project_timelines")
                return self._normalize_timeline_id(timeline)
        
        return None
    
    async def get_timeline_by_id(self, timeline_id: str) -> Optional[Dict]:
        """Get timeline by ID (handles both field names)."""
        # Try canonical collection with canonical field
        timeline = await self.db.timelines.find_one({"timeline_id": timeline_id}, {"_id": 0})
        
        if not timeline and COMPAT_MODE:
            # Try with deprecated field name
            timeline = await self.db.timelines.find_one({"project_timeline_id": timeline_id}, {"_id": 0})
            
            if not timeline:
                # Try deprecated collection
                timeline = await self.db.project_timelines.find_one(
                    {"$or": [{"timeline_id": timeline_id}, {"project_timeline_id": timeline_id}]},
                    {"_id": 0}
                )
                if timeline:
                    self._log_conflict("get_timeline_by_id", f"Timeline {timeline_id} in deprecated collection")
        
        return self._normalize_timeline_id(timeline) if timeline else None
    
    async def create_timeline(self, timeline_doc: Dict) -> Dict:
        """
        Create timeline - ALWAYS writes to canonical collection with canonical field.
        """
        # Ensure we use timeline_id, not project_timeline_id
        if "project_timeline_id" in timeline_doc and "timeline_id" not in timeline_doc:
            timeline_doc["timeline_id"] = timeline_doc.pop("project_timeline_id")
        
        await self.db.timelines.insert_one(timeline_doc)
        return await self.db.timelines.find_one({"timeline_id": timeline_doc["timeline_id"]}, {"_id": 0})
    
    async def update_timeline(self, timeline_id: str, update_data: Dict) -> Optional[Dict]:
        """Update timeline. Phase E: canonical collection only."""
        await self.db.timelines.update_one(
            {"timeline_id": timeline_id},
            {"$set": update_data}
        )
        return await self.get_timeline_by_id(timeline_id)
    
    async def find_timeline_one(self, query: Dict, projection: Dict = None) -> Optional[Dict]:
        """
        Flexible find_one for timelines with dual-collection fallback.
        Use when specific helper methods don't cover the query pattern.
        """
        if projection is None:
            projection = {"_id": 0}
        elif "_id" not in projection:
            projection = {**projection, "_id": 0}
        
        result = await self.db.timelines.find_one(query, projection)
        if result:
            return self._normalize_timeline_id(result)
        
        if COMPAT_MODE:
            result = await self.db.project_timelines.find_one(query, projection)
            if result:
                self._log_conflict("find_timeline_one", f"Found in project_timelines")
                return self._normalize_timeline_id(result)
        
        return None
    
    async def find_timeline_many(self, query: Dict, projection: Dict = None, limit: int = 100) -> List[Dict]:
        """Flexible find for timelines with dual-collection fallback."""
        if projection is None:
            projection = {"_id": 0}
        elif "_id" not in projection:
            projection = {**projection, "_id": 0}
        
        results = await self.db.timelines.find(query, projection).to_list(limit)
        
        if not results and COMPAT_MODE:
            results = await self.db.project_timelines.find(query, projection).to_list(limit)
            if results:
                self._log_conflict("find_timeline_many", f"Found {len(results)} in project_timelines")
        
        return [self._normalize_timeline_id(t) for t in results]
    
    async def insert_timeline(self, doc: Dict) -> None:
        """Insert timeline into canonical collection only. Normalizes field names."""
        if "project_timeline_id" in doc and "timeline_id" not in doc:
            doc["timeline_id"] = doc["project_timeline_id"]
        await self.db.timelines.insert_one(doc)
    
    async def delete_timeline_one(self, query: Dict) -> bool:
        """Delete single timeline from canonical + deprecated during compat."""
        result = await self.db.timelines.delete_one(query)
        deleted = result.deleted_count > 0
        if COMPAT_MODE:
            dep_result = await self.db.project_timelines.delete_one(query)
            deleted = deleted or dep_result.deleted_count > 0
        return deleted
    
    async def delete_timelines_many(self, query: Dict) -> int:
        """Delete many timelines from canonical + deprecated during compat."""
        result = await self.db.timelines.delete_many(query)
        count = result.deleted_count
        if COMPAT_MODE:
            dep_result = await self.db.project_timelines.delete_many(query)
            count += dep_result.deleted_count
        return count
    
    # =========================================================================
    # TIMELINE REFERENCE HELPERS (for timeline_steps FK field)
    # =========================================================================
    
    @staticmethod
    def timeline_ref_query(timeline_id: str) -> Dict:
        """
        Query helper for finding timeline_steps by timeline reference.
        Phase E: canonical field only. Remove $or fallback in Phase F cleanup.
        """
        return {"timeline_id": timeline_id}
    
    @staticmethod
    def timeline_ref_fields(timeline_id: str) -> Dict:
        """
        Write helper for timeline reference fields in step documents.
        Phase E: writes canonical only. Drop deprecated in Phase F.
        """
        return {"timeline_id": timeline_id}
    
    @staticmethod
    def get_step_timeline_ref(step: Dict) -> str:
        """
        Get timeline reference from a step document.
        Phase E: canonical field, with safe fallback.
        """
        return step.get('timeline_id') or step.get('project_timeline_id', '')
    
    # =========================================================================
    # TIMELINE STEPS COMPATIBILITY
    # =========================================================================
    
    async def get_steps(self, timeline_id: str, **filters) -> List[Dict]:
        """Get steps for a timeline. Phase E: canonical field only."""
        query = {"timeline_id": timeline_id, **filters}
        steps = await self.db.timeline_steps.find(query, {"_id": 0}).to_list(500)
        return [self._normalize_step(step) for step in steps]
    
    async def get_steps_by_project(self, project_id: str, **filters) -> List[Dict]:
        """Get steps by project_id (denormalized field)."""
        query = {"project_id": project_id, **filters}
        steps = await self.db.timeline_steps.find(query, {"_id": 0}).to_list(500)
        return [self._normalize_step(step) for step in steps]
    
    async def get_step(self, step_id: str) -> Optional[Dict]:
        """Get single step by ID."""
        step = await self.db.timeline_steps.find_one({"step_id": step_id}, {"_id": 0})
        return self._normalize_step(step) if step else None
    
    async def create_step(self, step_doc: Dict) -> Dict:
        """
        Create step - normalizes field names before insert.
        """
        # Ensure canonical field names
        if "project_timeline_id" in step_doc and "timeline_id" not in step_doc:
            step_doc["timeline_id"] = step_doc.pop("project_timeline_id")
        
        await self.db.timeline_steps.insert_one(step_doc)
        return await self.db.timeline_steps.find_one({"step_id": step_doc["step_id"]}, {"_id": 0})
    
    async def update_step(self, step_id: str, update_data: Dict) -> Optional[Dict]:
        """Update step."""
        await self.db.timeline_steps.update_one({"step_id": step_id}, {"$set": update_data})
        return await self.get_step(step_id)
    
    async def delete_step(self, step_id: str) -> bool:
        """Delete step."""
        result = await self.db.timeline_steps.delete_one({"step_id": step_id})
        return result.deleted_count > 0
    
    # =========================================================================
    # NORMALIZATION HELPERS
    # =========================================================================
    
    def _normalize_timeline_id(self, timeline: Optional[Dict]) -> Optional[Dict]:
        """
        Normalize timeline to use timeline_id field.
        
        CONFLICT FLAG: Logs if document has project_timeline_id but not timeline_id.
        """
        if not timeline:
            return None
        
        if "project_timeline_id" in timeline:
            if "timeline_id" not in timeline:
                self._log_conflict(
                    "_normalize_timeline_id",
                    f"Document has project_timeline_id but not timeline_id: {timeline.get('project_timeline_id')}"
                )
                timeline["timeline_id"] = timeline["project_timeline_id"]
            # Keep both during migration for backward compat
            # del timeline["project_timeline_id"]  # Remove in Phase F
        
        return timeline
    
    def _normalize_step(self, step: Optional[Dict]) -> Optional[Dict]:
        """
        Normalize step to use timeline_id field.
        """
        if not step:
            return None
        
        if "project_timeline_id" in step:
            if "timeline_id" not in step:
                self._log_conflict(
                    "_normalize_step",
                    f"Step has project_timeline_id but not timeline_id: {step.get('step_id')}"
                )
                step["timeline_id"] = step["project_timeline_id"]
        
        return step
    
    # =========================================================================
    # CONFLICT LOGGING
    # =========================================================================
    
    def _log_conflict(self, operation: str, message: str):
        """
        Log a conflict between live code and canonical schema.
        
        RULE 2: Require conflict reporting
        """
        conflict = {
            "operation": operation,
            "message": message
        }
        self._conflict_log.append(conflict)
        logger.warning(f"SCHEMA CONFLICT [{operation}]: {message}")
    
    def get_conflicts(self) -> List[Dict]:
        """Get all logged conflicts."""
        return self._conflict_log
    
    def clear_conflicts(self):
        """Clear conflict log."""
        self._conflict_log = []


# Singleton instance - initialized when db is available
_compat: Optional[DatabaseCompat] = None


def init_compat(db: AsyncIOMotorDatabase) -> DatabaseCompat:
    """Initialize compatibility layer with database."""
    global _compat
    _compat = DatabaseCompat(db)
    logger.info(f"Database compatibility layer initialized (COMPAT_MODE={COMPAT_MODE})")
    return _compat


def get_compat() -> DatabaseCompat:
    """Get compatibility layer instance."""
    if _compat is None:
        raise RuntimeError("Compatibility layer not initialized. Call init_compat(db) first.")
    return _compat

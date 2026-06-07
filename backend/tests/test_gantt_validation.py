"""
Gantt validation — unit tests (no DB, no API).
"""
import importlib.util
import sys
import types
from pathlib import Path

import pytest

_services_dir = Path(__file__).resolve().parents[1] / "services"

# Stub services package so gantt_validation can import gantt_constants
# without loading the full services/__init__.py dependency chain.
if "services" not in sys.modules:
    _services_pkg = types.ModuleType("services")
    _services_pkg.__path__ = [str(_services_dir)]
    sys.modules["services"] = _services_pkg

_constants_path = _services_dir / "gantt_constants.py"
_constants_spec = importlib.util.spec_from_file_location(
    "services.gantt_constants", _constants_path
)
_gantt_constants = importlib.util.module_from_spec(_constants_spec)
sys.modules["services.gantt_constants"] = _gantt_constants
_constants_spec.loader.exec_module(_gantt_constants)

_validation_path = _services_dir / "gantt_validation.py"
_spec = importlib.util.spec_from_file_location("gantt_validation", _validation_path)
_gantt_validation = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gantt_validation)

GanttValidationError = _gantt_validation.GanttValidationError
detect_dependency_cycle = _gantt_validation.detect_dependency_cycle
get_gantt_config = _gantt_validation.get_gantt_config
normalize_task_dates = _gantt_validation.normalize_task_dates
validate_dependencies = _gantt_validation.validate_dependencies
validate_reorder_task_ids = _gantt_validation.validate_reorder_task_ids
validate_task_payload = _gantt_validation.validate_task_payload
validate_draft_tasks = _gantt_validation.validate_draft_tasks


class TestDateValidation:
    def test_both_dates_null_allowed(self):
        start, end, duration = normalize_task_dates("task", None, None)
        assert start is None
        assert end is None
        assert duration is None

    def test_start_only_allowed(self):
        start, end, duration = normalize_task_dates("task", "2026-01-10", None)
        assert start == "2026-01-10"
        assert end is None
        assert duration is None

    def test_reject_end_only(self):
        with pytest.raises(GanttValidationError, match="end_date requires start_date"):
            normalize_task_dates("task", None, "2026-01-10")

    def test_reject_end_before_start(self):
        with pytest.raises(GanttValidationError, match="end_date must not be before start_date"):
            normalize_task_dates("task", "2026-01-10", "2026-01-05")

    def test_invalid_date_format(self):
        with pytest.raises(GanttValidationError, match="valid calendar date"):
            normalize_task_dates("task", "2026-02-30", None)

    def test_duration_computed_exclusive(self):
        _, _, duration = normalize_task_dates("task", "2026-01-01", "2026-01-03")
        assert duration == 2

    def test_duration_spec_example_march(self):
        _, _, duration = normalize_task_dates("task", "2025-03-01", "2025-03-15")
        assert duration == 14


class TestMilestoneValidation:
    def test_milestone_requires_start(self):
        with pytest.raises(GanttValidationError, match="Milestones require start_date"):
            normalize_task_dates("milestone", None, None)

    def test_milestone_normalizes_end_date(self):
        start, end, duration = normalize_task_dates("milestone", "2026-03-15", None)
        assert start == "2026-03-15"
        assert end == "2026-03-15"
        assert duration == 0

    def test_milestone_rejects_differing_dates(self):
        with pytest.raises(GanttValidationError, match="must match"):
            normalize_task_dates("milestone", "2026-03-15", "2026-03-16")


class TestDependencyValidation:
    def test_reject_self_dependency(self):
        with pytest.raises(GanttValidationError, match="cannot depend on itself"):
            validate_dependencies(
                [{"task_id": "gt_abc", "type": "finish_to_start"}],
                "gt_abc",
                {"gt_abc"},
            )

    def test_reject_missing_dependency(self):
        with pytest.raises(GanttValidationError, match="not found in project"):
            validate_dependencies(
                [{"task_id": "gt_missing", "type": "finish_to_start"}],
                "gt_abc",
                {"gt_abc"},
            )

    def test_reject_unsupported_dependency_type(self):
        with pytest.raises(GanttValidationError, match="Unsupported dependency type"):
            validate_dependencies(
                [{"task_id": "gt_b", "type": "SS"}],
                "gt_a",
                {"gt_a", "gt_b"},
            )

    def test_detect_cycle(self):
        tasks = [
            {"task_id": "gt_a", "dependencies": [{"task_id": "gt_b", "type": "finish_to_start"}]},
            {"task_id": "gt_b", "dependencies": [{"task_id": "gt_c", "type": "finish_to_start"}]},
            {"task_id": "gt_c", "dependencies": []},
        ]
        with pytest.raises(GanttValidationError, match="Circular dependency"):
            detect_dependency_cycle(
                tasks,
                "gt_c",
                [{"task_id": "gt_a", "type": "finish_to_start"}],
            )


class TestGanttConfig:
    def test_config_matches_validation_constants(self):
        config = get_gantt_config()
        assert config["app_name"] == "Caribbean Regional Connectivity"
        assert config["requires_auth"] is True
        assert config["task_statuses"] == sorted(_gantt_validation.VALID_STATUSES)
        assert config["task_types"] == list(_gantt_validation.VALID_TASK_TYPES)
        assert config["dependency_types"] == ["finish_to_start"]
        assert ".csv" in config["import"]["allowed_extensions"]
        assert config["import"]["max_size_mb"] == 15
        assert "review all dates" in config["import"]["review_message"].lower()
        assert config["import"]["extraction_model"] == "gpt-5.4"


class TestTaskPayloadValidation:
    def test_clear_dates_allowed_on_update(self):
        result = validate_task_payload(
            {
                "title": "Task A",
                "start_date": None,
                "end_date": None,
            },
            task_id="gt_a",
            task_type="task",
            project_task_ids={"gt_a"},
            existing_tasks=[{"task_id": "gt_a", "dependencies": []}],
            is_create=False,
        )
        assert result["start_date"] is None
        assert result["end_date"] is None
        assert result["duration_days"] is None

    def test_reject_duration_mismatch(self):
        with pytest.raises(GanttValidationError, match="duration_days mismatch"):
            validate_task_payload(
                {
                    "title": "Task A",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-05",
                    "duration_days": 99,
                },
                task_id="gt_new",
                task_type="task",
                project_task_ids=set(),
                existing_tasks=[],
                is_create=True,
            )


class TestReorderValidation:
    def test_reject_duplicate_task_ids(self):
        existing = [{"task_id": "gt_a"}, {"task_id": "gt_b"}]
        with pytest.raises(GanttValidationError, match="must not contain duplicates"):
            validate_reorder_task_ids(["gt_a", "gt_a"], existing)

    def test_reject_wrong_length(self):
        existing = [{"task_id": "gt_a"}, {"task_id": "gt_b"}]
        with pytest.raises(GanttValidationError, match="full permutation"):
            validate_reorder_task_ids(["gt_a"], existing)

    def test_reject_unknown_task_id(self):
        existing = [{"task_id": "gt_a"}]
        with pytest.raises(GanttValidationError, match="full permutation"):
            validate_reorder_task_ids(["gt_fake"], existing)


class TestDraftValidation:
    def test_draft_cycle_rejected(self):
        draft_tasks = [
            {
                "temp_id": "t1",
                "title": "A",
                "dependencies": [{"temp_task_id": "t2", "type": "finish_to_start"}],
            },
            {
                "temp_id": "t2",
                "title": "B",
                "dependencies": [{"temp_task_id": "t1", "type": "finish_to_start"}],
            },
        ]
        with pytest.raises(GanttValidationError, match="Circular dependency"):
            validate_draft_tasks(draft_tasks)

    def test_draft_missing_dependency_rejected(self):
        with pytest.raises(GanttValidationError, match="not found in draft"):
            validate_draft_tasks([
                {
                    "temp_id": "t1",
                    "title": "A",
                    "dependencies": [{"temp_task_id": "t99", "type": "finish_to_start"}],
                },
            ])

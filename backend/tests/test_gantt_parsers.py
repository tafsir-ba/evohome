"""Unit tests for Gantt AI response parsing."""
import importlib.util
import sys
import types
from pathlib import Path

_services_dir = Path(__file__).resolve().parents[1] / "services"

if "services" not in sys.modules:
    _services_pkg = types.ModuleType("services")
    _services_pkg.__path__ = [str(_services_dir)]
    sys.modules["services"] = _services_pkg

# Stub heavy optional imports before loading gantt_parsers.
sys.modules.setdefault("fitz", types.ModuleType("fitz"))
_ai_service = types.ModuleType("services.ai_service")
_ai_service.OPENAI_API_KEY = ""
sys.modules["services.ai_service"] = _ai_service

_constants_path = _services_dir / "gantt_constants.py"
_constants_spec = importlib.util.spec_from_file_location(
    "services.gantt_constants", _constants_path
)
_gantt_constants = importlib.util.module_from_spec(_constants_spec)
sys.modules["services.gantt_constants"] = _gantt_constants
_constants_spec.loader.exec_module(_gantt_constants)

_parsers_path = _services_dir / "gantt_parsers.py"
_parsers_spec = importlib.util.spec_from_file_location("gantt_parsers_under_test", _parsers_path)
_gantt_parsers = importlib.util.module_from_spec(_parsers_spec)
_parsers_spec.loader.exec_module(_gantt_parsers)

_parse_ai_json_response = _gantt_parsers._parse_ai_json_response
_load_json_payload = _gantt_parsers._load_json_payload
_strip_markdown_fences = _gantt_parsers._strip_markdown_fences


class TestGanttAiJsonParsing:
    def test_parses_plain_json_object(self):
        raw = '{"tasks": [{"temp_id": "t1", "title": "Kickoff"}], "warnings": []}'
        tasks, warnings = _parse_ai_json_response(raw)
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Kickoff"
        assert warnings == []

    def test_parses_markdown_fenced_json(self):
        raw = """```json
{"tasks": [{"temp_id": "t1", "title": "Design"}], "warnings": ["check dates"]}
```"""
        tasks, warnings = _parse_ai_json_response(raw)
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Design"
        assert "check dates" in warnings

    def test_parses_json_with_leading_prose(self):
        raw = 'Here is the schedule:\n{"tasks": [{"title": "Build"}], "warnings": []}'
        tasks, warnings = _parse_ai_json_response(raw)
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Build"

    def test_returns_error_for_invalid_json(self):
        tasks, warnings = _parse_ai_json_response("not json at all")
        assert tasks == []
        assert "could not be parsed" in warnings[0].lower()

    def test_strip_markdown_fences(self):
        assert _strip_markdown_fences('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_load_json_payload_accepts_task_array(self):
        payload = _load_json_payload('[{"title": "Only task"}]')
        tasks, _warnings = _parse_ai_json_response('[{"title": "Only task"}]')
        assert payload is not None
        assert len(tasks) == 1

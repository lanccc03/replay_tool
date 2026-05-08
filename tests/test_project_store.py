from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

import tests.bootstrap  # noqa: F401

from replay_tool.app import ReplayApplication
from replay_tool.domain import ReplayScenario
from replay_tool.storage import SqliteProjectStore


ROOT = Path(__file__).resolve().parents[1]


def _scenario_payload(name: str = "demo", trace_path: str = "sample.asc") -> dict:
    return {
        "schema_version": 2,
        "name": name,
        "traces": [{"id": "trace1", "path": trace_path}],
        "devices": [{"id": "mock0", "driver": "mock"}],
        "sources": [{"id": "source0", "trace": "trace1", "channel": 0, "bus": "CANFD"}],
        "targets": [
            {
                "id": "target0",
                "device": "mock0",
                "physical_channel": 0,
                "bus": "CANFD",
            }
        ],
        "routes": [{"logical_channel": 0, "source": "source0", "target": "target0"}],
        "timeline": {"loop": False},
    }


class ProjectStoreTests(unittest.TestCase):
    def test_save_list_get_and_delete_generated_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteProjectStore(Path(tmp) / "library")
            scenario = ReplayScenario.from_dict(_scenario_payload())

            saved = store.save_scenario(scenario, base_dir=str(Path(tmp) / "scenarios"))
            listed = store.list_scenarios()
            loaded = store.get_scenario(saved.scenario_id)
            deleted = store.delete_scenario(saved.scenario_id)

        self.assertTrue(saved.scenario_id)
        self.assertEqual([saved.scenario_id], [item.scenario_id for item in listed])
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual("demo", loaded.body["name"])
        self.assertEqual(saved.scenario_id, deleted.scenario_id)

    def test_save_updates_existing_id_and_preserves_created_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteProjectStore(Path(tmp) / "library")
            first = ReplayScenario.from_dict(_scenario_payload("first"))
            second = ReplayScenario.from_dict(_scenario_payload("second"))

            saved = store.save_scenario(first, scenario_id="scenario-1", base_dir=tmp)
            updated = store.save_scenario(second, scenario_id="scenario-1", base_dir=tmp)
            listed = store.list_scenarios()

        self.assertEqual("scenario-1", updated.scenario_id)
        self.assertEqual(saved.created_at, updated.created_at)
        self.assertEqual("second", updated.name)
        self.assertEqual("second", updated.body["name"])
        self.assertEqual(1, len(listed))

    def test_base_dir_persistence_and_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / "scenario-root"
            store = SqliteProjectStore(Path(tmp) / "library")
            scenario = ReplayScenario.from_dict(_scenario_payload())

            saved = store.save_scenario(scenario, scenario_id="roundtrip", base_dir=str(base_dir))
            round_tripped = ReplayScenario.from_dict(saved.body)

        self.assertEqual(str(base_dir.resolve()), saved.base_dir)
        self.assertEqual(scenario, round_tripped)
        self.assertEqual(1, saved.trace_count)
        self.assertEqual(1, saved.route_count)

    def test_delete_unknown_scenario_raises_key_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteProjectStore(Path(tmp) / "library")

            with self.assertRaises(KeyError):
                store.delete_scenario("missing")


class ProjectStoreApplicationTests(unittest.TestCase):
    def test_application_compiles_and_runs_saved_scenario_by_id_with_base_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenario_dir = Path(tmp) / "scenario"
            scenario_dir.mkdir()
            shutil.copy2(ROOT / "examples" / "sample.asc", scenario_dir / "sample.asc")
            scenario_path = scenario_dir / "scenario.json"
            scenario_path.write_text(json.dumps(_scenario_payload("saved-by-id")), encoding="utf-8")
            app = ReplayApplication(workspace=Path(tmp) / "library")

            record = app.save_scenario(scenario_path, scenario_id="saved-mock")
            plan = app.compile_plan(record.scenario_id)
            runtime = app.run(record.scenario_id)

        self.assertEqual("saved-by-id", plan.name)
        self.assertEqual(1, plan.timeline_size)
        snapshot = runtime.snapshot()
        self.assertEqual(1, snapshot.sent_frames)
        self.assertEqual(0, snapshot.skipped_frames)

    def test_application_compiles_saved_scenario_referencing_imported_trace_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = ReplayApplication(workspace=Path(tmp) / "library")
            trace = app.import_trace(ROOT / "examples" / "sample.asc")
            payload = _scenario_payload("imported-trace-id", trace.trace_id)
            scenario_path = Path(tmp) / "scenario.json"
            scenario_path.write_text(json.dumps(payload), encoding="utf-8")

            record = app.save_scenario(scenario_path, scenario_id="saved-imported")
            plan = app.compile_plan(record.scenario_id)
            deleted = app.delete_scenario(record.scenario_id)
            remaining_trace = app.inspect_trace(trace.trace_id)

        self.assertEqual("imported-trace-id", plan.name)
        self.assertEqual(trace.trace_id, plan.frame_sources[0].library_trace_id)
        self.assertEqual("saved-imported", deleted.scenario_id)
        self.assertEqual(trace.trace_id, remaining_trace.record.trace_id)

    def test_compile_plan_prefers_existing_path_over_saved_scenario_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenario_path = Path(tmp) / "scenario.json"
            shutil.copy2(ROOT / "examples" / "sample.asc", Path(tmp) / "sample.asc")
            scenario_path.write_text(json.dumps(_scenario_payload("file-wins")), encoding="utf-8")
            app = ReplayApplication(workspace=Path(tmp) / "library")
            saved_payload = _scenario_payload("saved-id-loses")
            saved_path = Path(tmp) / "saved.json"
            saved_path.write_text(json.dumps(saved_payload), encoding="utf-8")
            app.save_scenario(saved_path, scenario_id=str(scenario_path))

            plan = app.compile_plan(str(scenario_path))

        self.assertEqual("file-wins", plan.name)

    def test_application_saves_validates_and_deletes_scenario_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenario_dir = Path(tmp) / "scenario"
            scenario_dir.mkdir()
            shutil.copy2(ROOT / "examples" / "sample.asc", scenario_dir / "sample.asc")
            app = ReplayApplication(workspace=Path(tmp) / "library")
            payload = _scenario_payload("body-workflow")

            saved = app.save_scenario_body(payload, scenario_id="body-scenario", base_dir=scenario_dir)
            loaded = app.get_scenario(saved.scenario_id)
            plan = app.validate_scenario_body(loaded.body, base_dir=loaded.base_dir)
            deleted = app.delete_scenario(saved.scenario_id)

        self.assertEqual("body-scenario", saved.scenario_id)
        self.assertEqual("body-workflow", loaded.name)
        self.assertEqual("body-workflow", plan.name)
        self.assertEqual(1, plan.timeline_size)
        self.assertEqual("body-scenario", deleted.scenario_id)


if __name__ == "__main__":
    unittest.main()

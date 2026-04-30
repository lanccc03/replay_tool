from __future__ import annotations

import copy
from pathlib import Path
import unittest

import tests.bootstrap  # noqa: F401

from replay_tool.app import ReplayApplication
from replay_tool.domain import BusType, ReplayScenario
from replay_tool.storage import AscTraceReader


ROOT = Path(__file__).resolve().parents[1]


def _minimal_v2_payload() -> dict:
    return {
        "schema_version": 2,
        "name": "demo",
        "traces": [{"id": "trace1", "path": "sample.asc"}],
        "devices": [{"id": "mock0", "driver": "mock"}],
        "sources": [{"id": "source0", "trace": "trace1", "channel": 0, "bus": "CANFD"}],
        "targets": [
            {
                "id": "target0",
                "device": "mock0",
                "physical_channel": 1,
                "bus": "CANFD",
            }
        ],
        "routes": [{"logical_channel": 0, "source": "source0", "target": "target0"}],
        "timeline": {"loop": False},
    }


class ScenarioAndPlannerTests(unittest.TestCase):
    def test_scenario_json_parses_v2_minimum_shape(self) -> None:
        payload = _minimal_v2_payload()

        scenario = ReplayScenario.from_dict(payload)

        self.assertEqual("demo", scenario.name)
        self.assertEqual(BusType.CANFD, scenario.sources[0].bus)
        self.assertEqual(BusType.CANFD, scenario.targets[0].config.bus)
        self.assertEqual(500000, scenario.targets[0].config.nominal_baud)
        self.assertEqual("source0", scenario.routes[0].source_id)

    def test_scenario_json_rejects_v1_shape(self) -> None:
        payload = {
            "schema_version": 1,
            "name": "demo",
            "traces": [{"id": "trace1", "path": "sample.asc"}],
            "devices": [{"id": "mock0", "driver": "mock"}],
            "channels": [
                {
                    "logical_channel": 0,
                    "trace_id": "trace1",
                    "source_channel": 0,
                    "device_id": "mock0",
                    "physical_channel": 1,
                    "bus": "CANFD",
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "schema_version=2"):
            ReplayScenario.from_dict(payload)

    def test_scenario_json_rejects_unknown_references(self) -> None:
        cases = {
            "unknown trace": ("sources", 0, "trace", "missing"),
            "unknown device": ("targets", 0, "device", "missing"),
            "unknown source": ("routes", 0, "source", "missing"),
            "unknown target": ("routes", 0, "target", "missing"),
        }
        for label, (collection, index, key, value) in cases.items():
            with self.subTest(label=label):
                payload = copy.deepcopy(_minimal_v2_payload())
                payload[collection][index][key] = value

                with self.assertRaises(ValueError):
                    ReplayScenario.from_dict(payload)

    def test_scenario_json_rejects_duplicate_ids_and_logical_channels(self) -> None:
        payload = _minimal_v2_payload()
        payload["targets"][0]["id"] = "source0"

        with self.assertRaisesRegex(ValueError, "scenario resource IDs"):
            ReplayScenario.from_dict(payload)

        payload = _minimal_v2_payload()
        payload["routes"].append({"logical_channel": 0, "source": "source0", "target": "target0"})

        with self.assertRaisesRegex(ValueError, "logical channels"):
            ReplayScenario.from_dict(payload)

    def test_scenario_json_rejects_source_target_bus_mismatch(self) -> None:
        payload = _minimal_v2_payload()
        payload["targets"][0]["bus"] = "CAN"

        with self.assertRaisesRegex(ValueError, "CANFD source to CAN target"):
            ReplayScenario.from_dict(payload)

    def test_scenario_json_rejects_unsupported_timeline_items(self) -> None:
        payload = _minimal_v2_payload()
        payload["timeline"]["link_actions"] = [{"ts_ns": 0, "action": "DISCONNECT"}]

        with self.assertRaisesRegex(ValueError, "link_actions"):
            ReplayScenario.from_dict(payload)

    def test_asc_reader_parses_can_and_canfd(self) -> None:
        events = AscTraceReader().read(str(ROOT / "examples" / "sample.asc"))

        self.assertEqual([BusType.CANFD, BusType.CAN], [item.bus for item in events])
        self.assertEqual(0x18DAF110, events[0].message_id)
        self.assertTrue(events[0].extended)
        self.assertTrue(events[0].brs)
        self.assertEqual(0xC, events[0].dlc)
        self.assertEqual(24, len(events[0].payload))
        self.assertEqual(0x123, events[1].message_id)

    def test_planner_maps_trace_source_to_logical_channel(self) -> None:
        app = ReplayApplication()
        plan = app.compile_plan(ROOT / "examples" / "mock_canfd.json")

        self.assertEqual("mock-canfd-demo", plan.name)
        self.assertEqual(1, len(plan.frames))
        self.assertEqual(0, plan.frames[0].channel)
        self.assertEqual("mock0", plan.channels[0].device_id)
        self.assertEqual(0, plan.channels[0].physical_channel)
        self.assertEqual(BusType.CANFD, plan.channels[0].config.bus)

    def test_four_channel_tongxing_example_maps_all_sources(self) -> None:
        app = ReplayApplication()
        plan = app.compile_plan(ROOT / "examples" / "tongxing_tc1014_four_channel_canfd.json")

        self.assertEqual("tongxing-tc1014-four-channel-canfd-smoke", plan.name)
        self.assertEqual([0, 1, 2, 3], [frame.channel for frame in plan.frames])
        self.assertEqual([0x18DAF110, 0x18DAF111, 0x18DAF112, 0x18DAF113], [frame.message_id for frame in plan.frames])
        self.assertEqual([0, 1, 2, 3], [channel.physical_channel for channel in plan.channels])
        self.assertTrue(all(frame.brs for frame in plan.frames))


if __name__ == "__main__":
    unittest.main()

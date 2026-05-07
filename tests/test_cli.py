from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import tests.bootstrap  # noqa: F401

from replay_tool.cli import main


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def _run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_validate_and_run_output_stays_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "library"
            scenario = ROOT / "examples" / "mock_canfd.json"

            validate_code, validate_out, validate_err = self._run_cli(
                "validate",
                "--workspace",
                str(workspace),
                str(scenario),
            )
            run_code, run_out, run_err = self._run_cli(
                "run",
                "--workspace",
                str(workspace),
                str(scenario),
            )

        self.assertEqual(0, validate_code, validate_err)
        self.assertIn("OK: mock-canfd-demo", validate_out)
        self.assertEqual("", validate_err)
        self.assertEqual(0, run_code, run_err)
        self.assertIn("DONE: state=STOPPED sent=1 skipped=0 errors=0", run_out)
        self.assertEqual("", run_err)
        self.assertNotIn("\n1\n", run_out)
        self.assertNotIn("\n2\n", run_out)

    def test_import_list_inspect_and_run_imported_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "library"
            code, out, err = self._run_cli(
                "import",
                "--workspace",
                str(workspace),
                str(ROOT / "examples" / "sample.asc"),
            )
            self.assertEqual(0, code, err)
            self.assertEqual("", err)
            self.assertIn(".frames.bin", out)
            trace_id = out.split("id=", 1)[1].split(" ", 1)[0]

            list_code, list_out, list_err = self._run_cli("traces", "--workspace", str(workspace))
            inspect_code, inspect_out, inspect_err = self._run_cli(
                "inspect",
                "--workspace",
                str(workspace),
                trace_id,
            )

            scenario_path = Path(tmp) / "imported_scenario.json"
            scenario_payload = json.loads((ROOT / "examples" / "mock_canfd.json").read_text(encoding="utf-8"))
            scenario_payload["traces"][0]["path"] = trace_id
            scenario_path.write_text(json.dumps(scenario_payload), encoding="utf-8")
            run_code, run_out, run_err = self._run_cli(
                "run",
                "--workspace",
                str(workspace),
                str(scenario_path),
            )
            rebuild_code, rebuild_out, rebuild_err = self._run_cli(
                "rebuild-cache",
                "--workspace",
                str(workspace),
                trace_id,
            )
            delete_code, delete_out, delete_err = self._run_cli(
                "delete-trace",
                "--workspace",
                str(workspace),
                trace_id,
            )
            empty_list_code, empty_list_out, empty_list_err = self._run_cli("traces", "--workspace", str(workspace))

        self.assertEqual(0, list_code, list_err)
        self.assertIn(trace_id, list_out)
        self.assertEqual(0, inspect_code, inspect_err)
        self.assertIn("SOURCES:", inspect_out)
        self.assertIn("CH0 CANFD frames=1", inspect_out)
        self.assertIn("0x18DAF110", inspect_out)
        self.assertEqual(0, run_code, run_err)
        self.assertIn("DONE: state=STOPPED sent=1 skipped=0 errors=0", run_out)
        self.assertEqual(0, rebuild_code, rebuild_err)
        self.assertIn("REBUILT:", rebuild_out)
        self.assertIn(".frames.bin", rebuild_out)
        self.assertEqual(0, delete_code, delete_err)
        self.assertIn("DELETED:", delete_out)
        self.assertIn("library_file=True", delete_out)
        self.assertIn("cache_file=True", delete_out)
        self.assertEqual(0, empty_list_code, empty_list_err)
        self.assertEqual("No traces.\n", empty_list_out)

    def test_save_list_show_run_and_delete_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "library"
            scenario = ROOT / "examples" / "mock_canfd.json"

            save_code, save_out, save_err = self._run_cli(
                "save-scenario",
                "--workspace",
                str(workspace),
                "--id",
                "saved-mock",
                str(scenario),
            )
            list_code, list_out, list_err = self._run_cli("scenarios", "--workspace", str(workspace))
            show_code, show_out, show_err = self._run_cli(
                "show-scenario",
                "--workspace",
                str(workspace),
                "saved-mock",
            )
            run_code, run_out, run_err = self._run_cli("run", "--workspace", str(workspace), "saved-mock")
            delete_code, delete_out, delete_err = self._run_cli(
                "delete-scenario",
                "--workspace",
                str(workspace),
                "saved-mock",
            )
            empty_code, empty_out, empty_err = self._run_cli("scenarios", "--workspace", str(workspace))

        self.assertEqual(0, save_code, save_err)
        self.assertIn("SAVED: id=saved-mock name=mock-canfd-demo traces=1 routes=1", save_out)
        self.assertEqual(0, list_code, list_err)
        self.assertIn("saved-mock mock-canfd-demo traces=1 routes=1 updated_at=", list_out)
        self.assertEqual(0, show_code, show_err)
        self.assertEqual("mock-canfd-demo", json.loads(show_out)["name"])
        self.assertEqual(0, run_code, run_err)
        self.assertIn("DONE: state=STOPPED sent=1 skipped=0 errors=0", run_out)
        self.assertEqual(0, delete_code, delete_err)
        self.assertIn("DELETED: id=saved-mock name=mock-canfd-demo", delete_out)
        self.assertEqual(0, empty_code, empty_err)
        self.assertEqual("No scenarios.\n", empty_out)


if __name__ == "__main__":
    unittest.main()

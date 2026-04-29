from __future__ import annotations

import argparse
from pathlib import Path
import sys

from replay_tool.app import ReplayApplication
from replay_tool.domain import DeviceConfig


def main(argv: list[str] | None = None) -> int:
    """Run the replay-tool command-line interface.

    Args:
        argv: Optional argument list. When None, argparse reads from sys.argv.

    Returns:
        Process-style exit code: 0 for success, nonzero for errors.
    """
    parser = argparse.ArgumentParser(prog="replay-tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    workspace_parent = argparse.ArgumentParser(add_help=False)
    workspace_parent.add_argument("--workspace", default=".replay_tool", help="Trace library workspace directory.")

    validate_parser = subparsers.add_parser("validate", parents=[workspace_parent], help="Validate and compile a scenario.")
    validate_parser.add_argument("scenario")

    run_parser = subparsers.add_parser("run", parents=[workspace_parent], help="Run a scenario.")
    run_parser.add_argument("scenario")

    import_parser = subparsers.add_parser("import", parents=[workspace_parent], help="Import a trace into the library.")
    import_parser.add_argument("trace")

    traces_parser = subparsers.add_parser("traces", parents=[workspace_parent], help="List imported traces.")

    inspect_parser = subparsers.add_parser("inspect", parents=[workspace_parent], help="Inspect an imported trace.")
    inspect_parser.add_argument("trace_id")

    rebuild_parser = subparsers.add_parser("rebuild-cache", parents=[workspace_parent], help="Rebuild an imported trace cache.")
    rebuild_parser.add_argument("trace_id")

    delete_parser = subparsers.add_parser("delete-trace", parents=[workspace_parent], help="Delete an imported trace.")
    delete_parser.add_argument("trace_id")

    devices_parser = subparsers.add_parser("devices", parents=[workspace_parent], help="List device channels.")
    devices_parser.add_argument("--driver", default="tongxing")
    devices_parser.add_argument("--sdk-root", default="TSMaster/Windows")
    devices_parser.add_argument("--application", default="ReplayTool")
    devices_parser.add_argument("--device-type", default="TC1014")
    devices_parser.add_argument("--device-index", type=int, default=0)

    args = parser.parse_args(argv)
    app = ReplayApplication(logger=print, workspace=args.workspace)
    try:
        if args.command == "validate":
            plan = app.validate(args.scenario)
            print(f"OK: {plan.name} frames={len(plan.frames)} devices={len(plan.devices)} channels={len(plan.channels)}")
            return 0
        if args.command == "run":
            runtime = app.run(args.scenario)
            snapshot = runtime.snapshot()
            print(
                "DONE: state={state} sent={sent} skipped={skipped} errors={errors}".format(
                    state=snapshot.state.value,
                    sent=snapshot.sent_frames,
                    skipped=snapshot.skipped_frames,
                    errors=len(snapshot.errors),
                )
            )
            return 0 if not snapshot.errors else 2
        if args.command == "import":
            record = app.import_trace(args.trace)
            print(
                "IMPORTED: id={id} name={name} frames={frames} cache={cache}".format(
                    id=record.trace_id,
                    name=record.name,
                    frames=record.event_count,
                    cache=record.cache_path,
                )
            )
            return 0
        if args.command == "traces":
            records = app.list_traces()
            if not records:
                print("No traces.")
                return 0
            for record in records:
                print(
                    "{id} {name} frames={frames} start_ns={start} end_ns={end}".format(
                        id=record.trace_id,
                        name=record.name,
                        frames=record.event_count,
                        start=record.start_ns,
                        end=record.end_ns,
                    )
                )
            return 0
        if args.command == "inspect":
            inspection = app.inspect_trace(args.trace_id)
            record = inspection.record
            print(
                "TRACE: id={id} name={name} frames={frames} start_ns={start} end_ns={end}".format(
                    id=record.trace_id,
                    name=record.name,
                    frames=record.event_count,
                    start=record.start_ns,
                    end=record.end_ns,
                )
            )
            print("SOURCES:")
            for source in inspection.sources:
                print(f"  CH{source.source_channel} {source.bus.value} frames={source.frame_count}")
            print("MESSAGES:")
            for message in inspection.messages:
                ids = ",".join(f"0x{message_id:X}" for message_id in message.message_ids)
                print(f"  CH{message.source_channel} {message.bus.value} frames={message.frame_count} ids={ids}")
            return 0
        if args.command == "rebuild-cache":
            record = app.rebuild_trace_cache(args.trace_id)
            print(
                "REBUILT: id={id} name={name} frames={frames} cache={cache}".format(
                    id=record.trace_id,
                    name=record.name,
                    frames=record.event_count,
                    cache=record.cache_path,
                )
            )
            return 0
        if args.command == "delete-trace":
            result = app.delete_trace(args.trace_id)
            print(
                "DELETED: id={id} name={name} library_file={library} cache_file={cache}".format(
                    id=result.trace_id,
                    name=result.name,
                    library=result.deleted_library_file,
                    cache=result.deleted_cache_file,
                )
            )
            return 0
        if args.command == "devices":
            config = DeviceConfig(
                id="device0",
                driver=args.driver,
                application=args.application,
                sdk_root=str(Path(args.sdk_root)),
                device_type=args.device_type,
                device_index=args.device_index,
            )
            device = app.create_device(config)
            info = device.open()
            channels = device.enumerate_channels()
            print(f"{info.driver}:{info.name} serial={info.serial_number} channels={list(channels)}")
            device.close()
            return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

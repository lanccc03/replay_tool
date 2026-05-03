from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import uuid

from replay_tool.domain import BusType, Frame
from replay_tool.ports import DeleteTraceResult, TraceInspection, TraceMessageSummary, TraceRecord, TraceSourceSummary
from replay_tool.storage.asc import AscTraceReader
from replay_tool.storage.binary_cache import (
    BINARY_CACHE_FORMAT,
    BINARY_CACHE_SUFFIX,
    BinaryFrameCacheWriter,
    BinaryFrameIndexEntry,
    build_binary_frame_cache_index,
    iter_binary_frame_cache,
    iter_binary_frame_cache_blocks,
)
from replay_tool.storage.frame_filters import normalize_source_filters


JSON_CACHE_SUFFIX = ".frames.json"


class ManagedTraceReader:
    def __init__(self) -> None:
        self.asc_reader = AscTraceReader()

    def read(self, path: str) -> list[Frame]:
        """Read frames from a raw ASC trace or managed binary frame cache.

        Args:
            path: Path to an ASC trace or binary frame cache.

        Returns:
            Parsed replay frames.
        """
        return list(self.iter(path))

    def iter(
        self,
        path: str,
        *,
        source_filters: Iterable[tuple[int, BusType]] | None = None,
        start_ns: int | None = None,
        end_ns: int | None = None,
    ) -> Iterator[Frame]:
        """Iterate frames from a raw ASC trace or managed binary frame cache.

        Args:
            path: Path to an ASC trace or binary frame cache.
            source_filters: Optional `(source_channel, bus)` pairs to include.
            start_ns: Optional inclusive lower timestamp bound.
            end_ns: Optional exclusive upper timestamp bound.

        Yields:
            Parsed replay frames matching the requested filters.

        Raises:
            ValueError: If a legacy JSON cache or unsupported trace path is
                requested.
        """
        trace_path = Path(path)
        if trace_path.name.endswith(BINARY_CACHE_SUFFIX):
            yield from iter_binary_frame_cache(
                trace_path,
                source_filters=source_filters,
                start_ns=start_ns,
                end_ns=end_ns,
            )
            return
        if trace_path.name.endswith(JSON_CACHE_SUFFIX) or trace_path.suffix.lower() == ".json":
            raise ValueError("JSON trace caches are unsupported; re-import the trace to create a binary cache.")
        if trace_path.suffix.lower() != ".asc":
            raise ValueError(f"Unsupported trace format: {trace_path.suffix}")
        normalized_filters = normalize_source_filters(source_filters)
        for frame in self.asc_reader.iter(str(trace_path)):
            if normalized_filters is not None and (frame.channel, frame.bus) not in normalized_filters:
                continue
            if start_ns is not None and frame.ts_ns < int(start_ns):
                continue
            if end_ns is not None and frame.ts_ns >= int(end_ns):
                continue
            yield frame


class SqliteTraceStore:
    def __init__(self, root: str | Path, trace_reader: ManagedTraceReader | None = None) -> None:
        self.root = Path(root)
        self.trace_dir = self.root / "traces"
        self.cache_dir = self.root / "cache"
        self.sqlite_path = self.root / "library.sqlite3"
        self.trace_reader = trace_reader or ManagedTraceReader()
        self._ensure_dirs()
        self._initialize_schema()

    def import_trace(self, source_path: str) -> TraceRecord:
        """Import a trace file into the SQLite-backed trace library.

        Args:
            source_path: Filesystem path to the original trace file.

        Returns:
            Metadata record for the imported trace and generated cache.

        Raises:
            FileNotFoundError: If the source trace does not exist.
            ValueError: If the trace reader finds no supported frames.
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(source)
        if source.suffix.lower() != ".asc":
            raise ValueError(f"Only ASC trace import is supported: {source.suffix}")
        trace_id = uuid.uuid4().hex
        library_path = self.trace_dir / f"{trace_id}{source.suffix.lower()}"
        cache_path = self.cache_dir / f"{trace_id}{BINARY_CACHE_SUFFIX}"
        shutil.copy2(source, library_path)
        try:
            summary, index_entries = self._write_cache_from_asc(library_path, cache_path)
        except Exception:
            self._unlink_if_exists(str(library_path))
            raise
        imported_at = datetime.now(timezone.utc).isoformat()
        record = TraceRecord(
            trace_id=trace_id,
            name=source.name,
            original_path=str(source.resolve()),
            library_path=str(library_path),
            cache_path=str(cache_path),
            imported_at=imported_at,
            event_count=summary.event_count,
            start_ns=summary.start_ns,
            end_ns=summary.end_ns,
            metadata={
                "cache_format": BINARY_CACHE_FORMAT,
                "source_summaries": summary.source_summaries_json(),
                "message_summaries": summary.message_summaries_json(),
            },
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO trace_files (
                    trace_id, name, original_path, library_path, cache_path, imported_at,
                    event_count, start_ns, end_ns, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.trace_id,
                    record.name,
                    record.original_path,
                    record.library_path,
                    record.cache_path,
                    record.imported_at,
                    record.event_count,
                    record.start_ns,
                    record.end_ns,
                    json.dumps(record.metadata, ensure_ascii=False, sort_keys=True),
                ),
            )
            self._replace_frame_index(connection, trace_id, index_entries)
        return record

    def list_traces(self) -> list[TraceRecord]:
        """List all imported traces.

        Returns:
            Trace records ordered by import timestamp and trace ID.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT trace_id, name, original_path, library_path, cache_path, imported_at,
                       event_count, start_ns, end_ns, metadata_json
                FROM trace_files
                ORDER BY imported_at, trace_id
                """
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def get_trace(self, trace_id: str) -> TraceRecord | None:
        """Look up an imported trace by ID.

        Args:
            trace_id: Trace library identifier.

        Returns:
            The trace record, or None if the ID is unknown.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT trace_id, name, original_path, library_path, cache_path, imported_at,
                       event_count, start_ns, end_ns, metadata_json
                FROM trace_files
                WHERE trace_id = ?
                """,
                (trace_id,),
            ).fetchone()
        return self._record_from_row(row) if row is not None else None

    def get_trace_by_original_path(self, original_path: str) -> TraceRecord | None:
        """Look up an imported trace by its original absolute source path.

        Args:
            original_path: Original source path used during import.

        Returns:
            The trace record, or None if no import matches the path.
        """
        normalized_path = str(Path(original_path).resolve())
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT trace_id, name, original_path, library_path, cache_path, imported_at,
                       event_count, start_ns, end_ns, metadata_json
                FROM trace_files
                WHERE original_path = ?
                ORDER BY imported_at DESC, trace_id DESC
                LIMIT 1
                """,
                (normalized_path,),
            ).fetchone()
        return self._record_from_row(row) if row is not None else None

    def get_trace_by_cache_path(self, cache_path: str) -> TraceRecord | None:
        """Look up an imported trace by its managed cache path.

        Args:
            cache_path: Binary frame cache path.

        Returns:
            The trace record, or None if no import uses the cache path.
        """
        raw_path = Path(cache_path)
        candidates = (str(raw_path), str(raw_path.resolve()))
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT trace_id, name, original_path, library_path, cache_path, imported_at,
                       event_count, start_ns, end_ns, metadata_json
                FROM trace_files
                WHERE cache_path IN (?, ?)
                ORDER BY imported_at DESC, trace_id DESC
                LIMIT 1
                """,
                candidates,
            ).fetchone()
        return self._record_from_row(row) if row is not None else None

    def inspect_trace(self, trace_id: str) -> TraceInspection:
        """Build source and message summaries for an imported trace.

        Args:
            trace_id: Trace library identifier.

        Returns:
            Trace metadata plus cached or recomputed summaries.

        Raises:
            KeyError: If the trace ID is unknown.
        """
        record = self.get_trace(trace_id)
        if record is None:
            raise KeyError(trace_id)
        metadata = record.metadata
        source_items = metadata.get("source_summaries")
        message_items = metadata.get("message_summaries")
        if not isinstance(source_items, list) or not isinstance(message_items, list):
            frames = self.load_frames(trace_id)
            source_items = _source_summaries_json(frames)
            message_items = _message_summaries_json(frames)
        return TraceInspection(
            record=record,
            sources=tuple(
                TraceSourceSummary(
                    source_channel=int(item["source_channel"]),
                    bus=BusType(item["bus"]),
                    frame_count=int(item["frame_count"]),
                )
                for item in source_items
            ),
            messages=tuple(
                TraceMessageSummary(
                    source_channel=int(item["source_channel"]),
                    bus=BusType(item["bus"]),
                    frame_count=int(item["frame_count"]),
                    message_ids=tuple(int(message_id) for message_id in item.get("message_ids", [])),
                )
                for item in message_items
            ),
        )

    def load_frames(
        self,
        trace_id: str,
        source_filters: Iterable[tuple[int, BusType]] | None = None,
        start_ns: int | None = None,
        end_ns: int | None = None,
    ) -> list[Frame]:
        """Load normalized cached frames for an imported trace.

        Args:
            trace_id: Trace library identifier.
            source_filters: Optional `(source_channel, bus)` pairs to include.
            start_ns: Optional inclusive lower timestamp bound.
            end_ns: Optional exclusive upper timestamp bound.

        Returns:
            Frames decoded from the managed binary cache.

        Raises:
            KeyError: If the trace ID is unknown.
            FileNotFoundError: If the cache file is missing.
            ValueError: If the cache payload is unsupported or invalid.
        """
        return list(self.iter_frames(trace_id, source_filters=source_filters, start_ns=start_ns, end_ns=end_ns))

    def iter_frames(
        self,
        trace_id: str,
        source_filters: Iterable[tuple[int, BusType]] | None = None,
        start_ns: int | None = None,
        end_ns: int | None = None,
    ) -> Iterator[Frame]:
        """Iterate normalized cached frames for an imported trace.

        Args:
            trace_id: Trace library identifier.
            source_filters: Optional `(source_channel, bus)` pairs to include.
            start_ns: Optional inclusive lower timestamp bound.
            end_ns: Optional exclusive upper timestamp bound.

        Returns:
            Iterator over frames decoded from the managed binary cache.

        Raises:
            KeyError: If the trace ID is unknown.
            FileNotFoundError: If the cache file is missing.
            ValueError: If the cache payload is unsupported or invalid.
        """
        record = self.get_trace(trace_id)
        if record is None:
            raise KeyError(trace_id)
        cache_path = Path(record.cache_path)
        if cache_path.name.endswith(JSON_CACHE_SUFFIX):
            raise ValueError("JSON trace caches are unsupported; re-import the trace to create a binary cache.")
        if not cache_path.exists():
            raise FileNotFoundError(cache_path)
        normalized_filters = normalize_source_filters(source_filters)
        index_entries = self._ensure_frame_index(record)
        if index_entries:
            selected_blocks = _select_index_blocks(index_entries, normalized_filters, start_ns, end_ns)
            return iter_binary_frame_cache_blocks(
                cache_path,
                selected_blocks,
                source_filters=normalized_filters,
                start_ns=start_ns,
                end_ns=end_ns,
            )
        return self.trace_reader.iter(
            str(cache_path),
            source_filters=normalized_filters,
            start_ns=start_ns,
            end_ns=end_ns,
        )

    def rebuild_cache(self, trace_id: str) -> TraceRecord:
        """Rebuild one binary cache from its copied ASC file.

        Args:
            trace_id: Trace library identifier.

        Returns:
            Updated trace record.

        Raises:
            KeyError: If the trace ID is unknown.
            FileNotFoundError: If the copied ASC file is missing.
            ValueError: If the copied file cannot be parsed as ASC.
        """
        record = self.get_trace(trace_id)
        if record is None:
            raise KeyError(trace_id)
        library_path = Path(record.library_path)
        if not library_path.exists():
            raise FileNotFoundError(library_path)
        cache_path = self.cache_dir / f"{trace_id}{BINARY_CACHE_SUFFIX}"
        summary, index_entries = self._write_cache_from_asc(library_path, cache_path)
        metadata = dict(record.metadata)
        metadata["cache_format"] = BINARY_CACHE_FORMAT
        metadata["source_summaries"] = summary.source_summaries_json()
        metadata["message_summaries"] = summary.message_summaries_json()
        with self._connect() as connection:
            self._update_trace_record(
                connection,
                trace_id,
                cache_path=str(cache_path),
                event_count=summary.event_count,
                start_ns=summary.start_ns,
                end_ns=summary.end_ns,
                metadata=metadata,
            )
            self._replace_frame_index(connection, trace_id, index_entries)
        updated = self.get_trace(trace_id)
        assert updated is not None
        return updated

    def delete_trace(self, trace_id: str) -> DeleteTraceResult:
        """Delete one imported trace record and managed files.

        Args:
            trace_id: Trace library identifier.

        Returns:
            Deletion result indicating which files were removed.

        Raises:
            KeyError: If the trace ID is unknown.
        """
        record = self.get_trace(trace_id)
        if record is None:
            raise KeyError(trace_id)
        deleted_library_file = self._unlink_if_exists(record.library_path)
        deleted_cache_file = self._unlink_if_exists(record.cache_path)
        with self._connect() as connection:
            connection.execute("DELETE FROM trace_frame_index WHERE trace_id = ?", (trace_id,))
            connection.execute("DELETE FROM trace_files WHERE trace_id = ?", (trace_id,))
        return DeleteTraceResult(
            trace_id=record.trace_id,
            name=record.name,
            deleted_library_file=deleted_library_file,
            deleted_cache_file=deleted_cache_file,
        )

    def _write_cache_from_asc(
        self,
        library_path: Path,
        cache_path: Path,
    ) -> tuple["_TraceSummaryBuilder", list[BinaryFrameIndexEntry]]:
        summary = _TraceSummaryBuilder()
        with BinaryFrameCacheWriter(cache_path) as writer:
            for frame in self.trace_reader.asc_reader.iter(str(library_path)):
                writer.write(frame)
                summary.add(frame)
            if summary.event_count == 0:
                raise ValueError(f"No ASC frames found in {library_path}.")
        return summary, list(writer.index_entries)

    def _ensure_frame_index(self, record: TraceRecord) -> list[BinaryFrameIndexEntry]:
        entries = self._load_frame_index(record.trace_id)
        if entries or record.event_count == 0:
            return entries
        rebuilt = build_binary_frame_cache_index(record.cache_path)
        with self._connect() as connection:
            self._replace_frame_index(connection, record.trace_id, rebuilt)
        return rebuilt

    def _load_frame_index(self, trace_id: str) -> list[BinaryFrameIndexEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT block_number, file_offset, start_ns, end_ns, frame_count, sources_json
                FROM trace_frame_index
                WHERE trace_id = ?
                ORDER BY block_number
                """,
                (trace_id,),
            ).fetchall()
        return [_index_entry_from_row(row) for row in rows]

    def _replace_frame_index(
        self,
        connection: sqlite3.Connection,
        trace_id: str,
        entries: Sequence[BinaryFrameIndexEntry],
    ) -> None:
        connection.execute("DELETE FROM trace_frame_index WHERE trace_id = ?", (trace_id,))
        connection.executemany(
            """
            INSERT INTO trace_frame_index (
                trace_id, block_number, file_offset, start_ns, end_ns, frame_count, sources_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    trace_id,
                    int(entry.block_number),
                    int(entry.file_offset),
                    int(entry.start_ns),
                    int(entry.end_ns),
                    int(entry.frame_count),
                    json.dumps(
                        [
                            {"source_channel": channel, "bus": bus.value}
                            for channel, bus in entry.sources
                        ],
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                )
                for entry in entries
            ],
        )

    def _ensure_dirs(self) -> None:
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.sqlite_path)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trace_files (
                    trace_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    library_path TEXT NOT NULL,
                    cache_path TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    start_ns INTEGER NOT NULL,
                    end_ns INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trace_frame_index (
                    trace_id TEXT NOT NULL,
                    block_number INTEGER NOT NULL,
                    file_offset INTEGER NOT NULL,
                    start_ns INTEGER NOT NULL,
                    end_ns INTEGER NOT NULL,
                    frame_count INTEGER NOT NULL,
                    sources_json TEXT NOT NULL,
                    PRIMARY KEY (trace_id, block_number),
                    FOREIGN KEY (trace_id) REFERENCES trace_files(trace_id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS trace_frame_index_time_idx
                ON trace_frame_index(trace_id, start_ns, end_ns)
                """
            )

    def _record_from_row(self, row) -> TraceRecord:
        metadata_raw = row[9] if row[9] else "{}"
        metadata = json.loads(metadata_raw)
        if not isinstance(metadata, dict):
            metadata = {}
        return TraceRecord(
            trace_id=str(row[0]),
            name=str(row[1]),
            original_path=str(row[2]),
            library_path=str(row[3]),
            cache_path=str(row[4]),
            imported_at=str(row[5]),
            event_count=int(row[6]),
            start_ns=int(row[7]),
            end_ns=int(row[8]),
            metadata=metadata,
        )

    def _update_trace_record(
        self,
        connection: sqlite3.Connection,
        trace_id: str,
        *,
        cache_path: str,
        event_count: int,
        start_ns: int,
        end_ns: int,
        metadata: dict[str, object],
    ) -> None:
        connection.execute(
            """
            UPDATE trace_files
            SET cache_path = ?, event_count = ?, start_ns = ?, end_ns = ?, metadata_json = ?
            WHERE trace_id = ?
            """,
            (
                cache_path,
                int(event_count),
                int(start_ns),
                int(end_ns),
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                trace_id,
            ),
        )

    @staticmethod
    def _unlink_if_exists(raw_path: str) -> bool:
        path = Path(raw_path)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True


class _TraceSummaryBuilder:
    def __init__(self) -> None:
        self.event_count = 0
        self.start_ns = 0
        self.end_ns = 0
        self._source_counts: dict[tuple[int, BusType], int] = {}
        self._source_start_ns: dict[tuple[int, BusType], int] = {}
        self._source_end_ns: dict[tuple[int, BusType], int] = {}
        self._message_ids: dict[tuple[int, BusType], set[int]] = {}

    def add(self, frame: Frame) -> None:
        """Accumulate one streamed frame.

        Args:
            frame: Frame passing through import or rebuild.
        """
        if self.event_count == 0:
            self.start_ns = frame.ts_ns
        self.event_count += 1
        self.end_ns = frame.ts_ns
        key = (frame.channel, frame.bus)
        self._source_counts[key] = self._source_counts.get(key, 0) + 1
        self._source_start_ns.setdefault(key, frame.ts_ns)
        self._source_end_ns[key] = frame.ts_ns
        self._message_ids.setdefault(key, set()).add(frame.message_id)

    def source_summaries_json(self) -> list[dict[str, object]]:
        """Return source summaries for trace metadata.

        Returns:
            JSON-serializable source-channel summary items.
        """
        return [
            {
                "source_channel": channel,
                "bus": bus.value,
                "frame_count": count,
                "start_ns": self._source_start_ns[(channel, bus)],
                "end_ns": self._source_end_ns[(channel, bus)],
            }
            for (channel, bus), count in sorted(
                self._source_counts.items(),
                key=lambda item: (item[0][0], item[0][1].value),
            )
        ]

    def message_summaries_json(self) -> list[dict[str, object]]:
        """Return message summaries for trace metadata.

        Returns:
            JSON-serializable message summary items.
        """
        result: list[dict[str, object]] = []
        for channel, bus in sorted(self._source_counts, key=lambda item: (item[0], item[1].value)):
            result.append(
                {
                    "source_channel": channel,
                    "bus": bus.value,
                    "frame_count": self._source_counts[(channel, bus)],
                    "message_ids": sorted(self._message_ids[(channel, bus)]),
                }
            )
        return result


def _index_entry_from_row(row) -> BinaryFrameIndexEntry:
    sources_raw = json.loads(row[5] or "[]")
    sources: list[tuple[int, BusType]] = []
    if isinstance(sources_raw, list):
        for item in sources_raw:
            if not isinstance(item, dict):
                continue
            sources.append((int(item["source_channel"]), BusType(item["bus"])))
    return BinaryFrameIndexEntry(
        block_number=int(row[0]),
        file_offset=int(row[1]),
        start_ns=int(row[2]),
        end_ns=int(row[3]),
        frame_count=int(row[4]),
        sources=tuple(sources),
    )


def _select_index_blocks(
    entries: Sequence[BinaryFrameIndexEntry],
    source_filters: set[tuple[int, BusType]] | None,
    start_ns: int | None,
    end_ns: int | None,
) -> list[BinaryFrameIndexEntry]:
    start_value = int(start_ns) if start_ns is not None else None
    end_value = int(end_ns) if end_ns is not None else None
    selected: list[BinaryFrameIndexEntry] = []
    for entry in entries:
        if start_value is not None and entry.end_ns < start_value:
            continue
        if end_value is not None and entry.start_ns >= end_value:
            continue
        if source_filters is not None and not any(source in source_filters for source in entry.sources):
            continue
        selected.append(entry)
    return selected


def _source_summaries_json(frames: Sequence[Frame]) -> list[dict[str, object]]:
    counts: dict[tuple[int, BusType], int] = {}
    for frame in frames:
        key = (frame.channel, frame.bus)
        counts[key] = counts.get(key, 0) + 1
    return [
        {
            "source_channel": channel,
            "bus": bus.value,
            "frame_count": count,
        }
        for (channel, bus), count in sorted(counts.items(), key=lambda item: (item[0][0], item[0][1].value))
    ]


def _message_summaries_json(frames: Sequence[Frame]) -> list[dict[str, object]]:
    grouped: dict[tuple[int, BusType], dict[str, object]] = {}
    for frame in frames:
        key = (frame.channel, frame.bus)
        summary = grouped.setdefault(
            key,
            {
                "source_channel": frame.channel,
                "bus": frame.bus.value,
                "frame_count": 0,
                "message_ids": set(),
            },
        )
        summary["frame_count"] = int(summary["frame_count"]) + 1
        message_ids = summary["message_ids"]
        assert isinstance(message_ids, set)
        message_ids.add(frame.message_id)
    result: list[dict[str, object]] = []
    for _key, summary in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1].value)):
        message_ids = summary["message_ids"]
        assert isinstance(message_ids, set)
        result.append(
            {
                "source_channel": int(summary["source_channel"]),
                "bus": str(summary["bus"]),
                "frame_count": int(summary["frame_count"]),
                "message_ids": sorted(int(message_id) for message_id in message_ids),
            }
        )
    return result

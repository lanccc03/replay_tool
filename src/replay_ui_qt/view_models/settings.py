from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from replay_ui_qt.view_models.base import BaseViewModel


class SettingsApplication(Protocol):
    """Application methods required by the Settings ViewModel."""

    def list_device_drivers(self) -> tuple[str, ...]:
        """List registered driver identifiers.

        Returns:
            Driver names available through the application registry.
        """
        ...


@dataclass(frozen=True)
class SettingsBoundaryRow:
    """Display row for an unsupported or blocked product capability."""

    feature: str
    state: str
    detail: str


@dataclass(frozen=True)
class SettingsValidationRow:
    """Display row for one automated or manual validation item."""

    item: str
    state: str
    detail: str


class SettingsViewModel(BaseViewModel):
    """Expose read-only productization and validation status for Settings.

    The ViewModel intentionally does not persist user preferences. It reports
    current workspace facts, existing app-layer driver registrations, and the
    validation boundaries that matter before the workbench is considered a
    daily-use engineering tool.
    """

    def __init__(self, application: SettingsApplication, *, workspace: str | Path) -> None:
        """Initialize Settings display data.

        Args:
            application: App-layer facade used only to list registered drivers.
            workspace: Trace/project workspace shown by the UI shell.
        """
        super().__init__()
        self._application = application
        self._workspace = Path(workspace)
        self._drivers = tuple(application.list_device_drivers())

    @property
    def workspace(self) -> str:
        """Return the workspace path shown in Settings.

        Returns:
            Workspace path string.
        """
        return str(self._workspace)

    @property
    def theme_name(self) -> str:
        """Return the active UI theme label.

        Returns:
            Human-readable theme name.
        """
        return "默认浅色工程主题"

    @property
    def driver_names(self) -> tuple[str, ...]:
        """Return registered device driver names.

        Returns:
            Driver names from the application registry, or a placeholder when
            none are registered.
        """
        if self._drivers:
            return self._drivers
        return ("未注册",)

    @property
    def driver_text(self) -> str:
        """Return a compact driver list for text panels.

        Returns:
            Comma-separated driver names.
        """
        return ", ".join(self.driver_names)

    @property
    def unsupported_features(self) -> tuple[SettingsBoundaryRow, ...]:
        """Return capabilities that must not be presented as usable yet.

        Returns:
            Blocked or planned feature rows for the Settings page.
        """
        return (
            SettingsBoundaryRow(
                feature="DBC / Signal Override",
                state="Blocked",
                detail="等待 SignalDatabase port、DBC adapter、planner override plan 和 runtime payload patch。",
            ),
            SettingsBoundaryRow(
                feature="Diagnostics / DoIP",
                state="Blocked",
                detail="等待 DiagnosticClient port、diagnostic timeline item、CAN ISO-TP 和 DoIP adapter。",
            ),
            SettingsBoundaryRow(
                feature="BLF / ZLG",
                state="Planned",
                detail="Trace Library 和设备 adapter 尚未接入；不能在 UI 中显示为可用能力。",
            ),
            SettingsBoundaryRow(
                feature="Dark theme / packaging",
                state="Planned",
                detail="保留到后续 M8 批次；本批不宣称完成。",
            ),
        )

    @property
    def validation_items(self) -> tuple[SettingsValidationRow, ...]:
        """Return automated validation commands for this UI baseline.

        Returns:
            Validation rows shown on the Settings page.
        """
        return (
            SettingsValidationRow(
                item="ruff",
                state="Required",
                detail="uv run ruff check src tests",
            ),
            SettingsValidationRow(
                item="compileall",
                state="Required",
                detail='$env:PYTHONPYCACHEPREFIX=(Join-Path $env:TEMP "next_replay_pycache_ui"); uv run python -m compileall src tests',
            ),
            SettingsValidationRow(
                item="unit tests",
                state="Required",
                detail="uv run python -m unittest discover -s tests -v",
            ),
            SettingsValidationRow(
                item="UI entry",
                state="Required",
                detail="uv run replay-ui --help",
            ),
        )

    @property
    def manual_items(self) -> tuple[SettingsValidationRow, ...]:
        """Return manual validation items that automation cannot replace.

        Returns:
            Manual validation rows and their current known state.
        """
        return (
            SettingsValidationRow(
                item="真实窗口点击",
                state="未验证",
                detail="按 docs/ui-manual-validation.md 记录 Trace、Scenario、Replay、Devices、Settings 页面。",
            ),
            SettingsValidationRow(
                item="Windows 高 DPI 100% / 125% / 150%",
                state="未验证",
                detail="检查文本重叠、表格列宽、按钮文本和 Inspector 可读性。",
            ),
            SettingsValidationRow(
                item="Windows 同星真机 UI",
                state="未验证",
                detail="按 docs/tongxing-hardware-validation.md 记录 Devices 枚举和 Scenario 真机 Run。",
            ),
        )

    def summary_text(self) -> str:
        """Return the Settings summary for text panels and tests.

        Returns:
            Multi-line summary of workspace, theme, drivers, and validation
            boundary.
        """
        return "\n".join(
            (
                f"Workspace: {self.workspace}",
                f"Theme: {self.theme_name}",
                f"Drivers: {self.driver_text}",
                "M8.1: Settings 产品化和验证记录基线；M6/M7 core 阻塞能力不启用。",
                "真实窗口、高 DPI 和同星真机 UI 需要手工记录；offscreen 自动化不能替代。",
            )
        )

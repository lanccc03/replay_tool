from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import Signal

from replay_tool.app import DeviceEnumerationResult
from replay_tool.domain import DeviceConfig
from replay_ui_qt.tasks import TaskRunner
from replay_ui_qt.view_models.base import BaseViewModel


class DevicesApplication(Protocol):
    """Application methods required by the Devices ViewModel."""

    def list_device_drivers(self) -> tuple[str, ...]:
        """List registered driver identifiers.

        Returns:
            Driver names available through the application registry.
        """
        ...

    def enumerate_device(self, config: DeviceConfig) -> DeviceEnumerationResult:
        """Enumerate one configured device.

        Args:
            config: Device adapter configuration.

        Returns:
            App-layer device enumeration result.
        """
        ...


@dataclass(frozen=True)
class DeviceConfigDraft:
    """Editable UI draft for one device enumeration request."""

    device_id: str = "device0"
    driver: str = "tongxing"
    sdk_root: str = "TSMaster/Windows"
    application: str = "ReplayTool"
    device_type: str = "TC1014"
    device_index: int = 0

    def to_config(self) -> DeviceConfig:
        """Convert the UI draft to a domain device configuration.

        Returns:
            DeviceConfig accepted by the app-layer enumeration API.
        """
        return DeviceConfig(
            id=self.device_id,
            driver=self.driver,
            application=self.application,
            sdk_root=self.sdk_root,
            device_type=self.device_type,
            device_index=int(self.device_index),
        )


@dataclass(frozen=True)
class DeviceSummaryDetails:
    """Display summary for an enumerated device."""

    device_id: str
    driver: str
    name: str
    serial_number: str
    channel_count: int
    health: str
    health_detail: str

    @classmethod
    def from_result(cls, result: DeviceEnumerationResult) -> "DeviceSummaryDetails":
        """Build display details from an app-layer enumeration result.

        Args:
            result: Device enumeration result returned by the application.

        Returns:
            Summary values ready for UI display.
        """
        return cls(
            device_id=result.info.id,
            driver=result.info.driver,
            name=result.info.name,
            serial_number=result.info.serial_number,
            channel_count=int(result.info.channel_count),
            health="Online" if result.health.online else "Offline",
            health_detail=result.health.detail,
        )


@dataclass(frozen=True)
class DeviceCapabilityRow:
    """Display row for one device capability flag."""

    name: str
    supported: bool


@dataclass(frozen=True)
class DeviceChannelRow:
    """Display row for one enumerated physical channel."""

    physical_channel: int
    status: str


class DevicesViewModel(BaseViewModel):
    """Expose device enumeration configuration and results to Qt views."""

    configChanged = Signal()
    resultChanged = Signal()

    def __init__(self, application: DevicesApplication, task_runner: TaskRunner) -> None:
        """Initialize the Devices ViewModel.

        Args:
            application: App-layer facade used for device enumeration.
            task_runner: Shared UI background task runner.
        """
        super().__init__()
        self._application = application
        self._task_runner = task_runner
        self._enumerate_task_name = f"devices-enumerate-{id(self)}"
        self._drivers = tuple(application.list_device_drivers())
        self._draft = DeviceConfigDraft()
        self._summary: DeviceSummaryDetails | None = None
        self._capabilities: tuple[DeviceCapabilityRow, ...] = ()
        self._channels: tuple[DeviceChannelRow, ...] = ()

    @property
    def drivers(self) -> tuple[str, ...]:
        """Return selectable driver names.

        Returns:
            Driver identifiers from the app registry.
        """
        if self._drivers:
            return self._drivers
        return ("tongxing",)

    @property
    def draft(self) -> DeviceConfigDraft:
        """Return the current editable device config draft.

        Returns:
            Current config draft.
        """
        return self._draft

    @property
    def summary(self) -> DeviceSummaryDetails | None:
        """Return the latest enumeration summary.

        Returns:
            Device summary, or None before successful enumeration.
        """
        return self._summary

    @property
    def capabilities(self) -> tuple[DeviceCapabilityRow, ...]:
        """Return latest capability rows.

        Returns:
            Capability rows from the last enumeration.
        """
        return self._capabilities

    @property
    def channels(self) -> tuple[DeviceChannelRow, ...]:
        """Return latest physical channel rows.

        Returns:
            Channel rows from the last enumeration.
        """
        return self._channels

    def set_driver(self, driver: str) -> None:
        """Update the selected driver.

        Args:
            driver: Driver identifier selected in the UI.
        """
        self._replace_draft(driver=str(driver).lower())

    def set_sdk_root(self, sdk_root: str) -> None:
        """Update SDK root path text.

        Args:
            sdk_root: SDK root entered by the user.
        """
        self._replace_draft(sdk_root=str(sdk_root))

    def set_application(self, application: str) -> None:
        """Update TSMaster application name.

        Args:
            application: Application name entered by the user.
        """
        self._replace_draft(application=str(application))

    def set_device_type(self, device_type: str) -> None:
        """Update hardware device type.

        Args:
            device_type: Device type entered by the user.
        """
        self._replace_draft(device_type=str(device_type))

    def set_device_index(self, device_index: int) -> None:
        """Update hardware device index.

        Args:
            device_index: Device index entered by the user.
        """
        self._replace_draft(device_index=int(device_index))

    def current_config(self) -> DeviceConfig:
        """Return the current draft as a domain config.

        Returns:
            DeviceConfig for app-layer enumeration.
        """
        return self._draft.to_config()

    def enumerate_current_device(self) -> None:
        """Enumerate the current device config through the app layer."""
        if self.busy:
            self.set_status_message("Devices 正在枚举")
            return
        self.run_background_task(
            self._task_runner,
            self._enumerate_task_name,
            lambda: self._application.enumerate_device(self.current_config()),
            self._apply_result,
            start_status="Devices 正在枚举",
            failure_status="Devices 枚举失败",
            duplicate_status="Devices 正在枚举",
        )

    def _apply_result(self, result: object) -> None:
        if not isinstance(result, DeviceEnumerationResult):
            raise TypeError("Device enumeration did not return DeviceEnumerationResult.")
        self._summary = DeviceSummaryDetails.from_result(result)
        self._capabilities = _capability_rows(result)
        self._channels = _channel_rows(result)
        self.resultChanged.emit()
        self.set_status_message(f"Device 已枚举: {result.info.name}")

    def _replace_draft(
        self,
        *,
        driver: str | None = None,
        sdk_root: str | None = None,
        application: str | None = None,
        device_type: str | None = None,
        device_index: int | None = None,
    ) -> None:
        if self.busy:
            self.set_status_message("Devices 正在枚举")
            return
        self._draft = DeviceConfigDraft(
            device_id=self._draft.device_id,
            driver=self._draft.driver if driver is None else driver,
            sdk_root=self._draft.sdk_root if sdk_root is None else sdk_root,
            application=self._draft.application if application is None else application,
            device_type=self._draft.device_type if device_type is None else device_type,
            device_index=self._draft.device_index if device_index is None else int(device_index),
        )
        self.configChanged.emit()


def _capability_rows(result: DeviceEnumerationResult) -> tuple[DeviceCapabilityRow, ...]:
    capabilities = result.capabilities
    return (
        DeviceCapabilityRow("CAN", bool(capabilities.can)),
        DeviceCapabilityRow("CANFD", bool(capabilities.canfd)),
        DeviceCapabilityRow("Async Send", bool(capabilities.async_send)),
        DeviceCapabilityRow("FIFO Read", bool(capabilities.fifo_read)),
    )


def _channel_rows(result: DeviceEnumerationResult) -> tuple[DeviceChannelRow, ...]:
    rows: list[DeviceChannelRow] = []
    for channel in result.channels:
        known = result.health.per_channel.get(int(channel))
        if known is None:
            status = "Unknown"
        else:
            status = "Channel Ready" if known else "Channel Error"
        rows.append(DeviceChannelRow(physical_channel=int(channel), status=status))
    return tuple(rows)

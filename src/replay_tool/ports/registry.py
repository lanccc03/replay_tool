from __future__ import annotations

from collections.abc import Callable

from replay_tool.domain import DeviceConfig
from replay_tool.ports.device import BusDevice


DeviceFactory = Callable[[DeviceConfig], BusDevice]


class DeviceRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, DeviceFactory] = {}

    def register(self, driver: str, factory: DeviceFactory) -> None:
        """Register a factory for a device driver name.

        Args:
            driver: Case-insensitive driver identifier.
            factory: Callable that builds a BusDevice from DeviceConfig.
        """
        self._factories[str(driver).lower()] = factory

    def create(self, config: DeviceConfig) -> BusDevice:
        """Create a device adapter for a configuration.

        Args:
            config: Device configuration with a registered driver.

        Returns:
            A newly created bus device adapter.

        Raises:
            ValueError: If the driver is not registered.
        """
        driver = config.driver.lower()
        factory = self._factories.get(driver)
        if factory is None:
            raise ValueError(f"Unsupported device driver: {config.driver}")
        return factory(config)

    def drivers(self) -> tuple[str, ...]:
        """Return registered driver names.

        Returns:
            Sorted tuple of driver identifiers.
        """
        return tuple(sorted(self._factories))

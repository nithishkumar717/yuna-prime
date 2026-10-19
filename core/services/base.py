from abc import ABC, abstractmethod
from core.logging import get_logger
from core.event_bus import EventDispatcher
from .models import ServiceState, ServiceCategory
from .events import ServiceStateChangedEvent
from .exceptions import ServiceLifecycleError


class BaseService(ABC):
    """Abstract base class dictating uniform lifecycle governance for all modules."""

    def __init__(
        self, name: str, category: ServiceCategory, event_bus: EventDispatcher
    ) -> None:
        self.name = name
        self.category = category
        self.event_bus = event_bus
        self.logger = get_logger("SERVICE", self.name)
        self._state = ServiceState.INITIALIZING

    @property
    def state(self) -> ServiceState:
        return self._state

    async def _set_state(self, new_state: ServiceState) -> None:
        prev_state = self._state
        self._state = new_state
        self.logger.info(f"Transitioning to {new_state.value}", event="StateTransition")

        # Emit SystemEvent denoting state drift
        await self.event_bus.publish(
            ServiceStateChangedEvent(
                service_name=self.name, previous_state=prev_state, new_state=new_state
            )
        )

    async def start(self) -> None:
        """Initiates the service, running custom _on_start logic."""
        if self._state not in (ServiceState.INITIALIZING, ServiceState.STOPPED):
            raise ServiceLifecycleError(
                f"Cannot start {self.name} from state {self._state.value}"
            )

        await self._set_state(ServiceState.STARTING)
        try:
            await self._on_start()
            await self._set_state(ServiceState.READY)
        except Exception as e:
            await self._set_state(ServiceState.FAILED)
            self.logger.error(
                f"Failed to start {self.name}: {e}", event="ServiceFailed"
            )
            raise

    async def stop(self) -> None:
        """Halts the service, running custom _on_stop logic."""
        if self._state not in (
            ServiceState.READY,
            ServiceState.DEGRADED,
            ServiceState.FAILED,
        ):
            raise ServiceLifecycleError(
                f"Cannot stop {self.name} from state {self._state.value}"
            )

        await self._set_state(ServiceState.STOPPING)
        try:
            await self._on_stop()
            await self._set_state(ServiceState.STOPPED)
        except Exception as e:
            await self._set_state(ServiceState.FAILED)
            self.logger.error(f"Failed to stop {self.name}: {e}", event="ServiceFailed")
            raise

    @abstractmethod
    async def _on_start(self) -> None:
        """Override to implement custom startup logic."""
        pass

    @abstractmethod
    async def _on_stop(self) -> None:
        """Override to implement custom shutdown logic."""
        pass

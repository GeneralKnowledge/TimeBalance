"""Model registry and a ModelManager that keeps at most N models resident (LRU)."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable

from mpe.models.base import ForecastModel
from mpe.models.baselines import BASELINES

Factory = Callable[[], ForecastModel]


def _timestral_factory(size: str) -> Factory:
    def make() -> ForecastModel:
        from mpe.models.timestral import TimestralModel  # lazy: keeps torch out of baseline-only use

        return TimestralModel(size)

    return make


REGISTRY: dict[str, Factory] = {
    **{f"timestral-{s.lower()}": _timestral_factory(s) for s in ("5M", "28M", "123M", "209M")},
    **{name: cls for name, cls in BASELINES.items()},
}


class ModelManager:
    """Loads models on demand and unloads the least recently used beyond ``max_resident``."""

    def __init__(
        self, registry: dict[str, Factory] | None = None, max_resident: int = 1, device: str = "auto"
    ) -> None:
        if max_resident < 1:
            raise ValueError("max_resident must be >= 1")
        self.registry = registry if registry is not None else REGISTRY
        self.max_resident = max_resident
        self.device = device
        self._resident: OrderedDict[str, ForecastModel] = OrderedDict()

    @property
    def resident(self) -> list[str]:
        return list(self._resident)

    def get(self, name: str) -> ForecastModel:
        if name in self._resident:
            self._resident.move_to_end(name)
            return self._resident[name]
        if name not in self.registry:
            raise KeyError(f"unknown model {name!r}; known: {sorted(self.registry)}")
        while len(self._resident) >= self.max_resident:
            self.release(next(iter(self._resident)))
        model = self.registry[name]()
        model.load(self.device)
        self._resident[name] = model
        return model

    def release(self, name: str) -> None:
        model = self._resident.pop(name, None)
        if model is not None:
            model.unload()

    def release_all(self) -> None:
        for name in list(self._resident):
            self.release(name)

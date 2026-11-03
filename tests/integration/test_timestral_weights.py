"""Real-weight checks. Run with: uv run pytest -m "weights or gpu" """

import numpy as np
import pytest

from mpe.features.transforms import inv_logit
from mpe.fixtures import make_input, sine_noise, synthetic_index
from mpe.models.base import validate_output
from mpe.models.timestral import SIZES, TimestralModel, cuda_usable


def _have(size):
    return (TimestralModel(size).local_path / "model.safetensors").exists()


def _inp(h=24, n=1000):
    df = sine_noise()
    return make_input(df["value"].to_numpy()[:n], synthetic_index(n), h)


@pytest.mark.weights
@pytest.mark.parametrize("size", list(SIZES))
def test_each_size_cpu(size):
    if not _have(size):
        pytest.skip("weights not downloaded")
    m = TimestralModel(size)
    m.load("cpu")
    a, b = m.forecast(_inp()), m.forecast(_inp())
    validate_output(a, 1, 24)
    np.testing.assert_array_equal(a.quantiles, b.quantiles)  # CPU determinism
    truth = sine_noise()["noiseless"].to_numpy()[1000:1024]
    assert np.abs(a.values[0] - truth).mean() < 1.5  # learns an obvious sine
    p = inv_logit(a.quantiles)
    assert ((p > 0) & (p < 1)).all()
    m.unload()
    assert not m.is_loaded


@pytest.mark.gpu
@pytest.mark.weights
def test_gpu_matches_cpu_and_releases_vram():
    import torch

    if not cuda_usable()[0] or not _have("5M"):
        pytest.skip("no usable GPU or weights")
    cpu = TimestralModel("5M")
    cpu.load("cpu")
    ref = cpu.forecast(_inp())
    cpu.unload()
    gpu = TimestralModel("5M")
    gpu.load("cuda")
    a, b = gpu.forecast(_inp()), gpu.forecast(_inp())
    assert a.device == "cuda:0"
    assert np.abs(a.quantiles - b.quantiles).max() <= 1e-5
    assert np.abs(a.quantiles - ref.quantiles).max() <= 1e-3 * (1 + np.abs(ref.quantiles).max())
    gpu.unload()
    assert torch.cuda.memory_allocated() == 0

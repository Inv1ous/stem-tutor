import matplotlib.pyplot as plt
import numpy as np
import pytest

from build.diagrams import maxwell_boltzmann


def curves(params):
    fig = maxwell_boltzmann(params)
    data = [(line.get_xdata(), line.get_ydata()) for line in fig.axes[0].lines[:len(params["temps"])]]
    plt.close(fig)
    return data


def test_kelvin_temperatures_plot_full_equal_area_distributions():
    data = curves({"temps": [300, 400], "labels": ["300 K", "400 K"], "ea": 1.2})

    for energy, density in data:
        peak = int(np.argmax(density))
        assert 0 < peak < len(density) - 1
        assert np.trapezoid(density, energy) == pytest.approx(1.0, abs=1e-3)
        assert density[-1] < 0.02 * density[peak]
        assert density[-1] < density[peak]


def test_relative_temperatures_are_accepted_and_activation_energy_stays_fixed():
    fig = maxwell_boltzmann({"temps": [0.7, 1.2], "labels": ["low", "high"], "ea": 0.7})
    try:
        ax = fig.axes[0]
        threshold = next(line for line in ax.lines[2:] if np.allclose(line.get_xdata(), [0.7, 0.7]))
        assert threshold.get_xdata()[0] == pytest.approx(0.7)
        assert ax.lines[0].get_xdata()[-1] > 10
    finally:
        plt.close(fig)


@pytest.mark.parametrize("temps", [[0, 1], [-1, 2], [1, float("nan")], [1, float("inf")], []])
def test_rejects_nonpositive_or_nonfinite_temperatures(temps):
    with pytest.raises(ValueError, match="temperatures"):
        maxwell_boltzmann({"temps": temps})


def test_rejects_label_count_mismatch():
    with pytest.raises(ValueError, match="labels"):
        maxwell_boltzmann({"temps": [300, 400], "labels": ["300 K"]})

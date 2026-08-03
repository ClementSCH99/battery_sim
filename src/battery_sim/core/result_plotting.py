"""Plotting utilities for simulation results.

Separated from Result to keep the data class free of presentation concerns.
Import matplotlib only when this module is used, so headless environments
never pay the import cost.
"""

from typing import Optional, List

import numpy as np

from battery_sim.core.result import Signal
from battery_sim.core.result import Result


def plot_result(
    result: Result,
    signals: Optional[List[Signal]] = None,
    figsize: tuple = (14, 10),
    save_path: str = "battery_simulation.png",
):
    """
    Plot selected or all signals with improved formatting.

    Args:
        result: A Result object containing simulation data.
        signals: List of signals to plot. If None, plots all available signals.
        figsize: Matplotlib figure size (width, height).
        save_path: Path to save the figure.
    """
    import matplotlib.pyplot as plt

    if signals is None:
        signals = result.available_signals()

    valid_names = [s for s in signals if s in result._data]

    if not valid_names:
        raise ValueError(
            f"No valid signals to plot. Available: "
            f"{[s.value for s in result.available_signals()]}"
        )

    num_plots = len(valid_names)
    num_cols = 2
    num_rows = (num_plots + num_cols - 1) // num_cols

    fig, axes = plt.subplots(num_rows, num_cols, figsize=figsize)
    fig.suptitle("Battery Simulation Results", fontsize=16, fontweight="bold")

    if num_rows == 1:
        axes = axes.reshape(1, -1)
    axes = axes.flatten()

    for idx, signal in enumerate(valid_names):
        ax = axes[idx]
        ts = result._data[signal]

        ax.plot(ts.time_s, ts.values, linewidth=2.0, color=f"C{idx}")
        ax.grid(True, alpha=0.3, linestyle="--")
        ax.set_xlabel("Time [s]", fontsize=10)
        ax.set_ylabel(
            f"{signal.value.replace('_', ' ').title()} [{ts.unit}]", fontsize=10
        )
        ax.set_title(
            f"{signal.value.replace('_', ' ').title()}", fontsize=11, fontweight="bold"
        )

        values_array = np.array(ts.values)
        valid = values_array[~np.isnan(values_array)]
        if len(valid) > 0:
            min_val, max_val = np.min(valid), np.max(valid)
            min_idx = np.nanargmin(values_array)
            max_idx = np.nanargmax(values_array)

            ax.annotate(
                f"Min: {min_val:.2f}",
                xy=(ts.time_s[min_idx], values_array[min_idx]),
                xytext=(5, -15),
                textcoords="offset points",
                fontsize=8,
                color="red",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.5),
            )
            ax.annotate(
                f"Max: {max_val:.2f}",
                xy=(ts.time_s[max_idx], values_array[max_idx]),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
                color="green",
                bbox=dict(
                    boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.5
                ),
            )

    for idx in range(num_plots, len(axes)):
        axes[idx].axis("off")

    plt.tight_layout()
    plt.savefig(save_path, dpi=100, bbox_inches="tight")
    print(f"✓ Plot saved to {save_path}")


def plot_single_signal(
    result: Result,
    signal: Signal,
    figsize: tuple = (10, 6),
    save_path: Optional[str] = None,
):
    """
    Plot a single signal with detailed formatting.

    Args:
        result: A Result object containing simulation data.
        signal: Signal to plot.
        figsize: Figure size.
        save_path: Path to save (optional). If None, shows interactively.
    """
    import matplotlib.pyplot as plt

    if signal not in result._data:
        raise KeyError(f"Signal '{signal.value}' not found")

    ts = result._data[signal]
    fig, ax = plt.subplots(figsize=figsize)

    ax.plot(
        ts.time_s, ts.values, linewidth=2.5, marker="o", markersize=3, label=signal.value
    )
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.set_xlabel("Time [s]", fontsize=12)
    ax.set_ylabel(
        f"{signal.value.replace('_', ' ').title()} [{ts.unit}]", fontsize=12
    )
    ax.set_title(
        f"{signal.value.replace('_', ' ').title()} Over Time",
        fontsize=14,
        fontweight="bold",
    )
    ax.legend(fontsize=10)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=100, bbox_inches="tight")
        print(f"✓ Plot saved to {save_path}")
    else:
        plt.show()

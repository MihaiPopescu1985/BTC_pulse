#!/usr/bin/env python3
"""Interactive viewer for SAFE feature series.

Reads ``statistics/out/features.json`` and lets you:
- choose one or more series from the ``series`` section
- switch between overlay and stacked layouts
- render the selected charts against the shared ``dates`` axis
"""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


DEFAULT_FEATURES_PATH = Path(__file__).resolve().parents[2] / "out" / "features.json"
DEFAULT_SELECTION = ["close"]


class FeaturesChartApp:
    def __init__(self, root: tk.Tk, features_path: Path) -> None:
        self.root = root
        self.root.title("SAFE Features Viewer")
        self.features_path = features_path

        self.df = self._load_features(features_path)
        self.series_names = list(self.df.columns)
        self.layout_var = tk.StringVar(value="overlay")
        self.status_var = tk.StringVar(value=f"Loaded {features_path}")

        self.figure = Figure(figsize=(12, 8), dpi=100)
        self.chart_frame: ttk.Frame | None = None
        self.canvas: FigureCanvasTkAgg | None = None
        self.toolbar: NavigationToolbar2Tk | None = None

        self._build_ui()
        self._set_default_selection()
        self.redraw()

    def _build_ui(self) -> None:
        self.root.geometry("1400x900")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)

        controls = ttk.Frame(self.root, padding=12)
        controls.grid(row=0, column=0, sticky="nsew")
        controls.rowconfigure(4, weight=1)

        ttk.Label(controls, text="Series", font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            controls,
            text="Select one or more series from features.json.",
            wraplength=280,
            foreground="#555555",
        ).grid(row=1, column=0, sticky="w", pady=(4, 8))

        self.series_listbox = tk.Listbox(
            controls,
            selectmode=tk.MULTIPLE,
            exportselection=False,
            height=28,
            width=34,
        )
        for name in self.series_names:
            self.series_listbox.insert(tk.END, name)
        self.series_listbox.grid(row=4, column=0, sticky="nsew")
        self.series_listbox.bind("<<ListboxSelect>>", lambda _event: self.redraw())

        list_actions = ttk.Frame(controls)
        list_actions.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(list_actions, text="Select all", command=self.select_all).grid(row=0, column=0, sticky="ew")
        ttk.Button(list_actions, text="Clear", command=self.clear_selection).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        list_actions.columnconfigure(0, weight=1)
        list_actions.columnconfigure(1, weight=1)

        layout_box = ttk.LabelFrame(controls, text="Layout", padding=10)
        layout_box.grid(row=6, column=0, sticky="ew", pady=(14, 0))
        ttk.Radiobutton(
            layout_box,
            text="Overlay",
            value="overlay",
            variable=self.layout_var,
            command=self.redraw,
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            layout_box,
            text="Stacked vertically",
            value="stacked",
            variable=self.layout_var,
            command=self.redraw,
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        ttk.Button(controls, text="Reload file", command=self.reload_data).grid(
            row=7, column=0, sticky="ew", pady=(14, 0)
        )
        ttk.Label(
            controls,
            textvariable=self.status_var,
            wraplength=280,
            foreground="#555555",
        ).grid(row=8, column=0, sticky="w", pady=(12, 0))

        self.chart_frame = ttk.Frame(self.root, padding=(0, 12, 12, 12))
        self.chart_frame.grid(row=0, column=1, sticky="nsew")
        self.chart_frame.rowconfigure(0, weight=1)
        self.chart_frame.columnconfigure(0, weight=1)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.chart_frame, pack_toolbar=False)
        self.toolbar.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.toolbar.update()
        self.canvas.draw()

    def _load_features(self, path: Path) -> pd.DataFrame:
        data = json.loads(path.read_text(encoding="utf-8"))
        dates = data.get("dates")
        series = data.get("series")
        if not isinstance(dates, list) or not isinstance(series, dict):
            raise ValueError(f"{path} must contain 'dates' and 'series'.")

        frame = pd.DataFrame(series)
        if frame.empty:
            raise ValueError(f"{path} does not contain any series data.")
        if len(frame) != len(dates):
            raise ValueError(
                f"features.json length mismatch: {len(dates)} dates vs {len(frame)} series rows."
            )

        frame.index = pd.to_datetime(dates, errors="raise")
        frame.index.name = "date"
        for column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame

    def _set_default_selection(self) -> None:
        for name in DEFAULT_SELECTION:
            if name in self.series_names:
                idx = self.series_names.index(name)
                self.series_listbox.selection_set(idx)

    def _selected_series(self) -> list[str]:
        return [self.series_names[i] for i in self.series_listbox.curselection()]

    def select_all(self) -> None:
        self.series_listbox.selection_set(0, tk.END)
        self.redraw()

    def clear_selection(self) -> None:
        self.series_listbox.selection_clear(0, tk.END)
        self.redraw()

    def reload_data(self) -> None:
        try:
            self.df = self._load_features(self.features_path)
        except Exception as exc:
            messagebox.showerror("Reload failed", str(exc))
            self.status_var.set(f"Reload failed: {exc}")
            return
        self.status_var.set(f"Reloaded {self.features_path}")
        self.redraw()

    def redraw(self) -> None:
        selected = self._selected_series()
        self.figure.clear()

        if not selected:
            ax = self.figure.add_subplot(111)
            ax.text(
                0.5,
                0.5,
                "Select one or more series from the list.",
                ha="center",
                va="center",
                fontsize=12,
                transform=ax.transAxes,
            )
            ax.set_axis_off()
            assert self.canvas is not None
            self.canvas.draw()
            self.status_var.set("No series selected")
            return

        layout = self.layout_var.get()
        if layout == "stacked":
            axes = self.figure.subplots(len(selected), 1, sharex=True)
            if len(selected) == 1:
                axes = [axes]
        else:
            axes = [self.figure.add_subplot(111)]

        dates = self.df.index.to_pydatetime()
        colors = plt.rcParams["axes.prop_cycle"].by_key().get("color", ["#1f77b4"])

        if layout == "overlay":
            ax = axes[0]
            for idx, series_name in enumerate(selected):
                values = self.df[series_name].to_numpy(dtype=float)
                ax.plot(dates, values, label=series_name, linewidth=1.6, color=colors[idx % len(colors)])
            ax.legend(loc="upper left", ncol=2, fontsize=9)
            ax.set_ylabel("value")
            ax.set_title("Selected SAFE feature series")
            self._style_axis(ax)
        else:
            for idx, (ax, series_name) in enumerate(zip(axes, selected)):
                values = self.df[series_name].to_numpy(dtype=float)
                ax.plot(dates, values, linewidth=1.6, color=colors[idx % len(colors)])
                ax.set_title(series_name, loc="left", fontsize=11)
                ax.set_ylabel("value")
                self._style_axis(ax)
            axes[-1].set_xlabel("date")

        self.figure.tight_layout()
        assert self.canvas is not None
        self.canvas.draw()
        if self.toolbar is not None:
            self.toolbar.update()
        self.status_var.set(f"Showing {len(selected)} series in {layout} layout")

    def _style_axis(self, ax: Any) -> None:
        ax.grid(True, alpha=0.25)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))



def main() -> None:
    root = tk.Tk()
    try:
        FeaturesChartApp(root, DEFAULT_FEATURES_PATH)
    except Exception as exc:
        root.withdraw()
        messagebox.showerror("SAFE features viewer", str(exc))
        raise SystemExit(str(exc)) from exc
    root.mainloop()


if __name__ == "__main__":
    main()

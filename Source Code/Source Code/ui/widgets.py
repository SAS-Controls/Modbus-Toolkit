"""
SAS Modbus Toolkit — Shared UI Widgets
Reusable widget components for the Modbus Toolkit UI.
"""

import tkinter as tk
import customtkinter as ctk
from ui.theme import *


def make_label_entry(parent, label: str, default: str = "", width: int = 120,
                      placeholder: str = "", mono: bool = False) -> ctk.CTkEntry:
    """Create a labeled input field inline."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(side="left", padx=(0, 16))

    ctk.CTkLabel(row, text=label, font=(FONT_FAMILY, FONT_SIZE_BODY),
                  text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))

    font = (FONT_FAMILY_MONO if mono else FONT_FAMILY, FONT_SIZE_BODY)
    entry = ctk.CTkEntry(row, width=width, height=INPUT_HEIGHT,
                          font=font, placeholder_text=placeholder,
                          fg_color=BG_INPUT, border_color=BORDER_COLOR)
    entry.pack(side="left")
    if default:
        entry.insert(0, default)
    return entry


def make_labeled_combo(parent, label: str, values: list,
                        default: str = "", width: int = 130) -> ctk.CTkComboBox:
    """Create a labeled combo box inline."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(side="left", padx=(0, 16))

    ctk.CTkLabel(row, text=label, font=(FONT_FAMILY, FONT_SIZE_BODY),
                  text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 6))

    combo = ctk.CTkComboBox(row, values=values, width=width,
                              height=INPUT_HEIGHT,
                              font=(FONT_FAMILY_MONO, FONT_SIZE_BODY),
                              fg_color=BG_INPUT, border_color=BORDER_COLOR,
                              button_color=SAS_BLUE, button_hover_color=SAS_BLUE_DARK,
                              dropdown_fg_color=BG_CARD,
                              dropdown_text_color=TEXT_PRIMARY)
    combo.pack(side="left")
    if default:
        combo.set(default)
    return combo


def make_section_header(parent, title: str, subtitle: str = "") -> ctk.CTkFrame:
    """Create a consistent section header bar."""
    frame = ctk.CTkFrame(parent, fg_color="transparent", height=50)
    frame.pack(fill="x", padx=24, pady=(16, 4))
    frame.pack_propagate(False)

    ctk.CTkLabel(frame, text=title,
                  font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                  text_color=TEXT_PRIMARY, anchor="w").pack(side="left")

    if subtitle:
        ctk.CTkLabel(frame, text=subtitle,
                      font=(FONT_FAMILY, FONT_SIZE_BODY),
                      text_color=TEXT_MUTED, anchor="w").pack(side="left", padx=(12, 0))
    return frame


def make_status_badge(parent, text: str, color: str) -> ctk.CTkLabel:
    """Create a colored status badge label."""
    return ctk.CTkLabel(parent, text=f"⬤  {text}",
                         font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
                         text_color=color)


def make_card(parent, **kwargs) -> ctk.CTkFrame:
    """Create a standard card frame."""
    return ctk.CTkFrame(parent, fg_color=BG_CARD,
                         corner_radius=CARD_CORNER_RADIUS, **kwargs)


def make_primary_button(parent, text: str, command=None,
                          width: int = 120, **kwargs) -> ctk.CTkButton:
    """Create a primary action button (SAS blue)."""
    return ctk.CTkButton(
        parent, text=text, command=command, width=width,
        height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER_RADIUS,
        font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
        fg_color=SAS_BLUE, hover_color=SAS_BLUE_DARK,
        **kwargs,
    )


def make_danger_button(parent, text: str, command=None,
                        width: int = 120, **kwargs) -> ctk.CTkButton:
    """Create a danger/stop button (red)."""
    return ctk.CTkButton(
        parent, text=text, command=command, width=width,
        height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER_RADIUS,
        font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"),
        fg_color=STATUS_ERROR, hover_color="#C53030",
        **kwargs,
    )


def make_secondary_button(parent, text: str, command=None,
                           width: int = 120, **kwargs) -> ctk.CTkButton:
    """Create a secondary/neutral button."""
    return ctk.CTkButton(
        parent, text=text, command=command, width=width,
        height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER_RADIUS,
        font=(FONT_FAMILY, FONT_SIZE_BODY),
        fg_color=BG_CARD, hover_color=BG_CARD_HOVER,
        text_color=TEXT_PRIMARY, border_width=1, border_color=BORDER_COLOR,
        **kwargs,
    )


def make_divider(parent) -> ctk.CTkFrame:
    """Create a horizontal divider line."""
    d = ctk.CTkFrame(parent, fg_color=BORDER_COLOR, height=1)
    d.pack(fill="x", padx=24, pady=6)
    return d


def enable_touch_scroll(widget):
    """Enable mouse wheel scrolling on a scrollable frame."""
    def _on_mousewheel(event):
        try:
            widget._parent_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass
    widget.bind_all("<MouseWheel>", _on_mousewheel)


class LogBox(ctk.CTkFrame):
    """
    Scrollable, color-coded log/console widget.
    Supports appending lines with per-line color tags.
    """

    def __init__(self, parent, max_lines: int = 500, **kwargs):
        super().__init__(parent, fg_color=BG_INPUT, corner_radius=CARD_CORNER_RADIUS,
                          border_width=1, border_color=BORDER_COLOR, **kwargs)
        self._max_lines = max_lines
        self._line_count = 0

        self._text = tk.Text(
            self,
            bg=resolve_color(BG_INPUT),
            fg=resolve_color(TEXT_PRIMARY),
            font=(FONT_FAMILY_MONO, FONT_SIZE_SMALL),
            wrap="none",
            state="disabled",
            relief="flat",
            bd=0,
            highlightthickness=0,
            insertbackground=resolve_color(TEXT_PRIMARY),
        )
        sb_y = ctk.CTkScrollbar(self, command=self._text.yview)
        sb_x = ctk.CTkScrollbar(self, command=self._text.xview, orientation="horizontal")
        self._text.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        sb_y.pack(side="right", fill="y", padx=(0, 2), pady=2)
        sb_x.pack(side="bottom", fill="x", padx=2, pady=(0, 2))
        self._text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)

        # Define color tags
        self._text.tag_configure("ok",      foreground=STATUS_GOOD)
        self._text.tag_configure("error",   foreground=STATUS_ERROR)
        self._text.tag_configure("warn",    foreground=STATUS_WARN)
        self._text.tag_configure("info",    foreground=STATUS_INFO)
        self._text.tag_configure("muted",   foreground=resolve_color(TEXT_MUTED))
        self._text.tag_configure("tx",      foreground=SAS_BLUE_LIGHT)
        self._text.tag_configure("rx",      foreground=STATUS_GOOD)
        self._text.tag_configure("timeout", foreground=MODBUS_TIMEOUT_COLOR)

    def append(self, line: str, tag: str = ""):
        """Append a line of text, optionally colored."""
        self._text.configure(state="normal")
        if self._line_count >= self._max_lines:
            self._text.delete("1.0", "2.0")
        else:
            self._line_count += 1

        if tag:
            self._text.insert("end", line + "\n", tag)
        else:
            self._text.insert("end", line + "\n")

        self._text.configure(state="disabled")
        self._text.see("end")

    def clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")
        self._line_count = 0


class HealthScoreWidget(ctk.CTkFrame):
    """Circular-style health score display widget."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=BG_CARD, corner_radius=CARD_CORNER_RADIUS,
                          **kwargs)
        self._score = 0
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Network Health",
                      font=(FONT_FAMILY, FONT_SIZE_SMALL),
                      text_color=TEXT_MUTED).pack(pady=(12, 0))

        self._score_label = ctk.CTkLabel(
            self, text="--",
            font=(FONT_FAMILY, 40, "bold"),
            text_color=STATUS_OFFLINE,
        )
        self._score_label.pack()

        self._label_label = ctk.CTkLabel(
            self, text="No Data",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=STATUS_OFFLINE,
        )
        self._label_label.pack(pady=(0, 12))

    def update_score(self, score: int, label: str):
        from ui.theme import get_health_color
        color = get_health_color(score)
        self._score_label.configure(text=str(score), text_color=color)
        self._label_label.configure(text=label, text_color=color)
        self._score = score


class MiniSparkline(tk.Canvas):
    """
    Tiny sparkline chart for response time visualization.
    Uses standard tkinter Canvas for maximum compatibility.
    """

    def __init__(self, parent, width=200, height=40, line_color=None, **kwargs):
        bg = resolve_color(BG_CARD)
        super().__init__(parent, width=width, height=height,
                          bg=bg, highlightthickness=0, **kwargs)
        self._line_color = line_color or SAS_BLUE_LIGHT
        self._data = []
        self._width = width
        self._height = height

    def update_data(self, values: list):
        """Redraw with new data."""
        self._data = list(values)
        self.delete("all")
        if len(self._data) < 2:
            return

        mn = min(self._data)
        mx = max(self._data)
        if mx == mn:
            mx = mn + 1

        pts = []
        for i, v in enumerate(self._data):
            x = int(i / (len(self._data) - 1) * (self._width - 4)) + 2
            y = self._height - 4 - int((v - mn) / (mx - mn) * (self._height - 8))
            pts.append(x)
            pts.append(y)

        if len(pts) >= 4:
            self.create_line(*pts, fill=self._line_color, width=1.5, smooth=True)


def get_serial_ports() -> list:
    """Return available serial port names."""
    try:
        import serial.tools.list_ports
        ports = [p.device for p in serial.tools.list_ports.comports()]
        return sorted(ports) if ports else ["COM1", "COM2", "COM3"]
    except Exception:
        return ["COM1", "COM2", "COM3", "COM4", "COM5"]

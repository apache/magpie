#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Full-screen dimmed "touch your key" overlay, shown while gpg blocks.

Spawned by gpg-touch-overlay.sh; it draws nothing on its own schedule and
exits when killed, so the shell script stays the only thing that decides
when a touch is actually being waited for.

Shape of the thing: one translucent window per monitor, so the whole
desktop dims the way the pinentry PIN prompt dims it, with the prompt
drawn large enough to read from across the room. The contact ring pulses
because a still image reads as "an error happened", while motion reads as
"something is waiting for you".

Closes on Esc or a click — the key must still be touched for the command
to go through, so trapping the screen would buy nothing.
"""

import os
import signal
import sys

import cairo
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gdk, Gtk  # noqa: E402

TITLE = "Touch your security key"
SUBTITLE = "Your security key is waiting for a touch"
HINT = "The git command stays blocked until you touch the key   ·   Esc to dismiss"

# How much of the context the window will show. The watcher has already
# capped what it writes; these are display widths, chosen so a line stays
# on one row at the font sizes below rather than wrapping the layout.
COMMAND_MAX = 96
CWD_MAX = 72

DIM = (0.0, 0.0, 0.0, 0.76)
ACCENT = (0.96, 0.76, 0.16)  # amber, the colour these keys blink

# The canvas is deliberately wider than the widest ripple: a ripple that
# reaches the widget edge gets clipped into a lopsided smudge.
CANVAS_PX = 420
RIPPLES = 3
PULSE_MS = 33
PULSE_PERIOD = 1.9  # seconds, one ripple's whole travel

CSS = b"""
.touch-title    { color: #ffffff; font-size: 84px; font-weight: 800;
                  letter-spacing: 1px; }
.touch-subtitle { color: #dfe4ec; font-size: 36px; }
.touch-command  { color: #f5c229; font-size: 26px; font-family: monospace; }
.touch-cwd      { color: #8d96a4; font-size: 20px; font-family: monospace; }
.touch-hint     { color: #8d96a4; font-size: 22px; letter-spacing: 1px; }
"""


def elide(text, limit, keep="head"):
    """Cut *text* to *limit*, marking where it was cut.

    Which end survives is not the same question for the two lines. A
    command is identified by how it starts — ``git commit``, ``git
    push`` — so the head is kept; a path is identified by where it ends,
    since the leading components are the ones every checkout on the
    machine shares.
    """
    if len(text) <= limit:
        return text
    if keep == "tail":
        return "…" + text[-(limit - 1):]
    return text[: limit - 1] + "…"


def context():
    """The command this touch is blocking and the directory it runs in.

    Both come from the watcher, which read them from the file the arming
    hook wrote. Either being absent is normal and not an error: a
    wrapped signature outside an agent session has no hook payload
    behind it, and an older watcher passes nothing at all. The window
    simply drops the lines it has no text for.

    Control characters are stripped again here even though the watcher
    already flattened them. This process is handed its text through the
    environment, and a window that renders whatever is in a variable is
    worth one defensive pass.
    """
    raw_command = os.environ.get("MAGPIE_GPG_TOUCH_COMMAND", "")
    raw_cwd = os.environ.get("MAGPIE_GPG_TOUCH_CWD", "")
    command, cwd = (
        " ".join(value.split()) for value in (raw_command, raw_cwd)
    )
    home = os.path.expanduser("~")
    if home and (cwd == home or cwd.startswith(home + os.sep)):
        cwd = "~" + cwd[len(home):]
    return elide(command, COMMAND_MAX), elide(cwd, CWD_MAX, keep="tail")


TAU = 6.283185307179586


class Pulse(Gtk.DrawingArea):
    """A contact dot sending out ripples — the "touch here" affordance.

    Several ripples at staggered phases, rather than one: a single ring
    spends most of its cycle invisible, which reads as a stalled image
    instead of something actively waiting.
    """

    def __init__(self):
        super().__init__()
        self.phase = 0.0
        self.set_size_request(CANVAS_PX, CANVAS_PX)
        self.connect("draw", self.on_draw)
        GLib.timeout_add(PULSE_MS, self.tick)

    def tick(self):
        self.phase = (self.phase + PULSE_MS / 1000.0 / PULSE_PERIOD) % 1.0
        self.queue_draw()
        return True

    def on_draw(self, _widget, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        cx, cy = w / 2.0, h / 2.0
        base = min(w, h) / 2.0
        r, g, b = ACCENT

        # Repaint the dim under the animation. Only this widget is damaged
        # per frame, so the window's own dim pass does not run again and the
        # previous ripples would otherwise pile up as a smudge.
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(*DIM)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        dot = base * 0.24
        ring = base * 0.42

        for i in range(RIPPLES):
            travel = (self.phase + i / RIPPLES) % 1.0
            radius = ring + (base * 0.92 - ring) * travel
            # Fade in off the ring, then out, so nothing pops into view.
            alpha = 0.45 * min(1.0, travel * 6.0) * (1.0 - travel) ** 1.5
            cr.set_source_rgba(r, g, b, alpha)
            cr.set_line_width(base * 0.055)
            cr.arc(cx, cy, radius, 0, TAU)
            cr.stroke()

        glow = cairo.RadialGradient(cx, cy, dot * 0.4, cx, cy, ring * 1.5)
        glow.add_color_stop_rgba(0.0, r, g, b, 0.38)
        glow.add_color_stop_rgba(1.0, r, g, b, 0.0)
        cr.set_source(glow)
        cr.arc(cx, cy, ring * 1.5, 0, TAU)
        cr.fill()

        cr.set_source_rgba(r, g, b, 0.9)
        cr.set_line_width(base * 0.075)
        cr.arc(cx, cy, ring, 0, TAU)
        cr.stroke()

        cr.set_source_rgba(1.0, 0.88, 0.45, 1.0)
        cr.arc(cx, cy, dot, 0, TAU)
        cr.fill()


def build_content():
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
    box.set_halign(Gtk.Align.CENTER)
    box.set_valign(Gtk.Align.CENTER)

    box.pack_start(Pulse(), False, False, 0)
    command, cwd = context()
    # The context sits between the subtitle and the hint, and only when
    # there is any: the lines are what distinguishes two windows raised
    # minutes apart, and an empty row where a command should be reads as
    # a window that failed to load one.
    lines = [
        (TITLE, "touch-title", 14),
        (SUBTITLE, "touch-subtitle", 0),
    ]
    if command:
        lines.append((command, "touch-command", 22))
    if cwd:
        lines.append((f"in {cwd}", "touch-cwd", 0))
    lines.append((HINT, "touch-hint", 34))

    for text, css_class, pad in lines:
        # `label=` and never `set_markup`: the command is arbitrary text
        # that routinely contains `&&`, `<` and `>`, and Pango would
        # take those for markup and refuse to render the line.
        label = Gtk.Label(label=text)
        label.get_style_context().add_class(css_class)
        box.pack_start(label, False, False, pad)
    return box


def make_window(geometry):
    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_title(TITLE)
    win.set_decorated(False)
    win.set_skip_taskbar_hint(True)
    win.set_skip_pager_hint(True)
    win.set_keep_above(True)
    win.set_type_hint(Gdk.WindowTypeHint.SPLASHSCREEN)

    # An RGBA visual is what makes the dim translucent rather than a solid
    # black sheet. Without a compositor the window still works — it just
    # blacks the screen out instead of dimming it.
    visual = win.get_screen().get_rgba_visual()
    if visual is not None:
        win.set_visual(visual)
    win.set_app_paintable(True)
    win.connect("draw", on_draw_dim)

    win.move(geometry.x, geometry.y)
    win.resize(geometry.width, geometry.height)

    win.add(build_content())
    win.connect("destroy", Gtk.main_quit)
    win.connect("button-press-event", lambda *_: Gtk.main_quit())
    win.connect(
        "key-press-event",
        lambda _w, ev: Gtk.main_quit() if ev.keyval == Gdk.KEY_Escape else None,
    )
    win.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.KEY_PRESS_MASK)
    return win


def on_draw_dim(_widget, cr):
    cr.set_operator(cairo.OPERATOR_SOURCE)  # replace the desktop, don't blend
    cr.set_source_rgba(*DIM)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)  # children draw normally on top
    return False


def main():
    # Killed by the watcher the moment the touch lands, so the default
    # SIGTERM disposition is the normal way this process ends.
    signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())
    signal.signal(signal.SIGINT, lambda *_: Gtk.main_quit())

    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    display = Gdk.Display.get_default()
    if display is None:
        return 1

    windows = [
        make_window(display.get_monitor(i).get_geometry())
        for i in range(display.get_n_monitors())
    ]
    for win in windows:
        win.show_all()
        win.get_window().raise_()
    if windows:
        windows[0].present()

    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())

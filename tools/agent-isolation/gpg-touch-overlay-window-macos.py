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
"""Full-screen dimmed "touch your key" overlay for macOS.

The Aqua half of gpg-touch-overlay-window.py — same shape, a dimmed
desktop with a pulsing contact ring, drawn with Tk instead of GTK. A Mac
has no PyGObject and no zenity, so the GTK window and its zenity fallback
both leave nothing on screen there; Tk ships with the system python3.

Three differences are the platform's rather than choices:

  * **Main display only.** Aqua Tk reports one screen geometry and offers
    no per-monitor enumeration, so there is nothing to fan windows out
    over the way the GTK version does.
  * **`overrideredirect`, not `-fullscreen`.** A real fullscreen window
    gets its own Space and macOS animates the switch to it, pulling the
    terminal you are watching off screen. A borderless window placed over
    the display dims what is already there.
  * **The whole window is translucent.** Tk has no per-widget alpha, so
    the dim is the window's own `-alpha` and the text rides along at the
    same value. The text is sized and coloured to stay legible through
    it.

It also takes the keyboard while it is up. A touch that lands before the
key is asking for one fires the key's OTP slot, which types a burst of
characters and a Return into whatever has focus; while the overlay is
showing that should be the overlay, which ignores them — see
``take_focus``.

Closes on Esc or a click — the key must still be touched for the command
to go through, so trapping the screen would buy nothing.
"""

import ctypes
import ctypes.util
import os
import signal
import sys
import tkinter as tk

TITLE = "Touch your security key"
SUBTITLE = "Your security key is waiting for a touch"
HINT = "The git command stays blocked until you touch the key   ·   Esc to dismiss"

# How much of the context the window will show. The watcher has already
# capped what it writes; these are display widths, chosen so a line stays
# on one row at the font sizes below rather than wrapping the layout.
COMMAND_MAX = 96
CWD_MAX = 72

BG = (0, 0, 0)
BG_HEX = "#000000"
ACCENT = (245, 194, 41)  # amber, the colour these keys blink
CORE = (255, 224, 115)

# Aqua composites the window over the desktop, so this alpha is the dim
# itself. Deeper than the GTK fill (0.76) because the text dims with it.
WINDOW_ALPHA = 0.84

CANVAS_PX = 420
RIPPLES = 3
PULSE_MS = 33
PULSE_PERIOD = 1.9  # seconds, one ripple's whole travel
STOP_POLL_MS = 60

FONT = "Helvetica Neue"
MONO = "Menlo"


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


def blend(fg, bg, alpha):
    """Mix ``fg`` toward ``bg`` and return a Tk colour.

    Canvas items have no alpha channel, but everything here is drawn on a
    flat backdrop, so a faded stroke is exactly the colour mixed toward
    that backdrop.
    """
    alpha = max(0.0, min(1.0, alpha))
    return "#%02x%02x%02x" % tuple(
        int(round(f * alpha + b * (1.0 - alpha))) for f, b in zip(fg, bg)
    )


class Pulse(tk.Canvas):
    """A contact dot sending out ripples — the "touch here" affordance.

    Several ripples at staggered phases, rather than one: a single ring
    spends most of its cycle invisible, which reads as a stalled image
    instead of something actively waiting.
    """

    def __init__(self, master):
        super().__init__(
            master,
            width=CANVAS_PX,
            height=CANVAS_PX,
            bg=BG_HEX,
            highlightthickness=0,
        )
        self.phase = 0.0
        self.after(PULSE_MS, self.tick)

    def tick(self):
        self.phase = (self.phase + PULSE_MS / 1000.0 / PULSE_PERIOD) % 1.0
        self.redraw()
        self.after(PULSE_MS, self.tick)

    def circle(self, cx, cy, radius, **kwargs):
        self.create_oval(
            cx - radius, cy - radius, cx + radius, cy + radius, **kwargs
        )

    def redraw(self):
        self.delete("all")
        cx = cy = CANVAS_PX / 2.0
        base = CANVAS_PX / 2.0

        dot = base * 0.24
        ring = base * 0.42

        # The GTK version fades its glow with a radial gradient. Tk has no
        # gradient, so a handful of discs stepping toward the backdrop
        # stand in for one.
        for step in range(6, 0, -1):
            radius = ring * (1.0 + 0.5 * step / 6.0)
            self.circle(
                cx, cy, radius, fill=blend(ACCENT, BG, 0.06), outline=""
            )

        for i in range(RIPPLES):
            travel = (self.phase + i / RIPPLES) % 1.0
            radius = ring + (base * 0.92 - ring) * travel
            # Fade in off the ring, then out, so nothing pops into view.
            alpha = 0.45 * min(1.0, travel * 6.0) * (1.0 - travel) ** 1.5
            self.circle(
                cx,
                cy,
                radius,
                outline=blend(ACCENT, BG, alpha),
                width=base * 0.055,
            )

        self.circle(
            cx, cy, ring, outline=blend(ACCENT, BG, 0.9), width=base * 0.075
        )
        self.circle(cx, cy, dot, fill="#%02x%02x%02x" % CORE, outline="")


def take_focus(root):
    """Make this process the active application, then focus the window.

    Tk's ``focus_force`` cannot take the keyboard from another
    application on macOS by itself: a bare python process has no
    activation policy, so AppKit never considers it for activation.
    Giving it one and activating it through the Objective-C runtime is
    all it takes — done over ctypes so PyObjC is not needed. If AppKit
    is not there to talk to, the window still shows, just without the
    keyboard.
    """
    try:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/AppKit.framework/AppKit"
        )
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]

        def send(ret, *argtypes):
            return ctypes.cast(
                objc.objc_msgSend,
                ctypes.CFUNCTYPE(ret, ctypes.c_void_p, ctypes.c_void_p, *argtypes),
            )

        app = send(ctypes.c_void_p)(
            objc.objc_getClass(b"NSApplication"),
            objc.sel_registerName(b"sharedApplication"),
        )
        # NSApplicationActivationPolicyRegular
        send(ctypes.c_bool, ctypes.c_long)(
            app, objc.sel_registerName(b"setActivationPolicy:"), 0
        )
        send(None, ctypes.c_bool)(
            app, objc.sel_registerName(b"activateIgnoringOtherApps:"), True
        )
        root.lift()
        root.focus_force()
        root.update()
        active = send(ctypes.c_bool)(app, objc.sel_registerName(b"isActive"))
        key = send(ctypes.c_void_p)(app, objc.sel_registerName(b"keyWindow"))
    except (OSError, AttributeError, TypeError) as exc:
        root.lift()
        root.focus_force()
        active, key = f"unknown ({exc})", None
    # Stderr is /dev/null unless the watcher is logging, in which case
    # this is the line that says whether anything reached the screen.
    print(
        f"overlay: viewable={root.winfo_viewable()} geometry={root.winfo_geometry()}"
        f" app_active={active} key_window={bool(key)}"
        f" tk_focus={root.focus_displayof() is root}",
        file=sys.stderr,
        flush=True,
    )


def build_window():
    root = tk.Tk()
    root.title(TITLE)
    root.configure(bg=BG_HEX)

    # Borderless and placed by hand — see the module docstring on why this
    # is not a -fullscreen window.
    root.overrideredirect(True)
    root.attributes("-alpha", WINDOW_ALPHA)
    root.attributes("-topmost", True)
    root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")

    frame = tk.Frame(root, bg=BG_HEX)
    frame.place(relx=0.5, rely=0.5, anchor="center")

    Pulse(frame).pack()
    command, cwd = context()
    # The context sits between the subtitle and the hint, and only when
    # there is any: the lines are what distinguishes two windows raised
    # minutes apart, and an empty row where a command should be reads as
    # a window that failed to load one.
    lines = [
        (TITLE, (FONT, 64, "bold"), "#ffffff", (14, 0)),
        (SUBTITLE, (FONT, 28), "#dfe4ec", (18, 0)),
    ]
    if command:
        lines.append((command, (MONO, 20), "#f5c229", (26, 0)))
    if cwd:
        lines.append((f"in {cwd}", (MONO, 16), "#8d96a4", (6, 0)))
    lines.append((HINT, (FONT, 16), "#8d96a4", (34, 0)))

    for text, font, colour, pad in lines:
        tk.Label(
            frame, text=text, font=font, fg=colour, bg=BG_HEX
        ).pack(pady=pad)

    root.bind("<Escape>", lambda _event: root.destroy())
    root.bind("<Button-1>", lambda _event: root.destroy())

    # The window has to exist before the application can be activated
    # around it.
    root.update()
    take_focus(root)
    return root


def watch_for_stop(root, stopping):
    """End the loop once a termination signal has been seen.

    The watcher kills this process the instant the touch lands, but a
    signal arriving while Tk sits in its C event loop is only handled
    once Python runs again — and a handler that runs there cannot break
    out of ``mainloop`` on its own. This poll is what turns the flag into
    a closed window.
    """
    if stopping:
        root.destroy()
        return
    root.after(STOP_POLL_MS, watch_for_stop, root, stopping)


def main():
    stopping = []
    signal.signal(signal.SIGTERM, lambda *_: stopping.append(True))
    signal.signal(signal.SIGINT, lambda *_: stopping.append(True))

    root = build_window()
    watch_for_stop(root, stopping)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

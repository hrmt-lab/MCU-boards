# Top-level: generate the routed board.
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pcbnew
import place as P
import build as BD
from build import route_net, gnd_stub, emit, log
import render

t0 = time.time()
b = P.make()
BD.mechanics(b)
c = BD.setup(b)
g = c.g
pads = c.pads

# keep the bottom layer under the 32k crystal free of signals
g.block_rect([1], 6.4, 16.6, 10.4, 21.1)
# ... and under the boost converter (keep its ground return solid)
g.block_rect([1], 22.9, 9.3, 30.6, 13.4)
# no vias directly above the FPC pad rows (top-layer entry corridor)
sl, m = g.rect_mask(3.0, 21.2, 16.4, 23.7, 0); g.novia[sl] |= m

FAIL = []


def R(net, w=0.2, **kw):
    t = time.time()
    ok = route_net(c, net, w, **kw)
    log("%-28s %s %.1fs" % (net, "ok" if ok else "FAIL", time.time() - t))
    if not ok: FAIL.append(net)


def G(ref, pin, hint=None):
    if not gnd_stub(c, (ref, pin), hint):
        FAIL.append("GND:%s.%s" % (ref, pin))


def PXY(ref, pin):
    return pads[(ref, pin)]["xy"]


def merge(a, *others):
    for o in others:
        g.comp[g.comp == pads[o]["comp"]] = pads[a]["comp"]


def M(ref, pin, pts, w, layer=0, via=None):
    """manual polyline starting at a pad (local mm, grid-snapped); optional via at the end."""
    pd = pads[(ref, pin)]
    emit(c, pd["net"], [(layer, pts)], [pts[-1]] if via else [], w, via[0] if via else 0, via[1] if via else 0, pd["comp"])


def ESC(pin, dx, dy):
    """escape a module pad to a via."""
    pd = pads[("U1", pin)]
    x, y = pd["xy"]; x = round(x / 0.05) * 0.05; y = round(y / 0.05) * 0.05
    M("U1", pin, [(x, y), (x + dx, y + dy)], 0.2, via=(0.5, 0.25))


XL1, XL2 = "Net-(U1-P0.00{slash}XL1)", "Net-(U1-P0.01{slash}XL2)"

# ---- 0. hand-routed boost converter (short, wide, tight loops)
M("U4", "5", [(24.55, 10.6), (23.3, 10.6)], 0.3)                      # VOUT -> C10
merge(("U4", "5"), ("C10", "1"))
M("C10", "1", [(23.3, 10.6), (22.5, 10.6), (22.5, 16.4), (22.85, 16.75), (23.85, 16.75)], 0.3)   # boost output -> mux IN2
merge(("U4", "5"), ("U5", "6"))
M("U4", "2", [(26.0, 10.6), (27.45, 10.6)], 0.3)                      # SW -> L1
merge(("U4", "2"), ("L1", "2"))
M("U4", "3", [(26.0, 10.1), (25.3, 10.1), (25.3, 11.1), (26.0, 11.1)], 0.2)   # EN = VIN (under the IC)
M("L1", "1", [(29.65, 11.4), (29.65, 12.6)], 0.4)                     # VIN node -> C9
M("L1", "1", [(29.3, 11.4), (29.0, 12.0), (26.4, 12.0), (26.0, 11.6), (26.0, 11.1)], 0.2)   # VIN pin feed
merge(("L1", "1"), ("C9", "1"), ("U4", "3"), ("U4", "1"))
M("U4", "6", [(24.55, 11.1), (24.55, 11.45), (23.85, 12.15), (23.3, 12.15)], 0.25)   # GND return U4 -> C10
merge(("U4", "6"), ("C10", "2"))
M("C4", "2", [(7.15, 20.55), (8.4, 20.55), (9.65, 20.55)], 0.25)      # crystal load-cap ground
merge(("C4", "2"), ("C5", "2"))
emit(c, "GND", [], [(8.4, 20.55)], 0.25, 0.6, 0.3, pads[("C4", "2")]["comp"])

# ---- 1. ground vias for the power stage and decoupling (short loops)
G("U4", "6", (24.3, 13.1)); G("U4", "4", (24.6, 9.2)); G("C9", "2", (27.6, 13.6))
for ref, pin in (("U5", "1"), ("C11", "2"), ("U3", "1"), ("C6", "2"), ("C7", "2")):
    G(ref, pin)
G("C1", "2", (13.6, 20.4)); G("C2", "2", (15.6, 20.4))
M("U1", "15", [(6.8, 15.45), (6.8, 16.0), (7.0, 16.3)], 0.25, via=(0.6, 0.3)); G("U1", "33", (16.4, 16.5))
# FPC pins that are fed from the bottom layer: stub + via under the connector body (3 staggered rows)
ROW = {"A": 24.2, "B": 25.05, "C": 25.85}
for pin, row in (("1", "C"), ("4", "A"), ("6", "A"), ("8", "A"), ("10", "C"), ("11", "A"), ("13", "A"), ("15", "A"),
                 ("17", "C"), ("18", "A"), ("19", "B"), ("21", "A"), ("22", "B"), ("24", "A")):
    x, y = PXY("J6", pin); x = round(x / 0.05) * 0.05
    M("J6", pin, [(x, 22.9), (x, ROW[row])], 0.18, via=(0.5, 0.25))
x, y = PXY("J7", "1"); x = round(x / 0.05) * 0.05
M("J7", "1", [(x, 22.9), (x, 25.3)], 0.25, via=(0.6, 0.3))
# power mux U5 (rotated 180): outputs (7/2) and USB inputs (3/5) are linked under the IC body
M("U5", "7", [(23.85, 17.25), (25.35, 17.25)], 0.25); merge(("U5", "7"), ("U5", "2"))
M("U5", "3", [(25.35, 16.75), (25.0, 16.75), (24.2, 16.25), (23.85, 16.25)], 0.2); merge(("U5", "3"), ("U5", "5"))
M("U5", "7", [(23.85, 17.25), (23.1, 17.25), (22.7, 17.65), (22.7, 18.0)], 0.3); merge(("U5", "7"), ("C11", "1"))
M("C11", "1", [(22.45, 18.0), (22.45, 17.7), (22.05, 17.3), (22.05, 11.9), (20.5, 10.35), (19.9, 10.1)], 0.25); merge(("U5", "7"), ("J3", "1"))   # 3V3 -> SWD header (lane between R4 and the boost output)
M("U5", "4", [(25.35, 16.25), (26.0, 16.25), (26.3, 15.95), (26.6, 15.95)], 0.2)
M("R5", "2", [(26.6, 15.95), (26.6, 14.45)], 0.25); merge(("U5", "4"), ("R5", "2"), ("R6", "1"))
M("U5", "3", [(25.35, 16.75), (26.0, 16.75), (26.3, 17.05), (26.3, 17.6), (26.55, 17.85)], 0.25); merge(("U5", "3"), ("C7", "1"))
M("C7", "1", [(26.7, 17.85), (26.7, 19.7), (29.55, 22.55), (30.0, 22.55)], 0.3); merge(("C7", "1"), ("U3", "2"))   # LDO out -> mux
# module supply pins straight into their decoupling caps
M("U1", "28", [(13.2, 15.45), (13.2, 16.2), (13.6, 16.6), (13.6, 17.5)], 0.25)
M("U1", "30", [(14.0, 15.45), (14.0, 16.2), (13.6, 16.6)], 0.25)
merge(("U1", "28"), ("U1", "30"), ("C1", "1"))
M("U1", "32", [(15.6, 15.45), (15.6, 17.5)], 0.25)
merge(("U1", "32"), ("C2", "1"))
M("U1", "32", [(15.6, 17.5), (16.7, 17.5)], 0.3, via=(0.6, 0.3))       # VBUS feed via next to C2

# ---- 2. crystal
R(XL1, allow_via=False); R(XL2, allow_via=False)

# ---- 3. module escapes
for pin in ("5", "7", "9", "11"): ESC(pin, 0.9, 0)                     # left inner row -> bottom layer
for pin in ("19", "21", "23", "25", "27"): ESC(pin, 0, -0.9)           # bottom inner row -> bottom layer
ESC("43", -1.4, 0); ESC("42", -2.1, 0); ESC("40", -0.7, 0)             # right inner row, staggered
ESC("34", 1.25, 0); ESC("35", 1.25, 0)                                 # USB D-/D+ -> bottom layer
ESC("44", 1.35, 0)                                                     # LED
# P0.12 (inner pin 29) leaves on the top layer through the corner gap between pins 33 and 34
M("U1", "29", [(13.6, 14.55), (15.4, 14.55), (15.75, 14.9), (16.95, 14.9), (17.3, 15.25)], 0.15)

# ---- 4. GPIO, top layer only
TOP = dict(allow_via=False)
for n in ("P0.04", "P0.06", "P0.08", "P1.09"):
    R(n, **TOP)
for n in ("P0.29", "P1.15", "P1.13", "P1.11", "P1.10"):
    R(n, **TOP)
# J7 signals: hand-placed lanes right of the module, then east above the J7 pad row
M("U1", "29", [(17.3, 15.25), (17.3, 20.3), (18.8, 21.8), (23.25, 21.8), (23.25, 22.9)], 0.2); merge(("U1", "29"), ("J7", "2"))
M("U1", "37", [(16.25, 12.85), (18.05, 12.85), (18.05, 19.9), (19.55, 21.4), (23.75, 21.4), (23.75, 22.9)], 0.2); merge(("U1", "37"), ("J7", "3"))
M("U1", "39", [(16.25, 12.05), (18.45, 12.05), (18.45, 19.5), (19.95, 21.0), (24.25, 21.0), (24.25, 22.9)], 0.2); merge(("U1", "39"), ("J7", "4"))
M("U1", "41", [(16.25, 11.25), (18.85, 11.25), (18.85, 19.1), (20.35, 20.6), (24.75, 20.6), (24.75, 22.9)], 0.2); merge(("U1", "41"), ("J7", "5"))

# ---- 5. GPIO via the bottom layer, coming up under the FPC connector body
NV = np.zeros_like(g.novia); sl, m = g.rect_mask(3.0, 15.9, 17.2, 23.7, 0); NV[sl] |= m
BOT = dict(layer_cost=(8, 0), novia_extra=NV)
for n in ("P0.26", "P0.05", "P0.07", "P1.08", "P0.11", "P0.03", "P1.14", "P1.12", "P0.19", "P0.21"):
    R(n, **BOT)
R("RESET", order=[("U1", "40"), ("J6", "24")], **BOT)
R("BAT_MON", order=[("U1", "11"), ("C8", "1"), ("R4", "1"), ("R3", "2")], layer_cost=(8, 0))
R("DBG_LED", layer_cost=(8, 0))
R("SWDIO", **TOP); R("SWDCLK", **TOP)
R("Net-(Q1-S)", 0.4, order=[("L1", "1"), ("Q1", "2")])
R("Net-(Q1-S)", 0.2, order=[("L1", "1"), ("R3", "1")], layer_cost=(6, 0))
R("USB_DM", layer_cost=(4, 0)); R("USB_DP", layer_cost=(4, 0))

# ---- 6. battery path / boost outputs
R("Net-(Q1-D)", 0.5)
R("Net-(SW2-C)", 0.5)
R("Net-(J5-Pin_1)", 0.5)

# ---- 7. USB + 3V3 distribution
R("SYS_3V3", 0.3, order=[("U5", "7"), ("U1", "28"), ("J7", "6"), ("J6", "23"), ("J3", "1")])
R("USB_5V", 0.3, order=[("J2", "1"), ("U3", "3"), ("C6", "1"), ("R5", "1"), ("U1", "32")])
R("RESET")
R("Net-(D1-A)")

# ---- 8. remaining ground pads
HINT = {("U1", "55"): (17.3, 4.9), ("U1", "1"): (5.8, 4.9), ("U1", "2"): (5.6, 5.65)}
for key in c.netpads["GND"]:
    pd = pads[key]
    if pd["layers"] != [0]: continue
    comp = int(g.comp[0][int(round(pd["xy"][1] / 0.05)), int(round(pd["xy"][0] / 0.05))])
    if any(int(g.comp[0][int(round(v[2] / 0.05)), int(round(v[1] / 0.05))]) == comp for v in c.vias if v[0] == "GND"): continue
    hint = HINT.get(key)
    if key[0] in ("J6", "J7"): hint = (pd["xy"][0], pd["xy"][1] + 1.6)
    G(key[0], key[1], hint)

import finish as FN
BD.write_copper(c)
st = FN.add_stitch(c, FN.stitch_candidates(c))
log("USB stubs removed:", FN.usb_cleanup(b))
BD.add_zones(b)
BD.fill(b)
log("stitching vias kept: %d of %d" % (FN.prune_stitch(b, st), len(st)))
FN.silk(b)
BD.fill(b)
b.Save(P.OUT)
log("saved; fails:", FAIL, "time %.0fs" % (time.time() - t0))
render.render(P.OUT, os.path.join(P.HERE, "r.png"), 27.5, 31.5, 68.5, 60.5, 34)

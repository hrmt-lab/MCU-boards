# Top-level: generate the routed board.
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pcbnew
import place as P
import build as BD
from build import route_net, gnd_stub, emit, log
import render

import guard as GUARD
GUARD.check(P.OUT)                       # stop before the long build if the board was edited in KiCad
t0 = time.time()
b = P.make()
BD.mechanics(b)
c = BD.setup(b)
g = c.g
pads = c.pads

# keep the bottom layer under the 32k crystal free of signals
g.block_rect([1], 6.4, 16.6, 10.4, 21.1)
# ... and under the boost converter (keep its ground return solid)
g.block_rect([1], 22.9, 6.9, 30.6, 11.0)
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
M("U4", "5", [(24.55, 8.2), (23.3, 8.2)], 0.3)                        # VOUT -> C10
merge(("U4", "5"), ("C10", "1"))
M("C10", "1", [(23.3, 8.2), (22.5, 8.2), (22.5, 16.4), (22.85, 16.75), (23.85, 16.75)], 0.3)   # boost output -> mux IN2
merge(("U4", "5"), ("U5", "6"))
M("U4", "2", [(26.0, 8.2), (27.45, 8.2)], 0.3)                        # SW -> L1
merge(("U4", "2"), ("L1", "2"))
M("U4", "3", [(26.0, 7.7), (25.3, 7.7), (25.3, 8.7), (26.0, 8.7)], 0.2)   # EN = VIN (under the IC)
# Rev I: input loop C9 -> L1 / U4 VIN kept short; C9 sits right under U4 and returns to the U4 GND pins
M("Q1", "2", [(24.45, 5.04), (25.25, 5.84), (28.9, 5.84), (29.62, 6.56), (29.62, 8.2)], 0.5)   # battery (after Q1) -> L1 input
merge(("L1", "1"), ("Q1", "2"))
M("L1", "1", [(29.4, 9.0), (27.95, 10.45), (26.58, 10.45)], 0.5)      # L1 input -> C9 (+)
merge(("L1", "1"), ("C9", "1"))
M("U4", "1", [(26.01, 8.7), (26.01, 9.55), (26.5, 10.04), (26.58, 10.45)], 0.3)   # U4 VIN -> C9 (+)
merge(("L1", "1"), ("U4", "1"), ("U4", "3"))
M("U4", "6", [(24.55, 8.7), (24.55, 9.05), (23.85, 9.75), (23.3, 9.75)], 0.25)   # GND return U4 -> C10
merge(("U4", "6"), ("C10", "2"))
M("C9", "2", [(25.03, 10.45), (24.55, 9.97), (24.55, 9.05)], 0.4)    # C9 (-) straight back to the U4 GND pin
merge(("U4", "6"), ("C9", "2"))
M("C4", "2", [(7.15, 20.55), (8.4, 20.55), (9.65, 20.55)], 0.25)      # crystal load-cap ground
merge(("C4", "2"), ("C5", "2"))
emit(c, "GND", [], [(8.4, 20.55)], 0.25, 0.6, 0.3, pads[("C4", "2")]["comp"])

# ---- 1. ground vias for the power stage and decoupling (short loops)
G("U4", "6", (23.85, 11.0)); G("U4", "6", (25.1, 11.55)); G("U4", "4", (24.6, 6.8))   # 2nd via next to C9 (-) (C9-2 is merged into U4-6)
G("Q1", "1", (22.55, 6.3))                                         # J8 (PH, THT) needs no GND via
for ref, pin in (("U5", "1"), ("C11", "2")):
    G(ref, pin)
# Rev I: LDO U3 (rot 0: GND/OUT on the left, IN on the right) with C7 (out) left of it and C6 (in) above it
M("U3", "2", [(29.96, 13.15), (28.2, 13.15)], 0.3); merge(("U3", "2"), ("C7", "1"))          # OUT -> C7 (+)
M("U3", "1", [(29.96, 11.25), (29.6, 11.6), (28.2, 11.6)], 0.3); merge(("U3", "1"), ("C7", "2"))   # GND -> C7 (-)
G("U3", "1", (30.5, 10.2))
M("C6", "1", [(P.W - 1.1, 9.675), (P.W - 1.1, 12.2)], 0.4); merge(("C6", "1"), ("U3", "3"))   # C6 (+) -> IN
G("C6", "2", (P.W - 1.1, 7.2)); G("J2", "4", (P.W - 3.8, 16.5))
M("C8", "2", [(20.0, 12.77), (21.3, 12.77)], 0.25); merge(("C8", "2"), ("R4", "2"))   # divider ground: one via
G("C8", "2", (20.65, 11.85))
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
M("C11", "1", [(22.45, 18.0), (22.45, 17.7), (22.05, 17.3), (22.05, 11.9), (21.3, 11.15), (19.9, 11.15), (19.4, 10.65), (19.4, 10.1)], 0.25); merge(("U5", "7"), ("J3", "1"))   # 3V3 -> SWD header (lane between R4 and the boost output)
M("R6", "1", [(25.42, 12.9), (25.42, 14.5)], 0.25); merge(("R6", "1"), ("R5", "2"))                   # PR1 divider node (R5 under R6)
M("R5", "2", [(25.42, 14.5), (25.42, 16.25)], 0.2); merge(("U5", "4"), ("R6", "1"), ("R5", "2"))
# Rev I: LDO output (C7) -> mux IN1, past the J2 pins
M("C7", "1", [(28.2, 13.175), (26.6, 14.775), (26.6, 16.4), (26.25, 16.75), (25.34, 16.75)], 0.3); merge(("U5", "3"), ("C7", "1"))
# module supply pins straight into their decoupling caps
M("U1", "28", [(13.2, 15.45), (13.2, 16.2), (13.6, 16.6), (13.6, 17.5)], 0.25)
M("U1", "30", [(14.0, 15.45), (14.0, 16.2), (13.6, 16.6)], 0.25)
merge(("U1", "28"), ("U1", "30"), ("C1", "1"))
M("U1", "32", [(15.6, 15.45), (15.6, 17.5)], 0.25)
merge(("U1", "32"), ("C2", "1"))
M("U1", "32", [(15.6, 17.5), (16.7, 17.5)], 0.3, via=(0.6, 0.3))       # VBUS feed via next to C2

R("USB_3.3V", 0.3, order=[("U5", "3"), ("U3", "2")])                    # (already joined by hand)

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

# Rev F: battery sense tap before USB D+/D- (they would wall off R3 on the bottom layer)
R("Net-(Q1-S)", 0.2, order=[("L1", "1"), ("R3", "1")], layer_cost=(6, 0))
R("DBG_LED", layer_cost=(8, 0))
R("USB_DP", layer_cost=(4, 0)); R("USB_DM", layer_cost=(4, 0))

# ---- 5. GPIO via the bottom layer, coming up under the FPC connector body
NV = np.zeros_like(g.novia); sl, m = g.rect_mask(3.0, 15.9, 17.2, 23.7, 0); NV[sl] |= m
BOT = dict(layer_cost=(8, 0), novia_extra=NV)
for n in ("P0.26", "P0.05", "P0.07", "P1.08", "P0.11", "P0.03", "P1.14", "P1.12", "P0.19", "P0.21"):
    R(n, **BOT)
R("RESET", order=[("U1", "40"), ("J6", "24"), ("J3", "4"), ("SW1", "1")], **BOT)
R("BAT_MON", order=[("U1", "11"), ("C8", "1"), ("R4", "1"), ("R3", "2")], layer_cost=(8, 0))
R("SWDIO", **TOP); R("SWDCLK", **TOP)
R("Net-(Q1-S)", 0.4, order=[("L1", "1"), ("Q1", "2")])

# ---- 6. battery path / boost outputs
R("VBAT_IN", 0.5, order=[("Q1", "3"), ("J8", "1")])                    # battery connector -> reverse-polarity FET

# ---- 7. USB + 3V3 distribution
R("SYS_3V3", 0.3, order=[("U5", "7"), ("U1", "28"), ("J7", "6"), ("J6", "23"), ("J3", "1")])
R("USB_5V", 0.3, order=[("J2", "1"), ("U3", "3"), ("C6", "1"), ("R5", "1"), ("U1", "32")])
R("Net-(D1-A)")

# ---- 8. remaining ground pads
HINT = {("J2", "4"): (P.W - 3.8, 16.3), ("U1", "55"): (17.3, 4.9), ("U1", "1"): (5.8, 4.9), ("U1", "2"): (5.6, 5.65)}
for key in c.netpads["GND"]:
    pd = pads[key]
    if pd["layers"] != [0]: continue
    comp = int(g.comp[0][int(round(pd["xy"][1] / 0.05)), int(round(pd["xy"][0] / 0.05))])
    if any(int(g.comp[0][int(round(v[2] / 0.05)), int(round(v[1] / 0.05))]) == comp for v in c.vias if v[0] == "GND"): continue
    hint = HINT.get(key)
    if key[0] in ("J6", "J7"): hint = (pd["xy"][0], pd["xy"][1] + 1.6)
    G(key[0], key[1], hint)

import finish as FN
import battery as BAT
BD.write_copper(c)
st = FN.add_stitch(c, FN.stitch_candidates(c))
log("USB stubs removed:", FN.usb_cleanup(b))
log("USB tracks redrawn (45 deg):", FN.usb_route(b))
FN.fix_joins(b)
BD.add_zones(b)
if P.BATTERY_ON_PANEL: BAT.build(b)
BD.fill(b)
log("stitching vias kept: %d of %d" % (FN.prune_stitch(b, st), len(st)))
if P.BATTERY_ON_PANEL: log("battery stitching vias kept: %d" % BAT.prune(b))
FN.silk(b)
BD.fill(b)
GUARD.save_board(b, P.OUT)
log("saved; fails:", FAIL, "time %.0fs" % (time.time() - t0)); log("unchamfered corners:", len(BD.NOCHAMFER), BD.NOCHAMFER[:20])
render.render(P.OUT, os.path.join(P.HERE, "r.png"), P.OX - 0.5, P.OY - 0.5, (P.BX + P.BW if P.BATTERY_ON_PANEL else P.RAIL_X1) + 0.5, P.OY + P.H + 0.5, 34)

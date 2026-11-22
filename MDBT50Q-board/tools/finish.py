# Finishing steps: stitching vias, USB daughter-board cleanup, silkscreen.
import math, re
import numpy as np
import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM
import place as P
import build as BD
from router import RES

F, B = pcbnew.F_Cu, pcbnew.B_Cu


def stitch_candidates(c, pitch=2.0, min_dist=1.3):
    """GND stitching vias on a grid wherever a 0.6/0.3 via is legal."""
    g = c.g; n = c.netid["GND"]
    blk, vb = g.masks(n, 0.25, 0.6)
    out = []
    xs = np.arange(0.9, P.W - 0.8, pitch / 2)
    ys = np.arange(4.9, P.H - 0.8, pitch / 2)
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            if (i + j) % 2: continue                       # staggered grid
            ix, iy = int(round(x / RES)), int(round(y / RES))
            if vb[iy, ix] or blk[0][iy, ix] or blk[1][iy, ix]: continue
            if 6.0 < x < 17.2 and y < 16.3: continue           # nothing extra under the RF module
            if any(math.hypot(x - v[1], y - v[2]) < min_dist for v in c.vias): continue
            if any(math.hypot(x - o[0], y - o[1]) < pitch * 0.9 for o in out): continue
            out.append((round(float(x), 2), round(float(y), 2)))
    return out


def add_stitch(c, pts):
    vs = []
    b = c.b
    for x, y in pts:
        v = pcbnew.PCB_VIA(b); v.SetPosition(BD.V(x, y)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(F, B); v.SetWidth(F, FromMM(0.6)); v.SetDrill(FromMM(0.3)); v.SetNet(b.FindNet("GND")); b.Add(v)
        vs.append(v)
    return vs


def prune_stitch(b, vs):
    """drop stitching vias that do not land in filled copper on both layers."""
    zones = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND"]
    kept = 0
    for v in vs:
        ok = all(any(z.IsOnLayer(L) and z.HitTestFilledArea(L, v.GetPosition(), FromMM(0.0)) for z in zones) for L in (F, B))
        if ok: kept += 1
        else: b.RemoveNative(v)
    return kept


def usb_cleanup(b):
    """remove the stubs that led to the deleted USB test pads (iteratively drop dangling ends)."""
    y0 = FromMM(70.0)
    removed = 0
    while True:
        tracks = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetStart().y > y0]
        vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetPosition().y > y0]
        pads = [p for f in b.GetFootprints() for p in f.Pads() if p.GetPosition().y > y0]

        def connected(pt, layer, me):
            for p in pads:
                if p.IsOnLayer(layer) and p.HitTest(pt): return True
            for v in vias:
                if v is not me and (v.GetPosition() - pt).EuclideanNorm() <= v.GetWidth(F) // 2: return True
            for t in tracks:
                if t is me or t.GetLayer() != layer: continue
                if t.HitTest(pt): return True
            return False
        rm = []
        for t in tracks:
            if not connected(t.GetStart(), t.GetLayer(), t) or not connected(t.GetEnd(), t.GetLayer(), t):
                rm.append(t)
        for v in vias:
            if v.GetNetname() == "USB_PORT_GND": continue
            n = 0
            for L in (F, B):
                pt = v.GetPosition()
                if any(p.IsOnLayer(L) and p.HitTest(pt) for p in pads) or any(t.GetLayer() == L and t.HitTest(pt) for t in tracks):
                    n += 1
            if n < 2: rm.append(v)
        rm += [t for t in tracks if t.GetLength() < FromMM(0.1) and t not in rm and not any(p.HitTest(t.GetStart()) for p in pads)]
        if not rm: break
        for it in rm:
            b.RemoveNative(it); removed += 1
    return removed


# Rev K: the USB board signal tracks (inherited from cdx) had right-angle bends, T-joins at 90 degrees and
# overlapping stubs. They are replaced here by the same topology drawn with 45-degree bends only.
# Absolute panel coordinates (mm). GND stubs and all vias are kept as they were.
USB_ROUTES = [
    # D+ : J1 B6/A6 joined below the pad row, then to U2-1
    ("Net-(J1-D+-PadA6)", F, 0.2, [(53.75, 77.395), (53.75, 78.25), (53.45, 78.55), (48.3, 78.55), (47.35, 77.6)]),
    ("Net-(J1-D+-PadA6)", F, 0.2, [(52.75, 77.395), (52.75, 78.25), (52.45, 78.55)]),
    # D- : J1 B7 joins A7 at 45 degrees above the pad row, then to U2-3
    ("Net-(J1-D--PadA7)", F, 0.2, [(53.25, 77.395), (53.25, 74.95), (52.95, 74.65), (48.55, 74.65), (47.6, 75.6), (47.237, 75.6)]),
    ("Net-(J1-D--PadA7)", F, 0.2, [(54.25, 77.395), (54.25, 76.5), (53.25, 75.5)]),
    # U2 -> J4 (D-, D+)
    ("USB_PORT_DM", F, 0.2, [(44.962, 75.6), (44.65, 75.6), (44.05, 75.0), (44.05, 73.85), (43.45, 73.25), (40.2, 73.25), (39.6, 73.85), (39.6, 74.65)]),
    ("USB_PORT_DP", F, 0.2, [(44.962, 77.5), (44.05, 77.5), (43.6, 77.05), (41.0, 77.05), (40.6, 76.65), (40.6, 74.65)]),
    # CC1 / CC2 -> R2 / R1 (top -> via -> bottom -> via -> top)
    ("Net-(J1-CC2)", F, 0.2, [(51.75, 77.395), (51.75, 76.55), (52.4, 75.9), (52.4, 75.45)]),
    ("Net-(J1-CC2)", B, 0.2, [(52.4, 75.45), (52.4, 74.75), (52.0, 74.35), (46.1, 74.35)]),
    ("Net-(J1-CC2)", F, 0.2, [(46.1, 74.35), (46.1, 73.46)]),
    ("Net-(J1-CC1)", F, 0.2, [(54.75, 77.395), (54.75, 75.55)]),
    ("Net-(J1-CC1)", B, 0.2, [(54.75, 75.55), (54.75, 74.0), (54.35, 73.6), (48.2, 73.6)]),
    ("Net-(J1-CC1)", F, 0.2, [(48.2, 73.6), (47.25, 73.6)]),
    # VBUS: J1 A4/B9 and A9/B4 -> bottom bus -> U2-5 and J4-1 / C3
    ("USB_PORT_5V", F, 0.3, [(55.95, 77.395), (55.95, 79.3)]),
    ("USB_PORT_5V", F, 0.2, [(51.05, 77.395), (51.05, 76.75), (51.3, 76.5), (51.3, 75.4)]),
    ("USB_PORT_5V", B, 0.25, [(51.3, 75.4), (51.7, 75.8), (51.7, 78.9), (52.1, 79.3)]),
    ("USB_PORT_5V", B, 0.3, [(55.95, 79.3), (42.1, 79.3), (38.6, 75.8), (38.6, 73.15)]),
    ("USB_PORT_5V", B, 0.3, [(46.1, 76.55), (46.1, 78.9), (46.5, 79.3)]),
    ("USB_PORT_5V", F, 0.25, [(46.1, 76.55), (44.962, 76.55)]),
    ("USB_PORT_5V", F, 0.3, [(38.6, 74.65), (38.6, 72.91), (39.16, 72.35)]),
]


def usb_route(b, y0=66.0):
    """replace the USB board signal tracks by USB_ROUTES (45-degree bends only)."""
    nets = {n for n, *_ in USB_ROUTES}
    rm = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetname() in nets
          and min(t.GetStart().y, t.GetEnd().y) > FromMM(y0)]
    for t in rm:
        b.RemoveNative(t)
    for net, layer, w, pts in USB_ROUTES:
        for (xa, ya), (xc, yc) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(VECTOR2I(FromMM(xa), FromMM(ya))); t.SetEnd(VECTOR2I(FromMM(xc), FromMM(yc)))
            t.SetLayer(layer); t.SetWidth(FromMM(w)); t.SetNet(b.FindNet(net)); b.Add(t)
    return len(rm)


def retrack(b, net, layer, old, new_pts):
    """replace the one track old=((xa, ya), (xb, yb)) (absolute mm) by the polyline new_pts (same width)."""
    key = {tuple(round(v, 3) for v in q) for q in old}
    hit = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA" and t.GetNetname() == net and t.GetLayer() == layer
           and {(round(ToMM(t.GetStart().x), 3), round(ToMM(t.GetStart().y), 3)), (round(ToMM(t.GetEnd().x), 3), round(ToMM(t.GetEnd().y), 3))} == key]
    assert len(hit) == 1, (net, old, len(hit))
    w = hit[0].GetWidth(); b.RemoveNative(hit[0])
    for (xa, ya), (xc, yc) in zip(new_pts, new_pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(VECTOR2I(FromMM(xa), FromMM(ya))); t.SetEnd(VECTOR2I(FromMM(xc), FromMM(yc)))
        t.SetLayer(layer); t.SetWidth(w); t.SetNet(b.FindNet(net)); b.Add(t)


def fix_joins(b):
    """Rev K: SYS_3V3 under U1: the U1-28 and U1-30 branches met at 90 degrees (V) above C1.
    U1-30 now runs down and joins the stem to C1 at 45 degrees."""
    X, Y = P.OX, P.OY
    retrack(b, "SYS_3V3", F, ((X + 14.0, Y + 16.2), (X + 13.6, Y + 16.6)),
            [(X + 14.0, Y + 16.2), (X + 14.0, Y + 16.6), (X + 13.6, Y + 17.0)])


def poly(b, pts, layer, w=0.15):
    for (xa, ya), (xc, yc) in zip(pts, pts[1:]):
        sh = pcbnew.PCB_SHAPE(b); sh.SetShape(pcbnew.SHAPE_T_SEGMENT)
        sh.SetStart(BD.VA(xa, ya)); sh.SetEnd(BD.VA(xc, yc)); sh.SetLayer(layer); sh.SetWidth(FromMM(w)); b.Add(sh)


def text(b, s, x, y, layer=pcbnew.F_SilkS, h=1.0, angle=0, absolute=False, thick=0.15):
    t = pcbnew.PCB_TEXT(b); t.SetText(s)
    t.SetPosition(BD.VA(x, y) if absolute else BD.V(x, y))
    t.SetLayer(layer); t.SetTextSize(VECTOR2I(FromMM(h), FromMM(h))); t.SetTextThickness(FromMM(thick))
    if angle: t.SetTextAngleDegrees(angle)
    if layer in (pcbnew.B_SilkS, pcbnew.B_Fab): t.SetMirrored(True)
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER); t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    b.Add(t)
    return t


def dim(b, x0, y0, x1, y1, h, layer=pcbnew.Dwgs_User):
    """aligned dimension (absolute mm) on User.Drawings (not fabricated). h > 0 puts the line on the right-hand
    side of start -> end (y down): left -> right = below, top -> bottom = left."""
    d = pcbnew.PCB_DIM_ALIGNED(b)
    d.SetLayer(layer)
    d.SetStart(VECTOR2I(FromMM(x0), FromMM(y0))); d.SetEnd(VECTOR2I(FromMM(x1), FromMM(y1)))
    d.SetHeight(FromMM(h))
    d.SetUnitsMode(pcbnew.DIM_UNITS_MODE_MM); d.SetUnitsFormat(pcbnew.DIM_UNITS_FORMAT_BARE_SUFFIX)
    d.SetPrecision(pcbnew.DIM_PRECISION_X_X); d.SetSuppressZeroes(False)
    d.SetLineThickness(FromMM(0.1)); d.SetTextSize(VECTOR2I(FromMM(1.0), FromMM(1.0))); d.SetTextThickness(FromMM(0.15))
    d.SetArrowLength(FromMM(1.0)); d.SetExtensionOffset(FromMM(0.5))
    d.SetTextPositionMode(pcbnew.DIM_TEXT_POSITION_OUTSIDE); d.SetKeepTextAligned(True)
    d.Update(); b.Add(d)
    return d


def outline_dims(b):
    """Rev K: outline dimensions of the panel (MCU board, USB board, whole panel) on User.Drawings."""
    x0, y0, x1, y1 = P.OX, P.OY, P.OX + P.W, P.OY + P.H                 # MCU board 33.3 x 27.8
    ux0, ux1, uy0, uy1 = P.RAIL_X0, P.RAIL_X1, 71.0, 80.0                # USB board 36 x 9 (= panel width)
    dim(b, x0, y0, x1, y0, -3.0)                                         # MCU width (above)
    dim(b, x0, y0, x0, y1, 3.0)                                          # MCU height (left)
    dim(b, x0, y0, x0, uy1, 7.0)                                         # panel height (further left)
    dim(b, ux0, uy1, ux1, uy1, 3.0)                                      # USB board / panel width (below)
    dim(b, ux1, uy0, ux1, uy1, -3.0)                                     # USB board height (right)


def lb(t):
    """left / bottom justification (as the user's hand-placed legends)."""
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT); t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_BOTTOM)
    return t


def refs_to_fab(b):
    # reference designators go to the fabrication layer (dense board; PCBA does not need them on silk)
    for f in b.GetFootprints():
        r = f.Reference()
        if re.match(r"^(MB|TOOL|FID|H)\d+$", f.GetReference()):
            r.SetVisible(False); continue
        r.SetLayer(pcbnew.B_Fab if f.IsFlipped() else pcbnew.F_Fab)
        r.SetTextSize(VECTOR2I(FromMM(0.6), FromMM(0.6))); r.SetTextThickness(FromMM(0.1))
        r.SetPosition(f.GetBoundingBox(False).Centre()); r.SetVisible(True)


def battery_silk(b):
    S, BS = pcbnew.F_SilkS, pcbnew.B_SilkS
    bx, by = P.BX, P.BY
    T = lambda s, x, y, layer=S, h=1.0: text(b, s, bx + x, by + y, layer, h=h, absolute=True)
    # cell outlines between the clips, with polarity (cell 1: BT1-BT2, cell 2: BT3-BT4)
    for x0 in (0.0, 48.0):
        poly(b, [(bx + x0 + a, by + c) for a, c in ((24.2, 1.9), (50.8, 1.9), (50.8, 12.1), (24.2, 12.1), (24.2, 1.9))], S)
        T("-", x0 + 26.4, P.CELL_Y, h=2.0); T("+", x0 + 48.6, P.CELL_Y, h=2.0); T("AAA", x0 + 37.5, P.CELL_Y, h=1.5)
    T("ON", 4.6, 6.75, h=0.8); T("OFF", 11.6, 6.75, h=0.8)                  # SW2 lever (top edge)
    T("MDBT50Q-board BATTERY  Rev G", 37.5, 4.2, BS); T("2x AAA ONLY   NO LiPo", 37.5, 9.8, BS)
    T("J9: 1=BAT+ 2=GND", 85.5, 4.2, BS); T("CELL 1 | CELL 2 in series", 85.5, 9.8, BS)


def silk(b, battery=P.BATTERY_ON_PANEL):
    refs_to_fab(b)
    S = pcbnew.F_SilkS
    # Rev K: front legends as the user edited them in KiCad (saved 2026-11-22 20:41; absolute mm)
    text(b, "RST", 31.65, 48.2, h=0.8, absolute=True, thick=0.1)         # SW1
    text(b, "SWD", 48.5, 35.0, h=0.8, absolute=True, thick=0.1)          # J3
    text(b, "1", 19.0, 11.75, h=0.8)                                      # J3 (pin 1 at the bottom)
    for s_, x, y, a in (("BAT", 53.97, 34.31, 90), ("USB", 59.83, 55.94, 90),              # J8 / J2 names
                        ("GND", 55.0, 48.11, 0), ("D+", 55.05, 50.19, 0), ("D-", 55.04, 51.25, 0), ("5V", 55.04, 52.77, 0),  # J2 pins
                        ("5V", 37.0, 73.75, 0), ("-", 39.1, 73.46, 0), ("+", 40.26, 73.47, 0), ("GND", 41.37, 73.55, 0)):   # USB board J4 pins
        lb(text(b, s_, x, y, h=0.8, angle=a, absolute=True, thick=0.1))
    x8, y8 = P.PLACE["J8"][:2]
    text(b, "+", x8 - 1.55, y8, h=0.9); text(b, "-", x8 - 1.55, y8 - 2.0, h=0.9)   # J8 polarity left of the pins
    # (Rev K: the front J6 / J7 names were removed by the user; the back ones stay)
    # back side legends
    BS = pcbnew.B_SilkS
    text(b, "MDBT50Q-board", 11.6, 8.0, BS)
    text(b, "Rev K  2L 1.2mm", 11.6, 9.8, BS)
    text(b, "BAT: 1=BAT+ 2=GND", P.W - 6.6, 5.9, BS, h=0.8)
    text(b, "SWD 1=3V3 2=IO", 23.6, 11.4, BS, h=0.8); text(b, "3=CLK 4=RST 5=GND", 23.6, 12.7, BS, h=0.8)
    text(b, "USB: 1=5V 2=D-", 53.48, 54.17, BS, h=0.8, absolute=True); text(b, "3=D+ 4=GND", 53.48, 55.37, BS, h=0.8, absolute=True)
    text(b, "J6", 9.7, 26.6, BS); text(b, "J7", 24.0, 26.6, BS)
    if battery:
        battery_silk(b)
    # rail + USB board
    text(b, "MDBT50Q-board / Rev K", (P.RAIL_X0 + P.RAIL_X1) / 2, 67.3, S, absolute=True)
    text(b, "USB Rev A", 47.5, 78.3, BS, absolute=True)
    outline_dims(b)
    text(b, "ANTENNA / NO COPPER", P.OX + 11.5, P.OY + 2.1, pcbnew.Dwgs_User, h=0.8, absolute=True, thick=0.1)
    tb = b.GetTitleBlock(); tb.SetRevision("K"); tb.SetTitle("MDBT50Q-board")

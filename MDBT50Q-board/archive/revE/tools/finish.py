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
    T("MDBT50Q-fable BATTERY  Rev D", 37.5, 4.2, BS); T("2x AAA ONLY   NO LiPo", 37.5, 9.8, BS)
    T("J9: 1=BAT+ 2=GND", 85.5, 4.2, BS); T("CELL 1 | CELL 2 in series", 85.5, 9.8, BS)


def silk(b, battery=P.BATTERY_ON_PANEL):
    refs_to_fab(b)
    S = pcbnew.F_SilkS
    text(b, "RST", 2.15, 16.2)                                            # SW1
    text(b, "SWD", 19.0, 3.0); text(b, "1", 19.0, 11.75, h=0.8)          # J3 (pin 1 at the bottom)
    text(b, "-", 25.6, 6.6, h=0.9); text(b, "+", 26.6, 6.6, h=0.9)       # J8 polarity under the pins
    text(b, "J6", 2.3, 22.6); text(b, "J7", 20.9, 21.4)
    # back side legends
    BS = pcbnew.B_SilkS
    text(b, "MDBT50Q-fable", 11.6, 8.0, BS)
    text(b, "Rev E  2L 1.2mm", 11.6, 9.8, BS)
    text(b, "J8: 1=BAT+ 2=GND", 25.6, 7.4, BS, h=0.8)
    text(b, "SWD 1=3V3 2=IO", 23.6, 11.4, BS, h=0.8); text(b, "3=CLK 4=RST 5=GND", 23.6, 12.7, BS, h=0.8)
    text(b, "J2/J4: 1=5V 2=D-", 24.6, 22.6, BS, h=0.8); text(b, "3=D+ 4=GND", 24.6, 23.8, BS, h=0.8)
    text(b, "J6", 9.7, 26.6, BS); text(b, "J7", 24.0, 26.6, BS)
    if battery:
        battery_silk(b)
    # rail + USB board
    text(b, "MDBT50Q-fable / Rev E", (P.RAIL_X0 + P.RAIL_X1) / 2, 67.3, S, absolute=True)
    text(b, "USB Rev A", 47.5, 78.3, BS, absolute=True)
    text(b, "ANTENNA / NO COPPER", P.OX + 11.5, P.OY + 2.1, pcbnew.Dwgs_User, h=0.8, absolute=True, thick=0.1)
    tb = b.GetTitleBlock(); tb.SetRevision("fable-E"); tb.SetTitle("MDBT50Q-board-fable")

# Build helpers for the compact MDBT50Q board: mechanics -> grid -> routing -> zones.
import sys, os, math, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM
import place as P
from router import Grid, RES, SLOP

W, H, OX, OY = P.W, P.H, P.OX, P.OY
F, B = pcbnew.F_Cu, pcbnew.B_Cu
LAY = [F, B]
log = print


def V(x, y):                      # local mm -> board VECTOR2I
    return VECTOR2I(FromMM(OX + x), FromMM(OY + y))


def VA(x, y):                     # absolute mm
    return VECTOR2I(FromMM(x), FromMM(y))


# ------------------------------------------------------------------ mechanics
def edge_line(b, x0, y0, x1, y1):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(VA(x0, y0)); s.SetEnd(VA(x1, y1)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.05)); b.Add(s)


def edge_arc(b, cx, cy, r, a0, a1):
    """arc around (cx,cy) from angle a0 to a1 (degrees, screen coords: 0=+x, 90=+y)."""
    pt = lambda a: (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetArcGeometry(VA(*pt(a0)), VA(*pt((a0 + a1) / 2)), VA(*pt(a1)))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(FromMM(0.05)); b.Add(s)


def broken_line(b, y, x0, x1, gaps):
    x = x0
    for g0, g1 in sorted(gaps):
        if g0 > x: edge_line(b, x, y, g0, y)
        x = g1
    if x1 > x: edge_line(b, x, y, x1, y)


def mechanics(b):
    x0, y0, x1, y1 = OX, OY, OX + W, OY + H
    R = P.R_CORNER
    tabs = [(OX + a, OX + c) for a, c in P.TABS]
    # MCU outline
    edge_arc(b, x0 + R, y0 + R, R, 180, 270); edge_line(b, x0 + R, y0, x1 - R, y0)
    edge_arc(b, x1 - R, y0 + R, R, 270, 360); edge_line(b, x1, y0 + R, x1, y1 - R)
    edge_arc(b, x1 - R, y1 - R, R, 0, 90); edge_arc(b, x0 + R, y1 - R, R, 90, 180)
    edge_line(b, x0, y1 - R, x0, y0 + R)
    broken_line(b, y1, x0 + R, x1 - R, tabs)
    # rail
    ry0, ry1, RR = P.RAIL_Y0, P.RAIL_Y1, 2.0
    for a, c in tabs:
        edge_line(b, a, y1, a, ry0); edge_line(b, c, y1, c, ry0)
    broken_line(b, ry0, x0 + RR, x1 - RR, tabs)
    edge_arc(b, x0 + RR, ry0 + RR, RR, 180, 270); edge_arc(b, x1 - RR, ry0 + RR, RR, 270, 360)
    edge_arc(b, x1 - RR, ry1 - RR, RR, 0, 90); edge_arc(b, x0 + RR, ry1 - RR, RR, 90, 180)
    edge_line(b, x0, ry0 + RR, x0, ry1 - RR); edge_line(b, x1, ry0 + RR, x1, ry1 - RR)
    broken_line(b, ry1, x0 + RR, x1 - RR, [(35.5, 40.5), (42.5, 47.5)])
    # mouse bites MCU<->rail (re-use MB1..24, duplicate for the rest)
    mbs = sorted([f for f in b.GetFootprints() if re.match(r"^MB\d+$", f.GetReference()) and int(f.GetReference()[2:]) <= 24],
                 key=lambda f: int(f.GetReference()[2:]))
    pos = []
    for a, c in tabs:
        cx = (a + c) / 2
        for yy in (y1 - P.MB_INSET, ry0 + P.MB_INSET):
            for k in range(6):
                pos.append((cx + (k - 2.5) * P.MB_PITCH, yy))
    n = 49
    while len(mbs) < len(pos):
        d = pcbnew.Cast_to_FOOTPRINT(mbs[0].Duplicate(False)); d.SetReference("MB%d" % n); n += 1
        b.Add(d); mbs.append(d)
    for f, (x, y) in zip(mbs, pos):
        f.SetPosition(VA(x, y))
    # tooling holes / fiducials on the rail
    for ref, (x, y) in {"TOOL1": (x0 + 2.5, 65.5), "TOOL2": (x1 - 2.5, 65.5), "FID1": (x0 + 6.0, 66.6),
                        "FID2": (x1 - 6.0, 66.6), "FID3": (x0 + W / 2 + 1.5, 64.4)}.items():
        b.FindFootprintByReference(ref).SetPosition(VA(x, y))

    # rule areas
    def rule_area(pts, pads=False):
        z = pcbnew.ZONE(b); z.SetIsRuleArea(True)
        ls = pcbnew.LSET(); ls.AddLayer(F); ls.AddLayer(B); z.SetLayerSet(ls)
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowPads(pads); z.SetDoNotAllowFootprints(False)
        o = z.Outline(); o.NewOutline()
        for x, y in pts: o.Append(FromMM(OX + x), FromMM(OY + y))
        b.Add(z)
    ax0, ay0, ax1, ay1 = P.ANT_KEEPOUT
    rule_area([(ax0, ay0), (ax1, ay0), (ax1, ay1), (ax0, ay1)], pads=True)
    for hx, hy in P.HOLES.values():
        r = P.HOLE_KEEPOUT_D / 2
        rule_area([(hx + r * math.cos(2 * math.pi * k / 48), hy + r * math.sin(2 * math.pi * k / 48)) for k in range(48)])


# ------------------------------------------------------------------ grid setup
class Ctx:
    pass


def setup(b):
    c = Ctx(); c.b = b; g = Grid(W, H); c.g = g
    c.netid = {}; c.pads = {}; c.netpads = {}

    def nid(name):
        if name not in c.netid: c.netid[name] = len(c.netid) + 1
        return c.netid[name]
    for f in b.GetFootprints():
        for p in f.Pads():
            bb = p.GetBoundingBox()
            x0, y0, x1, y1 = [ToMM(v) for v in (bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom())]
            cx, cy = ToMM(p.GetPosition().x) - OX, ToMM(p.GetPosition().y) - OY
            if y0 > OY + H + 0.6 or y1 < OY - 1: continue
            x0 -= OX; x1 -= OX; y0 -= OY; y1 -= OY
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                g.add_disk([0, 1], cx, cy, ToMM(p.GetDrillSize().x) / 2 + 0.15, -1)
                continue
            layers = [l for l, L in enumerate(LAY) if p.IsOnLayer(L)]
            name = p.GetNetname()
            if not name:
                g.add_rect(layers, x0, y0, x1, y1, -1)
            else:
                comp = g.new_comp()
                if p.GetShape() in (pcbnew.PAD_SHAPE_CIRCLE, pcbnew.PAD_SHAPE_OVAL):
                    g.add_rect(layers, x0, y0, x1, y1, nid(name), 0)
                    rr = min(x1 - x0, y1 - y0) / 2 - 0.08
                    for l in layers:
                        sl, m = g.seg_mask(cx, cy, cx, cy, rr)
                        g.comp[l][sl][m] = comp
                else:
                    g.add_rect(layers, x0, y0, x1, y1, nid(name), comp)
                key = (f.GetReference(), p.GetNumber())
                c.pads[key] = dict(xy=(cx, cy), rect=(x0, y0, x1, y1), layers=layers, net=name, comp=comp)
                c.netpads.setdefault(name, []).append(key)
            if layers == [0]:
                sl, m = g.rect_mask(x0, y0, x1, y1, 0)
                if sl: g.padmask[sl] |= m
    # board edge (0.3 mm copper clearance incl. router clearance)
    e = 0.15
    g.block_rect([0, 1], -1, -1, W + 1, e); g.block_rect([0, 1], -1, H - e, W + 1, H + 1)
    g.block_rect([0, 1], -1, -1, e, H + 1); g.block_rect([0, 1], W - e, -1, W + 1, H + 1)
    R = P.R_CORNER
    X = g.xx * RES; Y = g.yy * RES
    for cx, cy, sx, sy in ((R, R, -1, -1), (W - R, R, 1, -1), (W - R, H - R, 1, 1), (R, H - R, -1, 1)):
        m = ((X - cx) * sx > 0) & ((Y - cy) * sy > 0) & ((X - cx) ** 2 + (Y - cy) ** 2 > (R - e) ** 2)
        g.cu[0][m] = -1; g.cu[1][m] = -1
    g.block_rect([0, 1], *P.ANT_KEEPOUT)
    for hx, hy in P.HOLES.values():
        g.add_disk([0, 1], hx, hy, P.HOLE_KEEPOUT_D / 2 - 0.15, -1)   # mechanical keepout: no electrical clearance needed
    c.tracks = []; c.vias = []
    return c


def emit(c, net, runs, vias, w, via_d, via_drill, comp):
    g = c.g; n = c.netid[net]
    for l, pts in runs:
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            g.add_seg(l, xa, ya, xb, yb, w, n, comp)
            c.tracks.append((net, l, xa, ya, xb, yb, w))
    for x, y in vias:
        g.add_disk([0, 1], x, y, via_d / 2, n, comp)
        c.vias.append((net, x, y, via_d, via_drill))


def manual(c, net, layer, pts, w, comp=None):
    """hand-placed polyline (local mm)."""
    if comp is None:
        comp = c.g.new_comp()
    emit(c, net, [(layer, pts)], [], w, 0, 0, comp)
    return comp


def via_size(w):
    return (0.6, 0.3) if w >= 0.3 else (0.5, 0.25)


def route_net(c, net, w=0.2, order=None, **kw):
    """connect all pads of a net (root = first pad)."""
    g = c.g; n = c.netid[net]
    keys = order or c.netpads[net]
    root = c.pads[keys[0]]["comp"]
    done = [keys[0]]; todo = list(keys[1:])
    ok = True
    while todo:
        best = min(todo, key=lambda k: min(math.dist(c.pads[k]["xy"], c.pads[d]["xy"]) for d in done))
        todo.remove(best)
        tp = c.pads[best]
        x, y = tp["xy"]
        tcomp = int(g.comp[tp["layers"][0]][int(round(y / RES)), int(round(x / RES))])
        if tcomp == root:
            done.append(best); continue
        for attempt in range(6):
            path = None
            for ww in [w] + [v for v in (0.3, 0.25, 0.2) if v < w]:
                vd, vdr = via_size(ww)
                path = g.astar(n, root, tp["xy"], ww, vd, **kw)
                if path: break
            if not path:
                log("  !! FAILED %s -> %s" % (net, best)); ok = False
                break
            if ww != w: log("  (narrowed %s -> %s to %.2f)" % (net, best, ww))
            l, px, py = path[-1]
            hit = int(g.comp[l][py, px])
            runs, vias = Grid.simplify(path)
            emit(c, net, runs, vias, ww, vd, vdr, root)
            g.comp[g.comp == hit] = root
            if hit == tcomp:
                break
        done.append(best)
    return ok


def gnd_stub(c, key, hint=None, w=0.25):
    """short track from a GND SMD pad to a new via (ties it to both pours)."""
    g = c.g; n = c.netid["GND"]; pd = c.pads[key]
    vd, vdr = 0.6, 0.3
    blk, vb = g.masks(n, w, vd)
    goal = np.zeros_like(blk)
    goal[0] = ~vb & ~blk[0] & ~blk[1]
    path = g.astar(n, pd["comp"], hint or pd["xy"], w, vd, allow_via=False, goal=goal, max_exp=150000)
    if not path:
        log("  !! GND stub failed", key); return False
    runs, vias = Grid.simplify(path)
    l, px, py = path[-1]
    emit(c, "GND", runs, [(px * RES, py * RES)], w, vd, vdr, pd["comp"])
    return True


# ------------------------------------------------------------------ output
def write_copper(c):
    b = c.b
    for net, l, xa, ya, xb, yb, w in c.tracks:
        t = pcbnew.PCB_TRACK(b); t.SetStart(V(xa, ya)); t.SetEnd(V(xb, yb)); t.SetWidth(FromMM(w))
        t.SetLayer(LAY[l]); t.SetNet(b.FindNet(net)); b.Add(t)
    for net, x, y, d, dr in c.vias:
        v = pcbnew.PCB_VIA(b); v.SetPosition(V(x, y)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(F, B); v.SetWidth(F, FromMM(d)); v.SetDrill(FromMM(dr)); v.SetNet(b.FindNet(net)); b.Add(v)


def add_zones(b):
    zs = []
    for L in LAY:
        z = pcbnew.ZONE(b); z.SetLayer(L); z.SetNet(b.FindNet("GND"))
        o = z.Outline(); o.NewOutline()
        for x, y in ((0, 0), (W, 0), (W, H), (0, H)): o.Append(FromMM(OX + x), FromMM(OY + y))
        z.SetLocalClearance(FromMM(0.2)); z.SetMinThickness(FromMM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(FromMM(0.2)); z.SetThermalReliefSpokeWidth(FromMM(0.3))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetAssignedPriority(0); z.SetZoneName("GND_" + ("F" if L == F else "B"))
        b.Add(z); zs.append(z)
    return zs


def fill(b):
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())

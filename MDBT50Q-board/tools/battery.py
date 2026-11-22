# Rev D battery board (2x AAA in series): hand-routed copper and BATT_GND pours.
# Local mm: x along the board (J9 end = 0), y down, battery axis at y = 7.
#   BT1 (-) cell 1 (+) BT2 = BT3 (-) cell 2 (+) BT4 -> F1 -> SW2 -> J9-1 (BATT_SW); BT1 -> J9-2 (BATT_GND)
import pcbnew
from pcbnew import FromMM
import place as P

F, B = pcbnew.F_Cu, pcbnew.B_Cu

# (net, layer, polyline in battery-board local mm, width)
TRACKS = [
    ("BATT_GND", F, [(6.2, 11.4), (13.0, 11.4), (15.0, 9.4)], 0.5),                 # J9-2 -> BT1 (cell 1 -)
    ("Net-(SW2-C)", F, [(6.35, 4.9), (6.35, 6.5), (8.85, 9.0), (9.1, 9.0)], 0.5),  # SW2 throw -> F1-2
    ("BATT_SW", F, [(7.85, 4.9), (7.85, 6.6)], 0.5),                               # SW2 common -> via
    ("BATT_SW", B, [(7.85, 6.6), (6.2, 8.25), (6.2, 9.4)], 0.5),                   # under the SW2-C track -> J9-1 (THT)
    ("/BATT_P", F, [(11.9, 9.0), (13.3, 9.0)], 0.5),                               # F1-1 -> via
    ("/BATT_P", B, [(13.3, 9.0), (13.3, 8.2), (14.5, 7.0), (97.8, 7.0)], 0.5),      # along the board, bottom layer
    ("/BATT_P", F, [(97.8, 7.0), (100.0, 7.0)], 0.5),                              # -> BT4 (cell 2 +)
    ("/CELL_MID", F, [(56.0, 7.0), (67.0, 7.0)], 5.0),                             # BT2 (cell 1 +) = BT3 (cell 2 -)
]
VIAS = [("BATT_SW", 7.85, 6.6), ("/BATT_P", 13.3, 9.0), ("/BATT_P", 97.8, 7.0)]
# pours: top only around the J9 end and BT1 (same net); bottom over the whole board.
# Corners next to the screw holes stay bare (no slivers between the keepout and the board edge).
TOP_POUR = [(0, 4.2), (3.8, 4.2), (3.8, 0), (25.0, 0), (25.0, P.BH), (0, P.BH)]
BOT_POUR = [(0, 4.2), (3.8, 4.2), (3.8, 0), (109.5, 0), (109.5, P.BH), (0, P.BH)]
STITCH = [(1.5, 5.6), (8.6, 12.6), (10.5, 12.4), (13.3, 12.4), (14.6, 1.6), (16.0, 12.6), (24.0, 1.5), (24.0, 12.5)]


def build(b):
    for net, layer, pts, w in TRACKS:
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b); t.SetStart(P.BA(xa, ya)); t.SetEnd(P.BA(xb, yb)); t.SetWidth(FromMM(w))
            t.SetLayer(layer); t.SetNet(b.FindNet(net)); b.Add(t)
    for net, x, y in VIAS + [("BATT_GND", x, y) for x, y in STITCH]:
        v = pcbnew.PCB_VIA(b); v.SetPosition(P.BA(x, y)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(F, B); v.SetWidth(F, FromMM(0.6)); v.SetDrill(FromMM(0.3)); v.SetNet(b.FindNet(net)); b.Add(v)
    for L, poly in ((F, TOP_POUR), (B, BOT_POUR)):
        z = pcbnew.ZONE(b); z.SetLayer(L); z.SetNet(b.FindNet("BATT_GND"))
        o = z.Outline(); o.NewOutline()
        for x, y in poly:
            o.Append(FromMM(P.BX + x), FromMM(P.BY + y))
        z.SetLocalClearance(FromMM(0.3)); z.SetMinThickness(FromMM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(FromMM(0.3)); z.SetThermalReliefSpokeWidth(FromMM(0.5))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetZoneName("BATT_GND_" + ("F" if L == F else "B"))
        b.Add(z)


def prune(b):
    """drop battery stitching vias that are not inside the BATT_GND fill on both layers."""
    zones = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "BATT_GND"]
    pts = {(round(P.BX + x, 3), round(P.BY + y, 3)) for x, y in STITCH}
    n = 0
    for v in [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "BATT_GND"]:
        key = (round(pcbnew.ToMM(v.GetPosition().x), 3), round(pcbnew.ToMM(v.GetPosition().y), 3))
        if key not in pts: continue
        if all(any(z.IsOnLayer(L) and z.HitTestFilledArea(L, v.GetPosition(), 0) for z in zones) for L in (F, B)):
            n += 1
        else:
            b.RemoveNative(v)
    return n

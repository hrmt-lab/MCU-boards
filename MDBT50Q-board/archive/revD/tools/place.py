# Stage 1: build the un-routed compact board from the (read-only) cdx source.
import pcbnew, sys, os, re, math, uuid
from pcbnew import VECTOR2I, FromMM, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.dirname(HERE)
SRC = os.path.join(os.path.dirname(PRJ), "MDBT50Q-board-cdx", "MDBT50Q-board-cdx.kicad_pcb")
OUT = os.path.join(PRJ, "MDBT50Q-board-fable.kicad_pcb")
KFP = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "KiCad", "10.0", "share", "kicad", "footprints")

# ---- geometry of the new MCU board (absolute page coordinates) ----
W, H = 33.1, 27.8
OX, OY = 29.5, 32.0            # top-left corner of MCU board (x aligned with the USB daughter board)
RAIL_Y0, RAIL_Y1 = OY + H + 2.0, 69.0
R_CORNER = 1.0
HOLE_DRILL = 1.6               # M1.4 clearance hole (NPTH)
HOLE_KEEPOUT_D = 3.2           # copper-free ring for the screw head (head dia <= 3.0 mm)
ANT_KEEPOUT = (0.0, 0.0, 23.1, 4.3)   # local

# ref: (x, y, rot) in local mm
PLACE = {
    "U1": (11.6, 8.3, 0),
    "Y1": (8.4, 17.9, 0), "C4": (7.15, 20.05, -90), "C5": (9.65, 20.05, -90),
    "J6": (9.7, 24.2, 0), "J7": (24.0, 24.2, 0),
    "J8": (26.1, 3.3, 180), "Q1": (31.3, 2.6, 90),                     # battery input (SH 2P, opening at the top edge)
    "J2": (29.8, 18.0, 90),
    "U4": (25.3, 8.2, 180), "L1": (28.55, 8.2, 180), "C10": (23.3, 8.975, -90), "C9": (31.9, 7.6, -90),
    "R3": (20.0, 15.3, 90), "R4": (21.3, 13.6, 90), "C8": (20.0, 13.25, 90),
    "J3": (19.0, 10.08, 180), "D1": (20.97, 6.2, -90), "R7": (21.0, 9.4, 90),
    "SW1": (2.15, 12.0, -90),
    "C1": (13.6, 18.3, -90), "C2": (15.6, 18.3, -90),
    "U5": (24.6, 17.0, 180), "C11": (21.7, 18.0, 180), "R6": (24.6, 12.9, 180), "R5": (27.7, 12.9, 180),
    "U3": (30.95, 25.35, 0), "C6": (25.6, 20.3, 90), "C7": (24.1, 14.6, 0),
}
HOLES = {"H1": (2.0, 6.6), "H2": (2.0, 19.6), "H3": (31.3, 12.0)}
# mouse-bite tabs MCU<->rail: local x ranges on the bottom edge
TABS = [(2.0, 7.0), (16.6, 21.6), (27.0, 32.0)]
MB_D, MB_PITCH, MB_INSET = 0.5, 0.75, 0.15

# ---- battery board: separate PCB right of the MCU board, bottom edge on the same rail ----
# Rev D: 2x AAA in series along the board (MYOUNG SMD clips). Clip pad centres 37 mm apart per cell (datasheet:
# 9 mm pads, 28 mm between them); the two middle clips sit back to back, 11 mm apart (10 mm clip bases).
BW, BH = 113.3, 14.0
BX, BY = OX + W + 2.0, OY + H - BH          # absolute top-left corner
CELL_Y = 7.0                                # battery axis (local y)
BPLACE = {"F1": (10.0, 9.0, 180), "SW2": (8.6, 2.9, 180), "J9": (3.3, 10.0, 270),
          "BT1": (19.0, CELL_Y, 0), "BT2": (56.0, CELL_Y, 180), "BT3": (67.0, CELL_Y, 0), "BT4": (104.0, CELL_Y, 180)}
BHOLES = {"H7": (2.0, 2.4), "H8": (111.3, CELL_Y)}
BTABS = [(1.0, 6.0), (36.0, 41.0), (76.0, 81.0), (106.5, 111.5)]
RAIL_X0, RAIL_X1 = OX, BX + BW + 1.5

# J8/J9 (new in Rev C): JST SH 2P side entry, linked to the schematic symbols created by sch_update.py
SH2_LIB, SH2_NAME = "Connector_JST", "JST_SH_SM02B-SRSS-TB_1x02-1MP_P1.00mm_Horizontal"
SCH_ROOT = "/055b3003-8cf0-42f7-927e-2cf1136fcf40"
NEW_CONN = {"J8": ("VBAT_IN", "GND"), "J9": ("BATT_SW", "BATT_GND")}
NET_REV_C = {("SW2", "2"): "BATT_SW", ("Q1", "3"): "VBAT_IN"}
# Rev D: battery clips (footprints in libraries/fable_Parts.pretty, symbols created by sch_update.py rev_d)
CLIP19 = ("BatteryClip_MYOUNG_MY-AAA-19-J", "AAA-", "C6937104", "MYOUNG MY-AAA-19-J", "AAA battery clip, negative (spring)")
CLIP20 = ("BatteryClip_MYOUNG_MY-AAA-20-J", "AAA+", "C6937107", "MYOUNG MY-AAA-20-J", "AAA battery clip, positive")
CLIPS = {"BT1": (CLIP19, "BATT_GND", ", cell 1"), "BT2": (CLIP20, "/CELL_MID", ", cell 1"),
         "BT3": (CLIP19, "/CELL_MID", ", cell 2"), "BT4": (CLIP20, "/BATT_P", ", cell 2")}
FABLE_LIB = os.path.join(PRJ, "libraries", "fable_Parts.pretty")


def A(x, y):
    return VECTOR2I(FromMM(OX + x), FromMM(OY + y))


def BA(x, y):                  # battery-board local mm -> board
    return VECTOR2I(FromMM(BX + x), FromMM(BY + y))



def strip(b):
    # --- remove everything that will be regenerated ---
    usb_y = FromMM(70.0)
    rm = []
    for t in b.GetTracks():
        if t.GetStart().y < usb_y:
            rm.append(t)
    for i in range(b.GetAreaCount()):
        z = b.GetArea(i)
        if z.GetBoundingBox().GetY() < usb_y:
            rm.append(z)
    for d in b.GetDrawings():
        bb = d.GetBoundingBox()
        if d.GetLayer() == pcbnew.Edge_Cuts:
            if bb.GetY() < FromMM(68.5) or (d.GetStart().y == FromMM(69.0) and d.GetEnd().y == FromMM(69.0)):
                rm.append(d)
            continue
        if bb.GetY() < usb_y or d.GetClass().startswith("PCB_DIM"):
            rm.append(d)
        elif d.GetLayer() == pcbnew.B_SilkS:      # USB test-pad legends
            rm.append(d)
    for f in b.GetFootprints():
        r = f.GetReference()
        if re.match(r"^TP\d+$", r) or r == "H4":
            rm.append(f)
    for it in rm:
        b.RemoveNative(it)


def swap_j3(b):
    """Convert the unpopulated 2.54 mm SWD header into a 1.27 mm pitch one (in place)."""
    f = b.FindFootprintByReference("J3")
    f.SetOrientationDegrees(0)
    o = f.GetPosition()
    f.SetFPID(pcbnew.LIB_ID("CDX_Connectors", "PinHeader_1x05_P1.27mm_Vertical"))
    for p in f.Pads():
        n = int(p.GetNumber())
        p.SetPosition(VECTOR2I(o.x, o.y + FromMM(1.27 * (n - 1))))
        p.SetSize(VECTOR2I(FromMM(1.0), FromMM(1.0)))
        p.SetDrillSize(VECTOR2I(FromMM(0.65), FromMM(0.65)))
    for g in [g for g in f.GraphicalItems()]:
        f.RemoveNative(g)
    def rect(layer, x0, y0, x1, y1, w):
        s = pcbnew.PCB_SHAPE(f); s.SetShape(pcbnew.SHAPE_T_RECT)
        s.SetStart(VECTOR2I(o.x + FromMM(x0), o.y + FromMM(y0))); s.SetEnd(VECTOR2I(o.x + FromMM(x1), o.y + FromMM(y1)))
        s.SetLayer(layer); s.SetWidth(FromMM(w)); f.Add(s)
    rect(pcbnew.F_CrtYd, -1.15, -1.15, 1.15, 6.23, 0.05)
    rect(pcbnew.F_Fab, -1.05, -0.635, 1.05, 5.715, 0.1)
    rect(pcbnew.F_SilkS, -0.95, -0.95, 0.95, 6.03, 0.12)
    try:
        f.Models().clear()
    except Exception as ex:
        print("models", ex)


def place(b):
    for ref, (x, y, rot) in PLACE.items():
        f = b.FindFootprintByReference(ref)
        if f is None: continue                     # J8: created in rev_c()
        f.SetPosition(A(x, y))
        f.SetOrientationDegrees(rot)
    for ref, (x, y, rot) in BPLACE.items():
        f = b.FindFootprintByReference(ref)
        if f is None: continue                     # J9 / BT1-4: created in rev_c() / rev_d()
        f.SetPosition(BA(x, y))
        f.SetOrientationDegrees(rot)
    for ref, (x, y) in HOLES.items():
        f = b.FindFootprintByReference(ref)
        f.SetPosition(A(x, y))
        m14_hole(f)


def m14_hole(f):
    """turn the M2 NPTH footprint into an M1.4 clearance hole (in place)."""
    o = f.GetPosition()
    for p in f.Pads():
        p.SetPosition(o)
        p.SetSize(VECTOR2I(FromMM(HOLE_DRILL), FromMM(HOLE_DRILL)))
        p.SetDrillSize(VECTOR2I(FromMM(HOLE_DRILL), FromMM(HOLE_DRILL)))
    for g in [g for g in f.GraphicalItems()]:
        f.RemoveNative(g)
    for layer, r, w in ((pcbnew.F_Fab, HOLE_KEEPOUT_D / 2, 0.1),
                        (pcbnew.Cmts_User, HOLE_KEEPOUT_D / 2, 0.1)):
        s = pcbnew.PCB_SHAPE(f); s.SetShape(pcbnew.SHAPE_T_CIRCLE)
        s.SetCenter(o); s.SetEnd(VECTOR2I(o.x + FromMM(r), o.y))
        s.SetLayer(layer); s.SetWidth(FromMM(w)); f.Add(s)
    f.SetValue("M1.4")


# FPC pin re-assignment (ref, pad) -> net   (see CHANGES.md)
REASSIGN = {("J6", "20"): "P1.09", ("J7", "3"): "P0.13", ("J7", "5"): "P0.17"}


def reassign(b):
    for (ref, num), net in REASSIGN.items():
        for p in b.FindFootprintByReference(ref).Pads():
            if p.GetNumber() == num:
                p.SetNet(b.FindNet(net))


def rev_c(b):
    """battery board split: new nets, J8/J9 (SH 2P), battery-board holes H4/H5."""
    for n in ("VBAT_IN", "BATT_SW", "BATT_GND"):
        if not b.FindNet(n):
            b.Add(pcbnew.NETINFO_ITEM(b, n))
    b.BuildListOfNets()

    def setnet(f, num, net):
        for p in f.Pads():
            if p.GetNumber() == num:
                p.SetNet(b.FindNet(net))
    for (ref, num), net in NET_REV_C.items():
        setnet(b.FindFootprintByReference(ref), num, net)
    lib = os.path.join(KFP, SH2_LIB + ".pretty")
    for ref, (n1, n2) in NEW_CONN.items():
        f = pcbnew.FootprintLoad(lib, SH2_NAME)
        f.SetFPID(pcbnew.LIB_ID(SH2_LIB, SH2_NAME))
        f.SetReference(ref); f.SetValue("Conn_01x02")
        sym = str(uuid.uuid5(uuid.NAMESPACE_URL, "mdbt50q-fable/revC/sym" + ref))
        f.SetPath(pcbnew.KIID_PATH(SCH_ROOT + "/" + sym))
        b.Add(f)
        x, y, rot = PLACE[ref] if ref in PLACE else BPLACE[ref]
        f.SetPosition(A(x, y) if ref in PLACE else BA(x, y)); f.SetOrientationDegrees(rot)
        setnet(f, "1", n1); setnet(f, "2", n2)
        for fl in f.GetFields():
            if fl.GetName() == "Description":
                fl.SetText("JST SH 2P, SM02B-SRSS-TB (side entry, SMD)")
    src = b.FindFootprintByReference("H1")
    for ref, (x, y) in BHOLES.items():
        d = pcbnew.Cast_to_FOOTPRINT(src.Duplicate(False)); d.SetReference(ref)
        b.Add(d); d.SetPosition(BA(x, y)); m14_hole(d)


def rev_d(b):
    """2x AAA battery board: J5 (PH battery connector) replaced by four SMD clips BT1..BT4."""
    b.RemoveNative(b.FindFootprintByReference("J5"))
    for n in ("/BATT_P", "/CELL_MID"):
        if not b.FindNet(n):
            b.Add(pcbnew.NETINFO_ITEM(b, n))
    b.BuildListOfNets()
    for p in b.FindFootprintByReference("F1").Pads():
        if p.GetNumber() == "1": p.SetNet(b.FindNet("/BATT_P"))
    for ref, ((name, value, lcsc, mpn, descr), net, cell) in CLIPS.items():
        f = pcbnew.FootprintLoad(FABLE_LIB, name)
        f.SetFPID(pcbnew.LIB_ID("fable_Parts", name))
        f.SetReference(ref); f.SetValue(value)
        f.SetPath(pcbnew.KIID_PATH(SCH_ROOT + "/" + str(uuid.uuid5(uuid.NAMESPACE_URL, "mdbt50q-fable/revC/sym" + ref))))
        for k, v in (("Datasheet", "https://www.lcsc.com/product-detail/%s.html" % lcsc), ("Description", descr + cell),
                     ("LCSC", lcsc), ("MPN", mpn)):
            f.SetField(k, v); f.GetField(k).SetVisible(False)
        b.Add(f)
        x, y, rot = BPLACE[ref]
        f.SetPosition(BA(x, y)); f.SetOrientationDegrees(rot)
        for p in f.Pads(): p.SetNet(b.FindNet(net))


def make():
    b = pcbnew.LoadBoard(SRC); swap_j3(b); place(b); reassign(b); strip(b); rev_c(b); rev_d(b)
    return b


if __name__ == "__main__":
    b = make()
    b.Save(OUT)
    print("saved", OUT)

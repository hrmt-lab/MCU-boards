# Stage 1: build the un-routed compact board from the (read-only) cdx source.
import pcbnew, sys, os, re, math
from pcbnew import VECTOR2I, FromMM, ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.dirname(HERE)
SRC = os.path.join(os.path.dirname(PRJ), "MDBT50Q-board-cdx", "MDBT50Q-board-cdx.kicad_pcb")
OUT = os.path.join(PRJ, "MDBT50Q-board-fable.kicad_pcb")
KFP = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "KiCad", "10.0", "share", "kicad", "footprints")

# ---- geometry of the new MCU board (absolute page coordinates) ----
W, H = 36.0, 27.8
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
    "J5": (27.6, 6.2, 180), "F1": (33.0, 11.05, 0),
    "SW2": (33.1, 5.2, 90), "J2": (32.7, 19.6, 90),
    "Q1": (32.4, 13.95, 0),
    "U4": (25.3, 10.6, 180), "L1": (28.55, 10.6, 180), "C10": (23.3, 11.375, -90), "C9": (28.9, 12.75, 180),
    "R3": (20.0, 15.3, 90), "R4": (21.3, 13.6, 90), "C8": (20.0, 13.25, 90),
    "J3": (19.0, 10.08, 180), "D1": (20.97, 6.2, -90), "R7": (21.75, 8.85, 180),
    "SW1": (2.15, 12.0, -90),
    "C1": (13.6, 18.3, -90), "C2": (15.6, 18.3, -90),
    "U5": (24.6, 17.0, 180), "C11": (21.7, 18.0, 180), "R6": (27.45, 14.45, 0), "R5": (27.45, 15.95, 180),
    "U3": (31.0, 25.35, 0), "C6": (27.3, 21.2, 180), "C7": (27.45, 17.85, 0),
}
HOLES = {"H1": (2.0, 6.6), "H2": (2.0, 19.6), "H3": (34.4, 25.5)}
# mouse-bite tabs MCU<->rail: local x ranges on the bottom edge
TABS = [(2.0, 7.0), (16.6, 21.6), (29.0, 34.0)]
MB_D, MB_PITCH, MB_INSET = 0.5, 0.75, 0.15


def A(x, y):
    return VECTOR2I(FromMM(OX + x), FromMM(OY + y))



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
        f.SetPosition(A(x, y))
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


def make():
    b = pcbnew.LoadBoard(SRC); swap_j3(b); place(b); reassign(b); strip(b)
    return b


if __name__ == "__main__":
    b = make()
    b.Save(OUT)
    print("saved", OUT)

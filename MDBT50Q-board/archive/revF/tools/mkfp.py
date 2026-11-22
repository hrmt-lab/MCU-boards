# Rev D: footprints for the MYOUNG AAA SMD battery clips (datasheet WD-CP-0276 / -0277, 2023-03-09).
# Origin = pad centre. The battery lies towards +x; the contact plate (clip end wall) is at -x.
# Land pattern per datasheet: 9 MIN (along the cell) x 5 MIN (across); the inner pad edges of one cell are 28 mm apart,
# i.e. pad centres 37 mm apart. Pad here: 9.5 x 5.5.
import os
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "libraries", "fable_Parts.pretty")
PARTS = {
    "BatteryClip_MYOUNG_MY-AAA-19-J": ("MYOUNG MY-AAA-19-J, AAA battery clip, NEGATIVE (spring) contact, SMD, LCSC C6937104", "spring"),
    "BatteryClip_MYOUNG_MY-AAA-20-J": ("MYOUNG MY-AAA-20-J, AAA battery clip, POSITIVE (flat) contact, SMD, LCSC C6937107", "flat"),
}


def line(x0, y0, x1, y1, layer, w):
    return '\t(fp_line (start %s %s) (end %s %s) (stroke (width %s) (type solid)) (layer "%s"))\n' % (x0, y0, x1, y1, w, layer)


def rect(x0, y0, x1, y1, layer, w):
    return '\t(fp_rect (start %s %s) (end %s %s) (stroke (width %s) (type solid)) (fill no) (layer "%s"))\n' % (x0, y0, x1, y1, w, layer)


for name, (descr, kind) in PARTS.items():
    s = '(footprint "%s"\n\t(version 20241229)\n\t(generator "fable_mkfp")\n\t(layer "F.Cu")\n' % name
    s += '\t(descr "%s")\n\t(tags "battery clip AAA SMD MYOUNG")\n\t(attr smd)\n' % descr
    s += '\t(property "Reference" "REF**" (at 0 -6.8 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))\n'
    s += '\t(property "Value" "%s" (at 0 6.8 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))\n' % name
    # body: base 10 long, 11 (+0.8 tol) wide; plate wall at -x
    s += rect(-5.0, -5.5, 5.0, 5.5, "F.Fab", 0.1)
    s += line(-4.8, -4.5, -4.8, 4.5, "F.Fab", 0.4)                      # contact plate
    if kind == "spring":
        for k in range(4):                                                # spring hint
            s += line(-4.4 + 1.6 * k, -2.0, -3.6 + 1.6 * k, 2.0, "F.Fab", 0.1)
    s += '\t(fp_text user "${REFERENCE}" (at 1.5 0 90) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))\n'
    s += rect(-5.45, -6.15, 5.45, 6.15, "F.CrtYd", 0.05)       # base 10+0.5 long -> +-5.25, +0.2
    s += '\t(pad "1" smd rect (at 0 0) (size 9.5 5.5) (layers "F.Cu" "F.Paste" "F.Mask"))\n'
    s += ')\n'
    open(os.path.join(OUT, name + ".kicad_mod"), "w", encoding="utf8").write(s)
    print("wrote", name)


# Rev F: J8 (JST PH 2P S2B-PH-K, side entry) in the top-right corner of the MCU board, opening to the right.
# Same as CDX_Connectors:..._EdgeSilk, minus the body-outline silk on the pin-2 side (it would lie on the top
# board edge and the rounded corner).
SRC_PH = os.path.join(os.path.dirname(OUT), "CDX_Connectors.pretty", "JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal_EdgeSilk.kicad_mod")
PH_NAME = "JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal_CornerSilk"
t = open(SRC_PH, encoding="utf8").read()
k = t.index("(start 4.06 6)\n\t\t(end 4.06 -1.46)")
i = t.rindex("\n\t(fp_line", 0, k)
j = t.index("\n\t)", k) + 3
t = t[:i] + t[j:]
t = t.replace('(footprint "JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal_EdgeSilk"', '(footprint "%s"' % PH_NAME, 1)
open(os.path.join(OUT, PH_NAME + ".kicad_mod"), "w", encoding="utf8").write(t)
print("wrote", PH_NAME)

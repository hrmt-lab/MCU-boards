# Apply the fable changes to the schematic copy (idempotent; starts from the cdx original).
import os, re
HERE = os.path.dirname(os.path.abspath(__file__)); PRJ = os.path.dirname(HERE)
SRC = os.path.join(os.path.dirname(PRJ), "MDBT50Q-board-cdx", "MDBT50Q-board-cdx.kicad_sch")
OUT = os.path.join(PRJ, "MDBT50Q-board-fable.kicad_sch")
s = open(SRC, encoding="utf8").read()

def relabel(s, old, at, new):
    pat = re.compile(r'(\(global_label ")' + re.escape(old) + r'("\s*\(shape \w+\)\s*\(at ' + re.escape(at) + r' )')
    s2, n = pat.subn(lambda m: m.group(1) + new + m.group(2), s)
    assert n == 1, (old, at, n)
    return s2

# FPC pin re-assignment
s = relabel(s, "P0.17", "226.06 93.98", "P1.09")    # J6 pin 20
s = relabel(s, "P1.09", "289.56 72.39", "P0.13")    # J7 pin 3
s = relabel(s, "P0.13", "289.56 77.47", "P0.17")    # J7 pin 5
# SWD header: 1.27 mm pitch, unpopulated
a = '"Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical"'
assert s.count(a) == 1
s = s.replace(a, '"CDX_Connectors:PinHeader_1x05_P1.27mm_Vertical"')
# notes
NL = chr(92) + "n"
note = ('(text "FABLE Rev A / 2026-11-16: compact production layout (40 x 28 mm)' + NL +
        'FPC pins changed: J6-20 = P1.09 (was P0.17), J7-3 = P0.13 (was P1.09), J7-5 = P0.17 (was P0.13).' + NL +
        'J3 (SWD) is now a 1.27 mm pitch unpopulated header. All PCB test pads removed.' + NL +
        'See CHANGES-fable.md." (at 20 275 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "3f0a6c1e-7b52-4d0e-9a61-fab1e0000001"))' + chr(10))
old = ("USB PCB: TP13-TP20 on back, 5V/GND/CC1/CC2 and D+/D- before/after ESD." + NL +
       "USB outline unchanged. Test pads are PCB-only, excluded from BOM/POS.")
assert old in s
s = s.replace(old, "USB outline unchanged. (Prototype test pads TP1-TP20 were removed in the fable revision.)")
i = s.rindex(")")
s = s[:i] + chr(9) + note + s[i:]
s = s.replace('(rev "F")', '(rev "fable-A")')
open(OUT, "w", encoding="utf8").write(s)
print("schematic updated")

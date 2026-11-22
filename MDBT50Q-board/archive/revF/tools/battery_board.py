# Rev E: the Rev D battery board (2x AAA) as a stand-alone PCB, to be merged into the keyboard PCB.
# Same parts, copper and silk as Rev D; no tabs, no rail. Output: battery-board/MDBT50Q-battery.kicad_pcb
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
import place as P
P.BX, P.BY = 50.0, 50.0                      # board top-left corner (before make(): placement reads these)
import build as BD
import battery as BAT
import finish as FN
import render

OUT_DIR = os.path.join(P.PRJ, "battery-board")
OUT = os.path.join(OUT_DIR, "MDBT50Q-battery.kicad_pcb")

b = P.make(battery=True)
keep = set(P.BREFS)
for f in [f for f in b.GetFootprints() if f.GetReference() not in keep]:
    b.RemoveNative(f)
for it in list(b.GetTracks()) + list(b.Zones()) + list(b.GetDrawings()):
    b.RemoveNative(it)
BD.battery_mechanics(b, [])
BAT.build(b)
BD.fill(b)
print("battery stitching vias kept: %d" % BAT.prune(b))
FN.refs_to_fab(b)
FN.battery_silk(b)
BD.fill(b)
tb = b.GetTitleBlock(); tb.SetTitle("MDBT50Q-fable battery board (2x AAA)"); tb.SetRevision("D")
os.makedirs(OUT_DIR, exist_ok=True)
b.Save(OUT)
shutil.copyfile(os.path.join(P.PRJ, "MDBT50Q-board-fable.kicad_pro"), OUT.replace(".kicad_pcb", ".kicad_pro"))   # same design rules
# the project's footprint libraries, seen from the sub-folder
t = open(os.path.join(P.PRJ, "fp-lib-table"), encoding="utf8").read()
open(os.path.join(OUT_DIR, "fp-lib-table"), "w", encoding="utf8").write(t.replace("${KIPRJMOD}/libraries/", "${KIPRJMOD}/../libraries/"))
print("saved", OUT)
render.render(OUT, os.path.join(P.HERE, "r_batt.png"), P.BX - 0.5, P.BY - 0.5, P.BX + P.BW + 0.5, P.BY + P.BH + 0.5, 16)

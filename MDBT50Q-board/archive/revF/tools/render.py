# 2D debug render of a board region to PNG (pads, courtyards, tracks, vias, refs)
import pcbnew, sys
from PIL import Image, ImageDraw, ImageFont
from pcbnew import ToMM

def render(path, out, x0, y0, x1, y1, S=24, layers="FB", zones=False):
    b = pcbnew.LoadBoard(path) if isinstance(path, str) else path
    img = Image.new("RGB", (int((x1 - x0) * S), int((y1 - y0) * S)), (20, 20, 20))
    d = ImageDraw.Draw(img, "RGBA")
    P = lambda x, y: ((ToMM(x) - x0) * S, (ToMM(y) - y0) * S)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except Exception:
        font = ImageFont.load_default()
    if zones:
        for z in b.Zones():
            if z.GetIsRuleArea(): continue
            for lay, col in ((pcbnew.B_Cu, (40, 60, 150, 90)), (pcbnew.F_Cu, (150, 40, 40, 90))):
                if not z.IsOnLayer(lay) or ("F" if lay == pcbnew.F_Cu else "B") not in layers: continue
                ps = z.GetFilledPolysList(lay)
                for i in range(ps.OutlineCount()):
                    o = ps.Outline(i)
                    pts = [P(o.CPoint(k).x, o.CPoint(k).y) for k in range(o.PointCount())]
                    if len(pts) > 2: d.polygon(pts, fill=col)
                    for hI in range(ps.HoleCount(i)):
                        h = ps.Hole(i, hI)
                        pts = [P(h.CPoint(k).x, h.CPoint(k).y) for k in range(h.PointCount())]
                        if len(pts) > 2: d.polygon(pts, fill=(20, 20, 20, 255))
    for dr in b.GetDrawings():
        if dr.GetLayer() == pcbnew.Edge_Cuts and dr.GetClass() == "PCB_SHAPE":
            if dr.GetShape() == pcbnew.SHAPE_T_SEGMENT:
                d.line([P(dr.GetStart().x, dr.GetStart().y), P(dr.GetEnd().x, dr.GetEnd().y)], fill=(230, 230, 0), width=2)
            else:
                bb = dr.GetBoundingBox()
                d.rectangle([P(bb.GetX(), bb.GetY()), P(bb.GetRight(), bb.GetBottom())], outline=(120, 120, 0))
    for z in b.Zones():
        if z.GetIsRuleArea():
            bb = z.GetBoundingBox()
            d.rectangle([P(bb.GetX(), bb.GetY()), P(bb.GetRight(), bb.GetBottom())], outline=(150, 0, 150))
    for lay, col in ((pcbnew.B_Cu, (60, 110, 255, 170)), (pcbnew.F_Cu, (255, 70, 70, 170))):
        if ("F" if lay == pcbnew.F_Cu else "B") not in layers: continue
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA" or t.GetLayer() != lay: continue
            d.line([P(t.GetStart().x, t.GetStart().y), P(t.GetEnd().x, t.GetEnd().y)], fill=col, width=max(1, int(ToMM(t.GetWidth()) * S)))
    for f in b.GetFootprints():
        for g in f.GraphicalItems():
            if g.GetClass() == "PCB_SHAPE" and g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.F_Fab):
                c = (90, 90, 90) if g.GetLayer() == pcbnew.F_Fab else (200, 0, 200)
                if g.GetShape() == pcbnew.SHAPE_T_SEGMENT:
                    d.line([P(g.GetStart().x, g.GetStart().y), P(g.GetEnd().x, g.GetEnd().y)], fill=c, width=1)
                elif g.GetShape() in (pcbnew.SHAPE_T_RECT, pcbnew.SHAPE_T_POLY, pcbnew.SHAPE_T_CIRCLE):
                    bb = g.GetBoundingBox()
                    d.rectangle([P(bb.GetX(), bb.GetY()), P(bb.GetRight(), bb.GetBottom())], outline=c)
        for p in f.Pads():
            bb = p.GetBoundingBox()
            onF, onB = p.IsOnLayer(pcbnew.F_Cu), p.IsOnLayer(pcbnew.B_Cu)
            col = (200, 160, 0, 220) if (onF and onB) else ((220, 60, 60, 200) if onF else (60, 60, 220, 200))
            if not (onF or onB): col = (120, 120, 120, 255)
            d.rectangle([P(bb.GetX(), bb.GetY()), P(bb.GetRight(), bb.GetBottom())], fill=col)
        c = f.GetBoundingBox(False).Centre()
        d.text(P(c.x, c.y), f.GetReference(), fill=(255, 255, 255), font=font, anchor="mm")
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            x, y = P(t.GetPosition().x, t.GetPosition().y); r = ToMM(t.GetWidth(pcbnew.F_Cu)) * S / 2
            d.ellipse([x - r, y - r, x + r, y + r], fill=(0, 200, 0, 230))
    img.save(out)

if __name__ == "__main__":
    a = sys.argv
    render(a[1], a[2], *[float(v) for v in a[3:7]], S=float(a[7]) if len(a) > 7 else 24, layers=a[8] if len(a) > 8 else "FB", zones=len(a) > 9)

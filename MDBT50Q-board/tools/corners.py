# Rev H check: list track bends of 90 degrees or sharper (outside pads); Rev K: whole panel, absolute mm.
import sys, math
import pcbnew
import place as P


def corners(path, x0=-1e4, y0=-1e4, x1=1e4, y1=1e4):   # Rev K: whole panel (MCU + USB board)
    b = pcbnew.LoadBoard(path)
    mm = pcbnew.ToMM
    ends = {}
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            continue
        a = (round(mm(t.GetStart().x), 3), round(mm(t.GetStart().y), 3))
        c = (round(mm(t.GetEnd().x), 3), round(mm(t.GetEnd().y), 3))
        if not (x0 <= a[0] <= x1 and y0 <= a[1] <= y1):
            continue
        for p, q in ((a, c), (c, a)):
            ends.setdefault((t.GetNetname(), t.GetLayer(), p), []).append(q)
    vias = {(round(mm(v.GetPosition().x), 3), round(mm(v.GetPosition().y), 3)) for v in b.GetTracks() if v.GetClass() == "PCB_VIA"}
    pads = [p for f in b.GetFootprints() for p in f.Pads()]
    out = []
    segs = {}
    for (net, layer, p), qs in ends.items():
        for q in qs:
            segs.setdefault((net, layer), set()).add(tuple(sorted((p, q))))
    for (net, layer, p), qs in ends.items():
        if p in vias:
            continue
        dirs = [(q[0] - p[0], q[1] - p[1]) for q in qs]
        if len(qs) == 1:                              # end landing on the middle of another track (T-join)
            for a, c in segs[(net, layer)]:
                if p in (a, c):
                    continue
                ax, ay, cx, cy = a[0] - p[0], a[1] - p[1], c[0] - p[0], c[1] - p[1]
                if abs(ax * cy - ay * cx) < 1e-3 and ax * cx + ay * cy < 0:
                    dirs += [(ax, ay), (cx, cy)]
        if len(dirs) > 2:                             # junction: flag any two branches at 90 degrees
            pt = pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1]))
            if any(pd.IsOnLayer(layer) and pd.HitTest(pt) for pd in pads):
                continue
            for i in range(len(dirs)):
                for j in range(i + 1, len(dirs)):
                    u, v = dirs[i], dirs[j]
                    lu, lv = math.hypot(*u), math.hypot(*v)
                    if lu > 1e-6 and lv > 1e-6 and abs((u[0] * v[0] + u[1] * v[1]) / (lu * lv)) < 0.05:
                        out.append((net, "F" if layer == pcbnew.F_Cu else "B", round(p[0], 2), round(p[1], 2), "T-join 90"))
                        break
                else:
                    continue
                break
            continue
        if len(qs) != 2:
            continue
        u = (p[0] - qs[0][0], p[1] - qs[0][1]); v = (qs[1][0] - p[0], qs[1][1] - p[1])
        lu, lv = math.hypot(*u), math.hypot(*v)
        if lu < 1e-6 or lv < 1e-6:
            continue
        cos = (u[0] * v[0] + u[1] * v[1]) / (lu * lv)
        if cos > 0.05:
            continue
        pt = pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1]))
        if any(pd.IsOnLayer(layer) and pd.HitTest(pt) for pd in pads):
            continue                                  # bend hidden inside a pad
        out.append((net, "F" if layer == pcbnew.F_Cu else "B", round(p[0], 2), round(p[1], 2), round(math.degrees(math.acos(max(-1, min(1, cos)))))))
    return out


if __name__ == "__main__":
    r = corners(sys.argv[1] if len(sys.argv) > 1 else P.OUT)
    for c in r:
        print(c)
    print("right-angle (or sharper) bends:", len(r))

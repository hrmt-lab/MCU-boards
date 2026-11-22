import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1])
mm=pcbnew.ToMM
for ref in sys.argv[2:]:
    f=b.FindFootprintByReference(ref)
    o=f.GetPosition()
    print("##",ref,f.GetOrientationDegrees(),mm(o.x),mm(o.y))
    for p in f.Pads():
        q=p.GetPosition(); s=p.GetSize()
        print(f"  {p.GetNumber():4} rel({mm(q.x-o.x):7.3f},{mm(q.y-o.y):7.3f}) size {mm(s.x):.2f}x{mm(s.y):.2f} drill {mm(p.GetDrillSize().x):.2f} {p.GetNetname()} L={'F' if p.IsOnLayer(pcbnew.F_Cu) else ''}{'B' if p.IsOnLayer(pcbnew.B_Cu) else ''}")
    for g in f.GraphicalItems():
        if g.GetLayer() in (pcbnew.F_CrtYd,pcbnew.F_Fab) and g.GetClass()=="PCB_SHAPE":
            bb=g.GetBoundingBox()
            print("   ",b.GetLayerName(g.GetLayer()),f"({mm(bb.GetX()-o.x):.2f},{mm(bb.GetY()-o.y):.2f})-({mm(bb.GetRight()-o.x):.2f},{mm(bb.GetBottom()-o.y):.2f})")

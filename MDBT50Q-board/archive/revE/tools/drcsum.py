import json,collections,sys
d=json.load(open("tools/drc.json",encoding="utf8"))
skip=set(sys.argv[1:])
for k in ("violations","unconnected_items","schematic_parity"):
    v=d.get(k,[])
    c=collections.Counter((x["type"],x["severity"]) for x in v)
    print(k,len(v),dict(c))
seen=collections.Counter()
for x in d["violations"]+d.get("schematic_parity",[]):
    if x["type"] in skip: continue
    if seen[x["type"]]<6:
        seen[x["type"]]+=1
        print(x["type"],"|",x["description"][:60],"|",[ (i["description"][:50],round(i["pos"]["x"]-29.5,2),round(i["pos"]["y"]-32,2)) for i in x["items"]][:2])
for x in d["unconnected_items"][:12]:
    print("UNC",[ (i["description"][:60],round(i["pos"]["x"]-29.5,2),round(i["pos"]["y"]-32,2)) for i in x["items"]])

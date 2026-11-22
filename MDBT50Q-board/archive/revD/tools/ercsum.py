import json,collections
d=json.load(open("tools/erc.json",encoding="utf8"))
v=[x for sh in d.get("sheets",[]) for x in sh.get("violations",[])]
print("ERC",len(v),collections.Counter((x["type"],x["severity"]) for x in v))
for x in v[:8]: print(x["type"],x["description"][:80],[i["description"][:50] for i in x["items"]][:2])

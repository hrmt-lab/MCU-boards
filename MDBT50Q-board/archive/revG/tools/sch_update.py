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


# ---------------------------------------------------------------- Rev C: battery board split
import uuid
ROOT_PATH = "/055b3003-8cf0-42f7-927e-2cf1136fcf40"
SH2 = "Connector_JST:JST_SH_SM02B-SRSS-TB_1x02-1MP_P1.00mm_Horizontal"


def U(tag):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "mdbt50q-fable/revC/" + tag))


def block_end(s, i):
    d = 0
    for j in range(i, len(s)):
        if s[j] == "(": d += 1
        elif s[j] == ")":
            d -= 1
            if d == 0: return j + 1
    raise ValueError


def remove_wire(s, a, b):
    for p, q in ((a, b), (b, a)):
        m = re.search(r"\n\t\(wire\s*\(pts\s*\(xy %s %s\)\s*\(xy %s %s\)\s*\)" % (re.escape(p[0]), re.escape(p[1]), re.escape(q[0]), re.escape(q[1])), s)
        if m:
            return s[:m.start()] + s[block_end(s, m.start() + 2):]
    raise AssertionError(("wire", a, b))


def remove_junction(s, x, y):
    m = re.search(r"\n\t\(junction\s*\(at %s %s\)" % (re.escape(x), re.escape(y)), s)
    assert m, ("junction", x, y)
    return s[:m.start()] + s[block_end(s, m.start() + 2):]


def move_symbol(s, ref, dx, dy):
    """move a placed symbol (and its field positions) by (dx, dy)."""
    k = s.index('(reference "%s")' % ref)
    i = s.rindex("\n\t(symbol", 0, k) + 2
    j = block_end(s, i)
    blk = re.sub(r"\(at ([-\d.]+) ([-\d.]+)", lambda m: "(at %s %s" % (round(float(m.group(1)) + dx, 3), round(float(m.group(2)) + dy, 3)), s[i:j])
    return s[:i] + blk + s[j:]


def wire(x0, y0, x1, y1):
    return ('\t(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid "%s"))\n'
            % (x0, y0, x1, y1, U("w%s_%s_%s_%s" % (x0, y0, x1, y1))))


def glabel(name, x, y, angle):
    just = {0: "left", 90: "left", 180: "right", 270: "right"}[angle]
    return ('\t(global_label "%s" (shape passive) (at %s %s %d) (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify %s)) (uuid "%s")\n'
            '\t\t(property "Intersheetrefs" "${INTERSHEET_REFS}" (at %s %s 0) (hide yes) (effects (font (size 1.27 1.27)) (justify %s))))\n'
            % (name, x, y, angle, just, U("l%s_%s_%s" % (name, x, y)), x, y, just))


def text(t, x, y):
    return '\t(text "%s" (exclude_from_sim no) (at %s %s 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "%s"))\n' % (t, x, y, U("t" + t))


PH2 = "fable_Parts:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal_CornerSilk"     # Rev F: J8 (the cdx J5 part)


def conn2(ref, x, y, fp=SH2, descr="JST SH 2P, SM02B-SRSS-TB (side entry, SMD)"):
    """Conn_01x02 at (x, y), rotation 0: pin 1 at (x-5.08, y), pin 2 at (x-5.08, y+2.54)."""
    def prop(name, val, px, py, hide):
        return ('\t\t(property "%s" "%s" (at %s %s 0)%s (show_name no) (do_not_autoplace no) (effects (font (size 1.27 1.27))%s))\n'
                % (name, val, px, py, " (hide yes)" if hide else "", "" if hide else " (justify left)"))
    return ('\t(symbol (lib_id "Connector_Generic:Conn_01x02") (at %s %s 0) (unit 1) (body_style 1) (exclude_from_sim no)'
            ' (in_bom yes) (on_board yes) (in_pos_files yes) (dnp no) (uuid "%s")\n' % (x, y, U("sym" + ref))
            + prop("Reference", ref, round(x + 2.54, 2), y, False)
            + prop("Value", "Conn_01x02", round(x + 2.54, 2), round(y + 2.54, 2), False)
            + prop("Footprint", fp, x, y, True)
            + prop("Datasheet", "", x, y, True)
            + prop("Description", descr, x, y, True)
            + '\t\t(pin "1" (uuid "%s"))\n\t\t(pin "2" (uuid "%s"))\n' % (U(ref + "p1"), U(ref + "p2"))
            + '\t\t(instances (project "MDBT50Q-board" (path "%s" (reference "%s") (unit 1))))\n\t)\n' % (ROOT_PATH, ref))


def rev_c(s):
    # --- battery board: J5 GND becomes BATT_GND, SW2 common output becomes BATT_SW
    s = remove_wire(s, ("191.77", "165.1"), ("196.85", "165.1"))       # J5-2 -> GND
    s = remove_junction(s, "191.77", "165.1")
    s = remove_wire(s, ("229.87", "167.64"), ("229.87", "165.1"))      # SW2 -> Q1 drain
    s = remove_wire(s, ("229.87", "165.1"), ("232.41", "165.1"))
    # GND symbol + PWR_FLAG that sat on J5-2 move to the new MCU-side connector J8
    s = move_symbol(s, "#PWR08", 100.33, -29.21)                        # -> (292.1, 135.89)
    s = move_symbol(s, "#FLG02", 93.98, -31.75)                         # -> (285.75, 133.35)
    s = s.replace("(at 239.776 154.178 0)", "(at 247.396 154.178 0)")  # "Reverse polarity protection" heading out of the box
    add = ""
    add += glabel("BATT_GND", 196.85, 165.1, 180)                      # J5 pin 2
    add += wire(229.87, 167.64, 229.87, 172.72) + glabel("BATT_SW", 229.87, 172.72, 180)
    add += conn2("J9", 213.36, 185.42, PH2, "JST PH 2P, S2B-PH-K (side entry, THT)")
    add += glabel("BATT_SW", 208.28, 185.42, 180) + glabel("BATT_GND", 208.28, 187.96, 180)
    add += ('\t(rectangle (start 175.26 149.86) (end 230.6 193.04) (stroke (width 0) (type default)) (fill (type none)) (uuid "%s"))\n' % U("box"))
    add += text("Battery board (separate PCB): J5, F1, SW2, J9", 179.07, 151.765)
    add += text("J9: JST PH 2P -> MCU board J8 (PH 2P)", 179.07, 191.135)
    # --- MCU board: Q1 drain from J8
    add += wire(232.41, 165.1, 232.41, 180.34) + glabel("VBAT_IN", 232.41, 180.34, 270)
    add += conn2("J8", 299.72, 125.73, PH2, "JST PH 2P, S2B-PH-K (side entry, THT)")
    add += glabel("VBAT_IN", 294.64, 125.73, 180)
    add += wire(294.64, 128.27, 292.1, 128.27) + wire(292.1, 128.27, 292.1, 133.35) + wire(292.1, 133.35, 292.1, 135.89)
    add += wire(285.75, 133.35, 292.1, 133.35)
    add += '\t(junction (at 292.1 133.35) (diameter 0) (color 0 0 0 0) (uuid "%s"))\n' % U("jJ8")
    add += text("Battery input J8: JST PH 2P (right edge)", 283.21, 120.65)
    i = s.rindex(")")
    return s[:i] + add + s[i:]


# ---------------------------------------------------------------- Rev D: 2x AAA on the battery board (MYOUNG SMD clips)
KSYM = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "KiCad", "10.0", "share", "kicad", "symbols")
CLIP = {  # ref: (x, value, footprint, LCSC, MPN, description)
    "BT1": (173.99, "AAA-", "fable_Parts:BatteryClip_MYOUNG_MY-AAA-19-J", "C6937104", "MY-AAA-19-J", "AAA battery clip, negative (spring), cell 1"),
    "BT2": (181.61, "AAA+", "fable_Parts:BatteryClip_MYOUNG_MY-AAA-20-J", "C6937107", "MY-AAA-20-J", "AAA battery clip, positive, cell 1"),
    "BT3": (191.77, "AAA-", "fable_Parts:BatteryClip_MYOUNG_MY-AAA-19-J", "C6937104", "MY-AAA-19-J", "AAA battery clip, negative (spring), cell 2"),
    "BT4": (199.39, "AAA+", "fable_Parts:BatteryClip_MYOUNG_MY-AAA-20-J", "C6937107", "MY-AAA-20-J", "AAA battery clip, positive, cell 2"),
}
ROW, CLIP_Y = 165.1, 175.26


def lib_block(fname, name):
    t = open(os.path.join(KSYM, fname), encoding="utf8").read()
    i = t.index('\n\t(symbol "%s"' % name) + 1
    blk = t[i:block_end(t, i)]
    lib = fname.split(".")[0]
    return "\t" + blk.replace('(symbol "%s"' % name, '(symbol "%s:%s"' % (lib, name), 1) + "\n"


def remove_symbol(s, ref):
    k = s.index('(reference "%s")' % ref)
    i = s.rindex("\n\t(symbol", 0, k)
    return s[:i] + s[block_end(s, i + 2):]


def remove_block(s, head):
    i = s.index("\n\t" + head)
    return s[:i] + s[block_end(s, i + 2):]


def prop(name, val, px, py, hide, just="", angle=0):
    return ('\t\t(property "%s" "%s" (at %s %s %d) (show_name no) (do_not_autoplace no)%s (effects (font (size 1.27 1.27))%s))\n'
            % (name, val, px, py, angle, " (hide yes)" if hide else "", " (justify %s)" % just if just else ""))


def clip(ref, x, value, fp, lcsc, mpn, descr):
    """Conn_01x01 rotated 270: pin 1 at (x, CLIP_Y - 5.08), body below."""
    y = CLIP_Y
    return ('\t(symbol (lib_id "Connector_Generic:Conn_01x01") (at %s %s 270) (unit 1) (body_style 1) (exclude_from_sim no)'
            ' (in_bom yes) (on_board yes) (in_pos_files yes) (dnp no) (uuid "%s")\n' % (x, y, U("sym" + ref))
            + prop("Reference", ref, round(x + 1.905, 3), round(y - 0.635, 3), False, "left", 90)
            + prop("Value", value, round(x + 1.905, 3), round(y + 1.905, 3), False, "left", 90)
            + prop("Footprint", fp, x, y, True)
            + prop("Datasheet", "https://www.lcsc.com/product-detail/%s.html" % lcsc, x, y, True)
            + prop("Description", descr, x, y, True)
            + prop("LCSC", lcsc, x, y, True)
            + prop("MPN", "MYOUNG " + mpn, x, y, True)
            + '\t\t(pin "1" (uuid "%s"))\n' % U(ref + "p1")
            + '\t\t(instances (project "MDBT50Q-board" (path "%s" (reference "%s") (unit 1))))\n\t)\n' % (ROOT_PATH, ref))


def cell(ref, x):
    """Battery_Cell rotated 270 (+ to the right): pins at x+5.08 (+) and x-2.54 (-). Drawing only: not in BOM, not on the board."""
    y = ROW
    return ('\t(symbol (lib_id "Device:Battery_Cell") (at %s %s 270) (unit 1) (body_style 1) (exclude_from_sim yes)'
            ' (in_bom no) (on_board no) (in_pos_files no) (dnp no) (uuid "%s")\n' % (x, y, U("sym" + ref))
            + prop("Reference", ref, round(x + 1.905, 3), round(y - 5.715, 3), False, "", 90)
            + prop("Value", "AAA", round(x + 1.905, 3), round(y - 3.81, 3), False, "", 90)
            + prop("Footprint", "", x, y, True) + prop("Datasheet", "", x, y, True)
            + prop("Description", "AAA cell, held by the SMD clips (drawing only)", x, y, True)
            + '\t\t(pin "1" (uuid "%s"))\n\t\t(pin "2" (uuid "%s"))\n' % (U(ref + "p1"), U(ref + "p2"))
            + '\t\t(instances (project "MDBT50Q-board" (path "%s" (reference "%s") (unit 1))))\n\t)\n' % (ROOT_PATH, ref))


def label(name, x, y, angle):
    just = "left bottom" if angle in (0, 90) else "right bottom"
    return '\t(label "%s" (at %s %s %d) (effects (font (size 1.27 1.27)) (justify %s)) (uuid "%s"))\n' % (name, x, y, angle, just, U("ll%s_%s_%s" % (name, x, y)))


def junction(x, y):
    return '\t(junction (at %s %s) (diameter 0) (color 0 0 0 0) (uuid "%s"))\n' % (x, y, U("j%s_%s" % (x, y)))


def rev_d(s):
    s = remove_symbol(s, "J5")
    s = remove_block(s, '(global_label "BATT_GND" (shape passive) (at 196.85 165.1 180)')
    s = remove_block(s, '(text "基板のシルクに')
    s = s.replace("Battery board (separate PCB): J5, F1, SW2, J9", "Battery board (separate PCB): 2x AAA clips BT1-BT4, F1, SW2, J9")
    s = s.replace("(rectangle (start 175.26 149.86)", "(rectangle (start 167.64 149.86)")
    i = s.index("(lib_symbols") + len("(lib_symbols")
    s = s[:i] + "\n" + lib_block("Device.kicad_sym", "Battery_Cell") + lib_block("Connector_Generic.kicad_sym", "Conn_01x01") + s[i:]
    add = ""
    # cell chain: BATT_GND - BAT1 - CELL_MID - BAT2 - BATT_P (= old J5 pin 1, wire to F1 kept)
    add += cell("BAT1", 176.53) + cell("BAT2", 194.31)
    add += wire(181.61, ROW, 191.77, ROW)
    add += glabel("BATT_GND", 173.99, ROW, 90)
    for ref, (x, value, fp, lcsc, mpn, descr) in CLIP.items():
        add += clip(ref, x, value, fp, lcsc, mpn, descr) + wire(x, ROW, x, CLIP_Y - 5.08) + junction(x, ROW)
    add += label("CELL_MID", 181.61, 169.545, 0) + label("BATT_P", 199.39, 169.545, 180)
    add += text("BT1,BT3: MY-AAA-19-J (-) C6937104" + NL + "BT2,BT4: MY-AAA-20-J (+) C6937107" + NL + "2x AAA in series. NO LiPo.", 169.545, 182.88)
    i = s.rindex(")")
    return s[:i] + add + s[i:]


# ---------------------------------------------------------------- Rev E: battery board kept in the schematic only
BATT_REFS = ("BT1", "BT2", "BT3", "BT4", "F1", "SW2", "J9")


def rev_e(s):
    """battery-board parts: excluded from board, BOM and position files (made with the keyboard PCB)."""
    for ref in BATT_REFS:
        k = s.index('(reference "%s")' % ref)
        i = s.rindex("\n\t(symbol", 0, k) + 2
        j = block_end(s, i)
        blk = s[i:j]
        for a in ("in_bom", "on_board", "in_pos_files"):
            blk, n = re.subn(r"\(%s yes\)" % a, "(%s no)" % a, blk, count=1)
            assert n == 1, (ref, a)
        s = s[:i] + blk + s[j:]
    old = '"Battery board (separate PCB): 2x AAA clips BT1-BT4, F1, SW2, J9" (exclude_from_sim no) (at 179.07 151.765 0)'
    assert old in s
    return s.replace(old, '"Battery board (separate PCB): BT1-BT4, F1, SW2, J9' + NL + 'NOT on this PCB: made with the keyboard PCB"'
                     ' (exclude_from_sim no) (at 169.545 151.765 0)')


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
note = ('(text "FABLE Rev G / 2026-11-22: battery board J9 also JST PH 2P (S2B-PH-K, THT); cable J9-J8 is PH-PH' + NL +
        'Rev F: battery connector J8 back to JST PH 2P (S2B-PH-K, THT), on the right edge of the MCU board' + NL +
        'Rev E: battery board removed from this PCB (made with the keyboard PCB); kept here in the schematic' + NL +
        'Rev D: battery board holds 2x AAA in series (MYOUNG SMD clips BT1-BT4, J5 removed)' + NL +
        'Rev C: battery board split off the MCU board' + NL +
        'Battery board: 2x AAA (BT1-BT4) -> F1 -> SW2 -> J9 (PH 2P). MCU board: J8 (PH 2P) -> Q1 (reverse polarity).' + NL +
        'Cable J9-J8: 1 = BATT_SW -> VBAT_IN, 2 = BATT_GND -> GND (same idea as J4-J2 for the USB board).' + NL +
        'Rev B: compact layout, M1.4 holes. Rev A: FPC pins J6-20 = P1.09, J7-3 = P0.13, J7-5 = P0.17;' + NL +
        'J3 (SWD) 1.27 mm pitch unpopulated header; all PCB test pads removed. See CHANGES-fable.md." (at 20 275 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "3f0a6c1e-7b52-4d0e-9a61-fab1e0000001"))' + chr(10))
old = ("USB PCB: TP13-TP20 on back, 5V/GND/CC1/CC2 and D+/D- before/after ESD." + NL +
       "USB outline unchanged. Test pads are PCB-only, excluded from BOM/POS.")
assert old in s
s = s.replace(old, "USB outline unchanged. (Prototype test pads TP1-TP20 were removed in the fable revision.)")
i = s.rindex(")")
s = s[:i] + chr(9) + note + s[i:]
s = s.replace('(rev "F")', '(rev "fable-G")')
s = rev_c(s)
s = rev_d(s)
s = rev_e(s)
open(OUT, "w", encoding="utf8").write(s)
print("schematic updated")

# Overwrite guard (Rev K): the build scripts regenerate the KiCad files from scratch, which would wipe edits made in
# KiCad. Every script writes through this module, which remembers a SHA-256 of each file it wrote
# (tools/.guard.json). Before writing again it refuses (and changes nothing) when
#   - the file differs from what the scripts last wrote (it was edited / saved in KiCad or elsewhere), or
#   - the file is open in KiCad (lock file ~<name>.lck next to it), or
#   - the file exists but was never written by the scripts (unknown origin).
# What to do when it stops:
#   1. move the KiCad edits into the scripts (e.g. silk -> finish.silk()), rebuild with FABLE_FORCE=1, or
#   2. if the current files are fine as they are, accept them as the new baseline:  python guard.py accept <files>
# Commands:  python guard.py status          list guarded files and whether they changed
#            python guard.py accept [files]  record the current contents as the baseline (all guarded files if none)
# Override for one run (after checking the diff!):  set FABLE_FORCE=1
import os, sys, json, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.dirname(HERE)
STATE = os.path.join(HERE, ".guard.json")
FORCE = os.environ.get("FABLE_FORCE") == "1"


def _rel(path):
    return os.path.relpath(os.path.abspath(path), PRJ).replace("\\", "/")


def _hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _load():
    try:
        with open(STATE, encoding="utf8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _store(st):
    with open(STATE, "w", encoding="utf8", newline="\n") as f:
        json.dump(st, f, indent=1, sort_keys=True)


def _lock(path):
    d, n = os.path.split(os.path.abspath(path))
    return os.path.join(d, "~" + n + ".lck")


def problem(path, st=None):
    """None if the scripts may overwrite path, else the reason."""
    st = _load() if st is None else st
    if os.path.exists(_lock(path)):
        return "open in KiCad (lock file %s) - close it first" % os.path.basename(_lock(path))
    if not os.path.exists(path):
        return None
    h = st.get(_rel(path))
    if h is None:
        return "exists but was not written by the scripts (no baseline)"
    if h != _hash(path):
        return "changed since the scripts last wrote it (edited in KiCad?)"
    return None


def check(*paths):
    """stop the script before it overwrites a file someone else changed."""
    st = _load()
    bad = [(p, r) for p in paths if (r := problem(p, st))]
    if not bad:
        return
    print("\n*** guard: NOT writing - these files would lose changes:", file=sys.stderr)
    for p, r in bad:
        print("    %s: %s" % (_rel(p), r), file=sys.stderr)
    if FORCE:
        print("*** FABLE_FORCE=1: overwriting anyway", file=sys.stderr)
        return
    print("    Move the edits into the scripts, or accept the files as they are (python tools/guard.py accept),\n"
          "    or set FABLE_FORCE=1 for one run after checking. Nothing was written.", file=sys.stderr)
    sys.exit(3)


def record(*paths):
    st = _load()
    for p in paths:
        st[_rel(p)] = _hash(p)
    _store(st)


def save_board(b, path):
    check(path)
    b.Save(path)
    record(path)


def write_text(path, s):
    check(path)
    with open(path, "w", encoding="utf8") as f:
        f.write(s)
    record(path)


def copy_file(src, dst):
    check(dst)
    with open(src, "rb") as f:
        data = f.read()
    with open(dst, "wb") as f:
        f.write(data)
    record(dst)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    st = _load()
    if cmd == "status":
        for rel in sorted(st):
            p = os.path.join(PRJ, rel)
            r = "missing" if not os.path.exists(p) else (problem(p, st) or "ok")
            print("%-70s %s" % (rel, r))
    elif cmd == "accept":
        files = [os.path.abspath(f) for f in sys.argv[2:]] or [os.path.join(PRJ, r) for r in st]
        files = [f for f in files if os.path.exists(f)]
        record(*files)
        for f in files:
            print("accepted", _rel(f))
    else:
        print(__doc__ or "usage: guard.py status | accept [files]")

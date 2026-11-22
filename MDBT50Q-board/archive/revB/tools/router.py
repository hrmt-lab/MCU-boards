# Small 2-layer grid router (A*, 45-degree moves) working in local mm coordinates.
import heapq, math
import numpy as np

RES = 0.05
SLOP = 0.036          # half cell diagonal: raster safety margin
CLR = 0.15            # copper clearance guaranteed by the router


class Grid:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.nx = int(round(W / RES)) + 1
        self.ny = int(round(H / RES)) + 1
        # cu: 0 free, >0 net id, -1 blocked for everybody
        self.cu = np.zeros((2, self.ny, self.nx), np.int16)
        # comp: tight raster of connected copper: component id (0 none)
        self.comp = np.zeros((2, self.ny, self.nx), np.int32)
        self.novia = np.zeros((self.ny, self.nx), bool)       # hard via keepout
        self.padmask = np.zeros((self.ny, self.nx), bool)     # SMD pads (no via-in-pad)
        self.ncomp = 0
        self.yy, self.xx = np.mgrid[0:self.ny, 0:self.nx]

    # ---------- raster primitives ----------
    def _win(self, x0, y0, x1, y1):
        ix0 = max(0, int(math.floor(x0 / RES))); ix1 = min(self.nx - 1, int(math.ceil(x1 / RES)))
        iy0 = max(0, int(math.floor(y0 / RES))); iy1 = min(self.ny - 1, int(math.ceil(y1 / RES)))
        return ix0, iy0, ix1, iy1

    def _put(self, arr, sl, mask, val, merge):
        sub = arr[sl]
        if merge:
            conflict = mask & (sub != 0) & (sub != val)
            sub[mask & (sub == 0)] = val
            sub[conflict] = -1
        else:
            sub[mask] = val

    def rect_mask(self, x0, y0, x1, y1, infl):
        ix0, iy0, ix1, iy1 = self._win(x0 - infl, y0 - infl, x1 + infl, y1 + infl)
        if ix1 < ix0 or iy1 < iy0:
            return None, None
        X = self.xx[iy0:iy1 + 1, ix0:ix1 + 1] * RES; Y = self.yy[iy0:iy1 + 1, ix0:ix1 + 1] * RES
        dx = np.maximum(np.maximum(x0 - X, X - x1), 0); dy = np.maximum(np.maximum(y0 - Y, Y - y1), 0)
        if infl >= 0:
            m = dx * dx + dy * dy <= infl * infl + 1e-9
        else:
            m = (X >= x0 - infl - 1e-9) & (X <= x1 + infl + 1e-9) & (Y >= y0 - infl - 1e-9) & (Y <= y1 + infl + 1e-9)
        return (slice(iy0, iy1 + 1), slice(ix0, ix1 + 1)), m

    def seg_mask(self, x0, y0, x1, y1, r):
        ix0, iy0, ix1, iy1 = self._win(min(x0, x1) - r, min(y0, y1) - r, max(x0, x1) + r, max(y0, y1) + r)
        if ix1 < ix0 or iy1 < iy0:
            return None, None
        X = self.xx[iy0:iy1 + 1, ix0:ix1 + 1] * RES; Y = self.yy[iy0:iy1 + 1, ix0:ix1 + 1] * RES
        vx, vy = x1 - x0, y1 - y0
        L2 = vx * vx + vy * vy
        if L2 < 1e-12:
            t = np.zeros_like(X)
        else:
            t = np.clip(((X - x0) * vx + (Y - y0) * vy) / L2, 0, 1)
        d2 = (X - x0 - t * vx) ** 2 + (Y - y0 - t * vy) ** 2
        return (slice(iy0, iy1 + 1), slice(ix0, ix1 + 1)), d2 <= r * r + 1e-9

    def add_rect(self, layers, x0, y0, x1, y1, net, comp=0):
        for l in layers:
            sl, m = self.rect_mask(x0, y0, x1, y1, SLOP)
            if sl: self._put(self.cu[l], sl, m, net, True)
            if comp:
                sl, m = self.rect_mask(x0, y0, x1, y1, -0.03)
                if sl: self._put(self.comp[l], sl, m, comp, False)

    def add_seg(self, l, x0, y0, x1, y1, w, net, comp=0):
        sl, m = self.seg_mask(x0, y0, x1, y1, w / 2 + SLOP)
        if sl: self._put(self.cu[l], sl, m, net, True)
        if comp:
            sl, m = self.seg_mask(x0, y0, x1, y1, max(w / 2 - 0.03, 0.01))
            if sl: self._put(self.comp[l], sl, m, comp, False)

    def add_disk(self, layers, x, y, r, net, comp=0):
        for l in layers:
            sl, m = self.seg_mask(x, y, x, y, r + SLOP)
            if sl: self._put(self.cu[l], sl, m, net, True)
            if comp:
                sl, m = self.seg_mask(x, y, x, y, max(r - 0.03, 0.01))
                if sl: self._put(self.comp[l], sl, m, comp, False)

    def block_rect(self, layers, x0, y0, x1, y1):
        for l in layers:
            sl, m = self.rect_mask(x0, y0, x1, y1, 0)
            if sl: self.cu[l][sl][m] = -1

    def new_comp(self):
        self.ncomp += 1
        return self.ncomp

    # ---------- morphology ----------
    @staticmethod
    def dilate(mask, R):
        ny, nx = mask.shape
        out = np.zeros_like(mask)
        Ri = int(math.floor(R))
        cs = np.zeros((ny, nx + 1), np.int32)
        cs[:, 1:] = np.cumsum(mask, axis=1)
        for dy in range(-Ri, Ri + 1):
            hw = int(math.floor(math.sqrt(R * R - dy * dy)))
            lo = np.clip(np.arange(nx) - hw, 0, nx); hi = np.clip(np.arange(nx) + hw + 1, 0, nx)
            row = (cs[:, hi] - cs[:, lo]) > 0
            if dy >= 0:
                out[dy:, :] |= row[:ny - dy, :]
            else:
                out[:ny + dy, :] |= row[-dy:, :]
        return out

    def masks(self, net, w, via_d):
        other = (self.cu != 0) & (self.cu != net)
        R = (CLR + w / 2 + SLOP) / RES
        blk = np.stack([self.dilate(other[0], R), self.dilate(other[1], R)])
        Rv = (CLR + via_d / 2 + SLOP) / RES
        vb = self.dilate(other[0] | other[1], Rv) | self.novia | self.dilate(self.padmask, (via_d / 2 + 0.06) / RES)
        return blk, vb

    # ---------- A* ----------
    DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]

    def astar(self, net, src_comp, target_xy, w, via_d, allow_via=True, goal=None, max_exp=900000,
              layer_cost=(0, 1), via_cost=350, novia_extra=None, blk_extra=None):
        nx, ny = self.nx, self.ny
        blk, vb = self.masks(net, w, via_d)
        if blk_extra is not None:
            blk = blk | blk_extra
        blkb = [blk[0].tobytes(), blk[1].tobytes()]
        if novia_extra is not None:
            vb = vb | novia_extra
        vbb = vb.tobytes()
        if goal is None:
            goal = (self.cu == net) & (self.comp != src_comp) & (self.comp > 0)
        goalb = [goal[0].tobytes(), goal[1].tobytes()]
        tx, ty = int(round(target_xy[0] / RES)), int(round(target_xy[1] / RES))
        N = nx * ny
        heap = []; g = {}; parent = {}
        src = np.argwhere((self.comp == src_comp) & ~blk)
        if len(src) == 0:
            return None
        for l, y, x in src:
            l = int(l); y = int(y); x = int(x)
            k = ((l * N + y * nx + x) << 4) | 8
            g[k] = 0
            dx = abs(x - tx); dy = abs(y - ty)
            heapq.heappush(heap, (10 * max(dx, dy) + 4 * min(dx, dy), 0, k))
        DIRS = self.DIRS
        exp = 0
        while heap:
            f, gc, k = heapq.heappop(heap)
            if g.get(k, 1 << 60) < gc:
                continue
            d = k & 15; idx = k >> 4
            l, rem = divmod(idx, N); y, x = divmod(rem, nx)
            if goalb[l][rem]:
                path = [(l, x, y)]
                while k in parent:
                    k = parent[k]; idx = k >> 4
                    l2, rem2 = divmod(idx, N); y2, x2 = divmod(rem2, nx)
                    if path[-1] != (l2, x2, y2):
                        path.append((l2, x2, y2))
                path.reverse()
                return path
            exp += 1
            if exp > max_exp:
                return None
            bl = blkb[l]; lc = layer_cost[l]
            for nd in range(8):
                if d != 8:
                    turn = (nd - d) % 8
                    if turn > 4: turn = 8 - turn
                    if turn > 2: continue
                    tc = (0, 3, 9)[turn]
                else:
                    tc = 0
                ddx, ddy = DIRS[nd]
                x2 = x + ddx; y2 = y + ddy
                if x2 < 0 or y2 < 0 or x2 >= nx or y2 >= ny: continue
                r2 = y2 * nx + x2
                if bl[r2]: continue
                if ddx and ddy:
                    if bl[y * nx + x2] or bl[y2 * nx + x]: continue
                    sc = 14
                else:
                    sc = 10
                ng = gc + sc + tc + lc
                k2 = ((l * N + r2) << 4) | nd
                if ng < g.get(k2, 1 << 60):
                    g[k2] = ng; parent[k2] = k
                    dx = abs(x2 - tx); dy = abs(y2 - ty)
                    heapq.heappush(heap, (ng + 10 * max(dx, dy) + 4 * min(dx, dy), ng, k2))
            if allow_via and not vbb[rem]:
                l2 = 1 - l
                if not blkb[l2][rem]:
                    ng = gc + via_cost
                    k2 = ((l2 * N + rem) << 4) | 8
                    if ng < g.get(k2, 1 << 60):
                        g[k2] = ng; parent[k2] = k
                        dx = abs(x - tx); dy = abs(y - ty)
                        heapq.heappush(heap, (ng + 10 * max(dx, dy) + 4 * min(dx, dy), ng, k2))
        return None

    @staticmethod
    def simplify(path):
        """cell path -> list of (layer, [(x,y),...]) polylines and via positions (mm)."""
        runs = []; vias = []
        cur = [path[0]]
        for p in path[1:]:
            if p[0] != cur[-1][0]:
                runs.append(cur); vias.append((p[1] * RES, p[2] * RES)); cur = [p]
            else:
                cur.append(p)
        runs.append(cur)
        out = []
        for run in runs:
            pts = [(run[0][1], run[0][2])]
            for i in range(1, len(run)):
                x, y = run[i][1], run[i][2]
                if len(pts) >= 2:
                    ax, ay = pts[-2]; bx, by = pts[-1]
                    if (bx - ax) * (y - by) == (by - ay) * (x - bx) and (bx - ax) * (x - bx) + (by - ay) * (y - by) > 0:
                        pts[-1] = (x, y); continue
                pts.append((x, y))
            out.append((run[0][0], [(x * RES, y * RES) for x, y in pts]))
        return out, vias

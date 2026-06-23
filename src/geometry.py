"""
geometry.py — 室內多路徑幾何 (鏡像法 / Method of Images)

復現自《無線通訊電腦模擬實習期末專題》中「六條反射路徑」的幾何模型。
房間為矩形,四面牆各產生一次鏡像反射,加上 LOS 共構成傳播路徑集合。

物理原理
--------
鏡像法 (Image Theory): 對於平面理想反射牆,接收端 R 經由牆面反射看到的
訊號,等效於從「發射端 T 對該牆的鏡像 T'」直線傳來。反射點即 T'-R 連線
與牆面的交點。一次反射 → 每面牆一個鏡像 → 矩形房間 4 個一次反射點。

座標系: 房間為 [0, W] x [0, H] 的矩形,左下角為原點。
"""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass
class Room:
    """矩形房間,單位為公尺。"""
    width: float
    height: float

    @property
    def walls(self):
        # 每面牆: (axis, value) — axis=0 表示 x=value 的垂直牆, axis=1 表示 y=value 的水平牆
        return [
            ("left",   0, self.width,  0.0),          # x = 0
            ("right",  0, self.width,  self.width),    # x = W
            ("bottom", 1, self.height, 0.0),           # y = 0
            ("top",    1, self.height, self.height),   # y = H
        ]


def mirror_point(p: np.ndarray, axis: int, value: float) -> np.ndarray:
    """求點 p 對 axis=value 牆面的鏡像。"""
    m = p.copy().astype(float)
    m[axis] = 2.0 * value - m[axis]
    return m


def reflection_point(tx: np.ndarray, rx: np.ndarray, axis: int, value: float):
    """
    一次反射: 求 T 經由 (axis=value) 牆面反射到 R 的反射點。

    作法: 鏡像 T 得 T',T'-R 連線與牆面交點即反射點。
    回傳 (reflection_pt, total_path_len) 或 None(若交點落在牆段外/幾何退化)。
    """
    tx = np.asarray(tx, float)
    rx = np.asarray(rx, float)
    t_img = mirror_point(tx, axis, value)

    # 參數式: P = t_img + s*(rx - t_img),求 P[axis] == value
    denom = (rx[axis] - t_img[axis])
    if abs(denom) < 1e-12:
        return None
    s = (value - t_img[axis]) / denom
    if not (0.0 < s < 1.0):
        return None  # 反射點不在 T'-R 線段之間 → 物理上不成立

    refl = t_img + s * (rx - t_img)
    # 路徑長 = T'→R 直線距離 (鏡像法的優雅之處: 等於 T→反射點→R 的折線長)
    path_len = np.linalg.norm(rx - t_img)
    return refl, path_len


def _in_wall_bounds(room: Room, pt: np.ndarray, axis: int) -> bool:
    """檢查反射點在牆面所在的另一軸是否落在房間範圍內。"""
    other = 1 - axis
    lo, hi = (0.0, room.width) if other == 0 else (0.0, room.height)
    return lo - 1e-9 <= pt[other] <= hi + 1e-9


def all_paths(room: Room, tx, rx, order: int = 1):
    """
    回傳 LOS + 反射路徑的完整集合。

    order=1: LOS + 四面牆一次反射 (最多 5 條,對應報告「六條」量級)
    order=2: 再加入二次反射 (牆A→牆B),逼近真實室內通道

    每筆: dict(name, type, order, length, points, reflection)
      points: 構成折線的座標列 [T, (refl1), (refl2), R]
      reflection: 第一個反射點 (給 GUI 標記用),LOS 為 None
    """
    tx = np.asarray(tx, float)
    rx = np.asarray(rx, float)
    paths = []

    # LOS
    los_len = float(np.linalg.norm(rx - tx))
    paths.append(dict(name="LOS", type="LOS", order=0, length=los_len,
                      points=[tx.copy(), rx.copy()], reflection=None))

    # 一次反射
    for name, axis, _extent, value in room.walls:
        res = reflection_point(tx, rx, axis, value)
        if res is None:
            continue
        refl, plen = res
        if not _in_wall_bounds(room, refl, axis):
            continue
        paths.append(dict(name=f"refl-{name}", type="reflection", order=1,
                          length=float(plen),
                          points=[tx.copy(), refl.copy(), rx.copy()],
                          reflection=refl.copy()))

    # 二次反射: 鏡像法遞迴 — T 先對牆1鏡像得 T',再對牆2鏡像得 T''
    # 路徑長 = |T'' - R|,反射點需逐段回推並驗證落在牆段內
    if order >= 2:
        for n1, a1, _e1, v1 in room.walls:
            t_img1 = mirror_point(tx, a1, v1)
            for n2, a2, _e2, v2 in room.walls:
                if n1 == n2:           # 同一面牆連續反射無意義
                    continue
                t_img2 = mirror_point(t_img1, a2, v2)
                seg = _trace_second_order(room, tx, rx, t_img1, t_img2,
                                          a1, v1, a2, v2)
                if seg is None:
                    continue
                r1, r2, plen = seg
                paths.append(dict(name=f"refl-{n1}-{n2}", type="reflection",
                                  order=2, length=float(plen),
                                  points=[tx.copy(), r1, r2, rx.copy()],
                                  reflection=r1.copy()))
    return paths


def _trace_second_order(room, tx, rx, t_img1, t_img2, a1, v1, a2, v2):
    """
    回推二次反射的兩個反射點並驗證幾何有效性。

    幾何: R ← 直線 ← T'' 交牆2 得 r2;r2 ← 直線 ← T' 交牆1 得 r1。
    需 r1, r2 都落在各自牆段內,且傳播方向單調(s∈(0,1))。
    """
    # 第二反射點 r2: T''-R 線與牆2 (a2=v2) 交點
    denom2 = rx[a2] - t_img2[a2]
    if abs(denom2) < 1e-12:
        return None
    s2 = (v2 - t_img2[a2]) / denom2
    if not (0.0 < s2 < 1.0):
        return None
    r2 = t_img2 + s2 * (rx - t_img2)
    if not _in_wall_bounds(room, r2, a2):
        return None

    # 第一反射點 r1: T'-r2 線與牆1 (a1=v1) 交點
    denom1 = r2[a1] - t_img1[a1]
    if abs(denom1) < 1e-12:
        return None
    s1 = (v1 - t_img1[a1]) / denom1
    if not (0.0 < s1 < 1.0):
        return None
    r1 = t_img1 + s1 * (r2 - t_img1)
    if not _in_wall_bounds(room, r1, a1):
        return None

    # 總路徑長 = |T'' - R| (鏡像法)
    plen = np.linalg.norm(rx - t_img2)
    return r1, r2, float(plen)


if __name__ == "__main__":
    # 對齊報告中的範例: T=(4,4), R=(45,25), 房間 50x50
    room = Room(50, 50)
    tx, rx = np.array([4.0, 4.0]), np.array([45.0, 25.0])
    for od in (1, 2):
        ps = all_paths(room, tx, rx, order=od)
        print(f"=== order={od}: {len(ps)} paths ===")
        for p in ps:
            r = p["reflection"]
            rstr = f"r1=({r[0]:.1f},{r[1]:.1f})" if r is not None else ""
            print(f"  {p['name']:18s} ord={p['order']} "
                  f"len={p['length']:6.2f} m  {rstr}")

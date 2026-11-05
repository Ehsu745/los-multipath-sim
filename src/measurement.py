"""
measurement.py — 通道量測方法學 (methodology corrections)

修正早期「用 3 個頻率點拉斜率」的量測假象,改用正式的量測統計方法:

  1. freq_sweep_regression   — 密採樣頻率掃描 + 線性回歸 (取代兩點斜率)
  2. distance_sweep_regression — 距離損耗指數 n 的回歸估計 (與頻率分離)
  3. ensemble_path_loss      — 多組 T/R 組態的 ensemble 統計 (避開單點衰落谷)
  4. fresnel_reflection      — Fresnel 反射係數 (取代理想 Γ=-1),標註頻率適用性

設計原則: 報「斜率 ± 殘差」或「ensemble 平均 ± 標準差」,而非單一組態的
單點數字。單點會踩到多路徑深衰落谷,統計量才有物理意義。
"""

from __future__ import annotations
import numpy as np
from geometry import Room, all_paths
from channel import received_power_dbm, wavelength, C, free_space_path_gain


# ---------------------------------------------------------------------------
# 1. 頻率掃描 + 線性回歸
# ---------------------------------------------------------------------------
def freq_sweep_regression(room, tx, rx, f_lo=100e6, f_hi=10e9, n_pts=60,
                          order=1, los_only=False, gamma=-1.0 + 0j):
    """
    在 [f_lo, f_hi] 對 log10(f) 密採樣接收功率,線性回歸求 dB/decade 斜率。

    回傳 dict(freqs, prx_dbm, slope_db_per_decade, residual_std_db, intercept)
    slope 為負 (功率隨頻率上升而下降);Friis 理論 LOS = -20 dB/decade。
    """
    freqs = np.logspace(np.log10(f_lo), np.log10(f_hi), n_pts)
    prx = np.array([
        received_power_dbm(_filter_los(all_paths(room, tx, rx, order), los_only),
                           f, gamma=gamma)
        for f in freqs
    ])
    logf = np.log10(freqs)
    slope, intercept = np.polyfit(logf, prx, 1)
    resid = prx - (slope * logf + intercept)
    return dict(freqs=freqs, prx_dbm=prx,
                slope_db_per_decade=float(slope),
                residual_std_db=float(resid.std()),
                intercept=float(intercept))


def _filter_los(paths, los_only):
    return [p for p in paths if p["type"] == "LOS"] if los_only else paths


# ---------------------------------------------------------------------------
# 2. 距離掃描 + 路徑損耗指數 n
# ---------------------------------------------------------------------------
def distance_sweep_regression(room, rx, freq_hz, d_lo=1.0, d_hi=40.0,
                              n_pts=60, order=1, los_only=False,
                              gamma=-1.0 + 0j, seed=0):
    """
    固定頻率,讓 T 沿一方向遠離 R,對 log10(d) 回歸求路徑損耗指數 n。

    模型: Prx(dB) = -10·n·log10(d) + const
    自由空間 n=2;室內 NLOS 多重反射 n≈3~5。
    回傳 dict(dists, prx_dbm, path_loss_exponent, residual_std_db)
    """
    # T 沿 R→某方向移動,距離從 d_lo 到 d_hi
    direction = np.array([1.0, 0.3])
    direction /= np.linalg.norm(direction)
    rx = np.asarray(rx, float)
    dists = np.linspace(d_lo, d_hi, n_pts)
    txs = [rx + d * direction for d in dists]
    # 夾進房間
    txs = [np.clip(t, 0.5, [room.width - 0.5, room.height - 0.5]) for t in txs]
    actual_d = np.array([np.linalg.norm(t - rx) for t in txs])

    prx = np.array([
        received_power_dbm(_filter_los(all_paths(room, t, rx, order), los_only),
                           freq_hz, gamma=gamma)
        for t in txs
    ])
    logd = np.log10(actual_d)
    slope, intercept = np.polyfit(logd, prx, 1)
    # Prx = -10·n·log10(d) + c  →  n = -slope/10
    n_exp = -slope / 10.0
    resid = prx - (slope * logd + intercept)
    return dict(dists=actual_d, prx_dbm=prx,
                path_loss_exponent=float(n_exp),
                residual_std_db=float(resid.std()))


# ---------------------------------------------------------------------------
# 3. 多組態 ensemble 統計
# ---------------------------------------------------------------------------
def ensemble_path_loss(room, freq_hz, n_configs=200, order=1,
                       gamma=-1.0 + 0j, seed=1):
    """
    隨機抽樣 n_configs 組 (T, R) 位置,對每組量 Prx 與 T-R 距離,
    彙整成 ensemble,回歸求平均路徑損耗指數 ± shadowing 標準差。

    這是修正「單一 T/R 會踩到特定衰落谷」的關鍵: 統計量才有代表性。
    回傳 dict(dists, prx_dbm, path_loss_exponent, shadowing_std_db, n_configs)
    """
    rng = np.random.default_rng(seed)
    dists, prx = [], []
    margin = 2.0
    for _ in range(n_configs):
        tx = rng.uniform([margin, margin],
                         [room.width - margin, room.height - margin])
        rx = rng.uniform([margin, margin],
                         [room.width - margin, room.height - margin])
        d = np.linalg.norm(tx - rx)
        if d < 2.0:                      # 跳過太近的組態
            continue
        p = received_power_dbm(all_paths(room, tx, rx, order), freq_hz,
                               gamma=gamma)
        dists.append(d); prx.append(p)
    dists = np.array(dists); prx = np.array(prx)
    logd = np.log10(dists)
    slope, intercept = np.polyfit(logd, prx, 1)
    n_exp = -slope / 10.0
    # shadowing = 對回歸線的殘差標準差 (log-normal shadowing σ)
    resid = prx - (slope * logd + intercept)
    return dict(dists=dists, prx_dbm=prx,
                path_loss_exponent=float(n_exp),
                shadowing_std_db=float(resid.std()),
                n_configs=len(dists))


# ---------------------------------------------------------------------------
# 4. Fresnel 反射係數 (取代理想 Γ=-1)
# ---------------------------------------------------------------------------
def fresnel_reflection(theta_i_rad, eps_r=4.44, polarization="TE"):
    """
    Fresnel 反射係數 (介電質牆面,無損近似)。

    eps_r: 相對介電常數 (混凝土≈4~6, 磚≈4, 乾牆≈2.5);預設 4.44 (混凝土)
    theta_i_rad: 入射角 (從牆面法線量)
    polarization: 'TE'(垂直/s偏振) 或 'TM'(平行/p偏振)

    回傳複數反射係數 Γ。理想導體極限 (eps_r→∞) 時 Γ→-1 (TE) 或 +1 (TM)。
    物理意義: 真實牆面 |Γ|<1,掠射 (θ→90°) 時 |Γ|→1。
    """
    ct = np.cos(theta_i_rad)
    st = np.sin(theta_i_rad)
    root = np.sqrt(eps_r - st ** 2 + 0j)
    if polarization.upper() == "TE":
        gamma = (ct - root) / (ct + root)
    else:  # TM
        gamma = (eps_r * ct - root) / (eps_r * ct + root)
    return complex(gamma)


def fresnel_vs_angle(eps_r=4.44, polarization="TE", n=50):
    """掃描入射角,回傳 (angles_deg, |Γ|) 供視覺化牆面反射的頻率/角度依賴。"""
    angles = np.linspace(0, 89.9, n)
    gammas = [abs(fresnel_reflection(np.deg2rad(a), eps_r, polarization))
              for a in angles]
    return angles, np.array(gammas)


def _incidence_angle(points, wall_name):
    """
    從路徑折線與牆名推算第一個反射點的入射角 (rad, 從牆面法線量)。
    牆名含 'left'/'right' → 垂直牆,法線沿 x;'top'/'bottom' → 水平牆,法線沿 y。
    """
    incoming = np.asarray(points[1], float) - np.asarray(points[0], float)
    incoming /= (np.linalg.norm(incoming) + 1e-30)
    if "left" in wall_name or "right" in wall_name:
        normal = np.array([1.0, 0.0])
    else:
        normal = np.array([0.0, 1.0])
    cos_i = abs(np.dot(incoming, normal))
    return float(np.arccos(np.clip(cos_i, 0.0, 1.0)))


def received_power_fresnel_dbm(paths, freq_hz, eps_r=4.44,
                               polarization="TE", tx_power_dbm=0.0):
    """
    用 Fresnel 反射係數 (每條反射路徑依其入射角) 計算接收功率。

    取代 received_power_dbm 的「所有反射共用常數 Γ=-1」近似。
    二次反射以兩次 Fresnel 相乘近似 (每面牆各一次,用同一入射角上界)。
    """
    lam = wavelength(freq_hz)
    k = 2.0 * np.pi / lam
    ar = 0 + 0j
    for p in paths:
        d = p["length"]
        amp = free_space_path_gain(d, freq_hz)
        if p["type"] == "LOS":
            coef = 1.0 + 0j
        else:
            theta = _incidence_angle(p["points"], p["name"])
            g = fresnel_reflection(theta, eps_r, polarization)
            # 二次反射 → 兩次反射,係數相乘 (近似用同一角)
            coef = g ** (p.get("order", 1))
        ar += coef * amp * np.exp(-1j * k * d)
    p_lin = max(abs(ar) ** 2, 1e-30)
    return tx_power_dbm + 10.0 * np.log10(p_lin)


def ensemble_path_loss_fresnel(room, freq_hz, n_configs=200, order=1,
                               eps_r=4.44, polarization="TE", seed=1):
    """與 ensemble_path_loss 相同,但用 Fresnel 反射係數。"""
    rng = np.random.default_rng(seed)
    dists, prx = [], []
    margin = 2.0
    for _ in range(n_configs):
        tx = rng.uniform([margin, margin],
                         [room.width - margin, room.height - margin])
        rx = rng.uniform([margin, margin],
                         [room.width - margin, room.height - margin])
        d = np.linalg.norm(tx - rx)
        if d < 2.0:
            continue
        p = received_power_fresnel_dbm(all_paths(room, tx, rx, order), freq_hz,
                                       eps_r=eps_r, polarization=polarization)
        dists.append(d); prx.append(p)
    dists = np.array(dists); prx = np.array(prx)
    logd = np.log10(dists)
    slope, intercept = np.polyfit(logd, prx, 1)
    n_exp = -slope / 10.0
    resid = prx - (slope * logd + intercept)
    return dict(dists=dists, prx_dbm=prx,
                path_loss_exponent=float(n_exp),
                shadowing_std_db=float(resid.std()),
                n_configs=len(dists))


if __name__ == "__main__":
    room = Room(50, 50)
    tx, rx = [4.0, 4.0], [45.0, 25.0]

    print("=" * 60)
    print("1. 頻率掃描回歸 (LOS only — 應逼近 Friis -20 dB/decade)")
    r = freq_sweep_regression(room, tx, rx, los_only=True)
    print(f"   slope = {r['slope_db_per_decade']:.2f} dB/decade  "
          f"(residual σ = {r['residual_std_db']:.2f} dB)")
    print("   全多路徑 (趨勢 + shadowing):")
    r2 = freq_sweep_regression(room, tx, rx, los_only=False)
    print(f"   slope = {r2['slope_db_per_decade']:.2f} dB/decade  "
          f"(residual σ = {r2['residual_std_db']:.2f} dB)")

    print("\n2. 距離掃描回歸 @ 1 GHz (路徑損耗指數 n)")
    rd = distance_sweep_regression(room, rx, 1e9, los_only=True)
    print(f"   LOS n = {rd['path_loss_exponent']:.2f}  "
          f"(Friis 理論 n=2, residual σ = {rd['residual_std_db']:.2f} dB)")
    rd2 = distance_sweep_regression(room, rx, 1e9, los_only=False)
    print(f"   多路徑 n = {rd2['path_loss_exponent']:.2f}  "
          f"(residual σ = {rd2['residual_std_db']:.2f} dB)")

    print("\n3. Ensemble 統計 @ 1 GHz (200 組隨機 T/R)")
    re = ensemble_path_loss(room, 1e9, n_configs=200)
    print(f"   n = {re['path_loss_exponent']:.2f}, "
          f"shadowing σ = {re['shadowing_std_db']:.2f} dB  "
          f"({re['n_configs']} 組有效)")

    print("\n4. Fresnel 反射係數 (混凝土 eps_r=4.44)")
    for ang in [0, 30, 45, 60, 85]:
        g = fresnel_reflection(np.deg2rad(ang), polarization="TE")
        print(f"   θ={ang:2d}°  |Γ_TE|={abs(g):.3f}  (理想導體 |Γ|=1)")

    print("\n5. 理想 Γ=-1 vs Fresnel 對 ensemble n 的影響 @ 1 GHz")
    ri = ensemble_path_loss(room, 1e9, n_configs=300)
    rf = ensemble_path_loss_fresnel(room, 1e9, n_configs=300)
    print(f"   理想 Γ=-1 : n = {ri['path_loss_exponent']:.2f}, "
          f"σ = {ri['shadowing_std_db']:.2f} dB")
    print(f"   Fresnel   : n = {rf['path_loss_exponent']:.2f}, "
          f"σ = {rf['shadowing_std_db']:.2f} dB")
    print("   → Fresnel 削弱反射能量,n 回升接近自由空間 (理想 Γ 系統性低估路徑損耗)")

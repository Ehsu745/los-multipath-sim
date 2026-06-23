"""
channel.py — 多路徑通道模型

復現報告中三個物理量:
  1. 自由空間路徑損耗 (Friis) — 接收功率隨距離/頻率衰減
  2. 各路徑複數相量 → 在接收端合成總場 Ar (六反射 + LOS)
  3. 接收功率隨 T 移動 + 不同頻率 (100MHz/1GHz/10GHz) 的衰減曲線

物理原理
--------
每條路徑長度 d 造成:
  - 振幅衰減 ∝ 1/d           (自由空間)
  - 相位旋轉 exp(-j·k·d)     k = 2π/λ = 2πf/c
反射另含反射係數 Γ (理想導體 Γ=-1,實務 |Γ|<1)。
總接收相量 Ar = Σ_i (A_i / d_i) · Γ_i · exp(-j·2π·d_i/λ)
"""

from __future__ import annotations
import numpy as np

C = 299_792_458.0  # 光速 m/s


def wavelength(freq_hz: float) -> float:
    return C / freq_hz


def free_space_path_gain(d: np.ndarray, freq_hz: float) -> np.ndarray:
    """Friis 自由空間振幅增益 (linear, 非 dB)。返回 λ/(4πd)。"""
    lam = wavelength(freq_hz)
    d = np.asarray(d, float)
    d = np.where(d < 1e-3, 1e-3, d)  # 避免除零
    return lam / (4.0 * np.pi * d)


def path_phasors(paths, freq_hz: float, gamma: complex = -1.0 + 0j):
    """
    把幾何路徑集合轉成接收端複數相量列。
    LOS 反射係數=1,反射路徑用 gamma (預設理想導體 -1)。
    回傳: (phasors[list[complex]], names[list[str]])
    """
    lam = wavelength(freq_hz)
    k = 2.0 * np.pi / lam
    phasors, names = [], []
    for p in paths:
        d = p["length"]
        amp = free_space_path_gain(d, freq_hz)
        refl_coef = 1.0 if p["type"] == "LOS" else gamma
        phasors.append(refl_coef * amp * np.exp(-1j * k * d))
        names.append(p["name"])
    return phasors, names


def combined_field(paths, freq_hz: float, gamma: complex = -1.0 + 0j) -> complex:
    """接收端總相量 Ar = Σ 各路徑相量。"""
    phasors, _ = path_phasors(paths, freq_hz, gamma)
    return complex(np.sum(phasors))


def received_power_dbm(paths, freq_hz, tx_power_dbm=0.0, gamma=-1.0 + 0j):
    """接收功率 (dBm)。|Ar|^2 正比於功率。"""
    ar = combined_field(paths, freq_hz, gamma)
    p_lin = np.abs(ar) ** 2
    p_lin = max(p_lin, 1e-30)
    return tx_power_dbm + 10.0 * np.log10(p_lin)


def power_vs_position(room, rx, tx_path, freqs, gamma=-1.0 + 0j):
    """
    報告右上角圖: T 沿軌跡等速移動時,各頻率下的接收功率曲線。

    tx_path: (N,2) T 的移動軌跡
    freqs:   list of Hz, e.g. [100e6, 1e9, 10e9]
    回傳: dict{freq: power_dbm_array}, distances_array
    """
    from geometry import all_paths
    tx_path = np.asarray(tx_path, float)
    rx = np.asarray(rx, float)
    dists = np.linalg.norm(tx_path - rx, axis=1)
    out = {}
    for f in freqs:
        pw = np.array([received_power_dbm(all_paths(room, t, rx), f, gamma=gamma)
                       for t in tx_path])
        out[f] = pw
    return out, dists


if __name__ == "__main__":
    from geometry import Room, all_paths
    room = Room(50, 50)
    tx, rx = np.array([4.0, 4.0]), np.array([45.0, 25.0])
    paths = all_paths(room, tx, rx)
    for f, label in [(100e6, "100MHz"), (1e9, "1GHz"), (10e9, "10GHz")]:
        ar = combined_field(paths, f)
        print(f"{label:7s}  Ar = {ar:.3e}  |Ar|={abs(ar):.3e}  "
              f"Prx={received_power_dbm(paths, f):.2f} dBm")

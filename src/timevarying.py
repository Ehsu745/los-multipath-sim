"""
timevarying.py — 時變通道、都卜勒與 OFDM 載波間干擾 (ICI)

延伸方向 3: 把「T 等速移動」這件事(報告本就有)轉成時變通道,
並分析它對 OFDM 系統造成的載波間干擾 (Inter-Carrier Interference)。

這個模組刻意設計成可與 SIMO-OFDM 專案 (ICI_THEORY.md) 互相引用:
同一套都卜勒→ICI 推導,在這裡用「室內多路徑幾何」當通道來源。

物理原理
--------
T 以速度 v 移動 → 每條路徑長度 d_i(t) 隨時間變化 → 相位 2π d_i(t)/λ
隨時間變化 → 等效都卜勒頻移 f_d,i = -(1/λ)·d(d_i)/dt = (v/λ)·cosθ_i。

OFDM 子載波間距 Δf。當通道在一個 OFDM 符元內變化(f_d 不可忽略於 Δf),
子載波正交性破壞,能量洩漏到鄰近子載波 → ICI。
ICI 功率隨正規化都卜勒 (f_d / Δf) 上升而增大。
"""

from __future__ import annotations
import numpy as np
from channel import C, wavelength, free_space_path_gain
from geometry import all_paths


def doppler_shifts(room, rx, tx, velocity_vec, freq_hz, order=1):
    """
    計算 T 以 velocity_vec 移動時,各路徑的都卜勒頻移 (Hz)。

    f_d,i = (v/λ)·cos(θ_i),θ_i 為速度向量與「T→該路徑首段方向」夾角。
    回傳 list of (name, f_d, gain_complex)。
    """
    tx = np.asarray(tx, float)
    rx = np.asarray(rx, float)
    v = np.asarray(velocity_vec, float)
    speed = np.linalg.norm(v)
    lam = wavelength(freq_hz)
    paths = all_paths(room, tx, rx, order=order)
    out = []
    for p in paths:
        # 路徑離開 T 的首段方向 (T → 第一個下一點)
        nxt = np.asarray(p["points"][1], float)
        d_dir = nxt - tx
        nrm = np.linalg.norm(d_dir)
        if nrm < 1e-9 or speed < 1e-12:
            fd = 0.0
        else:
            cos_t = np.dot(v, d_dir) / (speed * nrm)
            fd = (speed / lam) * cos_t
        amp = free_space_path_gain(p["length"], freq_hz)
        coef = (1.0 if p["type"] == "LOS" else -1.0) * amp
        out.append((p["name"], float(fd), complex(coef)))
    return out


def time_varying_taps(dopplers, t_array):
    """
    給定 (name, f_d, gain) 與時間軸,回傳每個時刻的合成複數通道 h(t)。
    h(t) = Σ_i gain_i · exp(j·2π·f_d,i·t)
    """
    h = np.zeros(len(t_array), dtype=complex)
    for _, fd, g in dopplers:
        h += g * np.exp(1j * 2 * np.pi * fd * t_array)
    return h


def ici_power_vs_doppler(subcarrier_spacing, fd_norm_range, n_sub=64):
    """
    OFDM ICI 功率 vs 正規化都卜勒 (f_d / Δf)。

    用經典近似: 在一個 OFDM 符元內通道線性變化時,ICI-to-Signal Ratio
    (ISR) ≈ (π·f_d·T_sym)^2 / 3 = (π·(f_d/Δf))^2 / 3,因 T_sym = 1/Δf。
    回傳 (fd_norm_array, isr_db_array)。
    """
    fd_norm = np.asarray(fd_norm_range, float)
    isr = (np.pi * fd_norm) ** 2 / 3.0
    isr_db = 10 * np.log10(np.clip(isr, 1e-12, None))
    return fd_norm, isr_db


def ici_matrix(dopplers, subcarrier_spacing, n_sub=64, t_sym=None):
    """
    建立 OFDM 通道在頻域的 ICI 洩漏矩陣 (近似)。

    對角線 = 各子載波增益,非對角 = 都卜勒造成的洩漏。
    回傳 |H[k,l]| 矩陣 (n_sub x n_sub),供視覺化「能量洩漏到鄰近子載波」。
    """
    if t_sym is None:
        t_sym = 1.0 / subcarrier_spacing
    fds = np.array([fd for _, fd, _ in dopplers])
    gains = np.array([g for _, _, g in dopplers])

    H = np.zeros((n_sub, n_sub), dtype=complex)
    k = np.arange(n_sub)
    for fd, g in zip(fds, gains):
        # 子載波 l 洩漏到 k 的係數 ~ sinc((k-l) + fd·t_sym)
        for l in range(n_sub):
            diff = (k - l) + fd * t_sym
            leak = np.sinc(diff)        # numpy sinc = sin(pi x)/(pi x)
            H[:, l] += g * leak
    return np.abs(H)


if __name__ == "__main__":
    from geometry import Room
    room = Room(50, 50)
    tx, rx = [4.0, 4.0], [45.0, 25.0]
    f0 = 2.4e9                      # 2.4 GHz (Wi-Fi 頻段,接 ESP32 場景)
    v = [30.0, 0.0]                # 30 m/s 水平移動

    dop = doppler_shifts(room, rx, tx, v, f0, order=2)
    print("各路徑都卜勒頻移:")
    for name, fd, g in dop:
        print(f"  {name:18s} f_d={fd:+8.2f} Hz  |gain|={abs(g):.3e}")

    dfreq = 15e3                    # OFDM 子載波間距 15 kHz (LTE-like)
    max_fd = max(abs(fd) for _, fd, _ in dop)
    print(f"\n最大都卜勒 = {max_fd:.1f} Hz, 正規化 f_d/Δf = {max_fd/dfreq:.4f}")
    fn, isr = ici_power_vs_doppler(dfreq, np.linspace(0.001, 0.3, 5))
    for a, b in zip(fn, isr):
        print(f"  f_d/Δf={a:.3f}  ISR={b:6.1f} dB")

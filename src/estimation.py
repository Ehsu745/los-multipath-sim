"""
estimation.py — 多路徑通道估測 (報告左下角)

報告描述: 「實際輸出訊號(藍) vs 系統響應估計輸出(紅),誤差值(黑),
Error% 低於 1e-3 時自動停止」。

這是典型的 FIR 通道係數估測。我們用已知輸入訊號 x[n] 通過未知多路徑
通道 h(由各路徑延遲/增益離散化而成)得到輸出 y[n],再用自適應演算法
(LMS) 從 (x, y) 反推 ĥ,觀察輸出誤差收斂到 < 1e-3。

物理對應
--------
多路徑 → 離散時間 FIR 濾波器: 每條路徑是一個 tap,
  tap delay  = round(d_i / c / Ts)   (取樣後的延遲)
  tap weight = (λ/4πd_i)·Γ_i·exp(-jk d_i)
通道估測就是要在不知道牆面/幾何的情況下,只憑收發訊號還原這組 tap。
"""

from __future__ import annotations
import numpy as np


def paths_to_taps(paths, freq_hz, fs, gamma=-1.0 + 0j, max_taps=64):
    """把連續路徑離散化成 FIR taps (複數)。"""
    from channel import C, wavelength, free_space_path_gain
    lam = wavelength(freq_hz)
    k = 2 * np.pi / lam
    Ts = 1.0 / fs
    h = np.zeros(max_taps, dtype=complex)
    t0 = min(p["length"] for p in paths) / C  # 以最短路徑為時間原點
    for p in paths:
        d = p["length"]
        delay = (d / C) - t0
        idx = int(round(delay / Ts))
        if 0 <= idx < max_taps:
            amp = free_space_path_gain(d, freq_hz)
            coef = (1.0 if p["type"] == "LOS" else gamma)
            h[idx] += coef * amp * np.exp(-1j * k * d)
    return h


def lms_estimate(x, y, n_taps, mu=0.5, tol=1e-3, max_iter=2000, seed=0):
    """
    NLMS (Normalized LMS) 自適應估測 FIR 通道。

    使用正規化步長,對訊號尺度不敏感 → 數值穩定,μ 取 0<μ<2 皆收斂。
    回傳 dict(h_est, error_history, iters, converged)
    error_history 為每次完整掃描(epoch)的正規化均方誤差 (對應報告 Error%)。
    """
    x = np.asarray(x, complex)
    y = np.asarray(y, complex)
    N = len(x)
    w = np.zeros(n_taps, dtype=complex)
    err_hist = []
    sig_pow = np.mean(np.abs(y) ** 2) + 1e-12
    eps = 1e-6

    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        sq_err = 0.0
        for n in range(n_taps, N):
            xvec = x[n:n - n_taps:-1]
            y_hat = np.dot(w.conj(), xvec)
            e = y[n] - y_hat
            norm = np.dot(xvec.conj(), xvec).real + eps
            w += (mu / norm) * e.conj() * xvec   # NLMS 更新
            sq_err += np.abs(e) ** 2
        nmse = sq_err / ((N - n_taps) * sig_pow)
        err_hist.append(nmse)
        if nmse < tol:
            converged = True
            break
    return dict(h_est=w, error_history=np.array(err_hist),
                iters=it, converged=converged)


def make_io_signals(h_true, n_samples=400, snr_db=30, seed=1):
    """產生通過 h_true 的輸入/輸出訊號對 (QPSK 輸入 + 加性雜訊)。"""
    rng = np.random.default_rng(seed)
    syms = rng.choice([1+1j, 1-1j, -1+1j, -1-1j], size=n_samples) / np.sqrt(2)
    y = np.convolve(syms, h_true)[:n_samples]
    sp = np.mean(np.abs(y) ** 2)
    npow = sp / (10 ** (snr_db / 10))
    noise = np.sqrt(npow / 2) * (rng.standard_normal(n_samples)
                                 + 1j * rng.standard_normal(n_samples))
    return syms, y + noise


if __name__ == "__main__":
    from geometry import Room, all_paths
    room = Room(50, 50)
    paths = all_paths(room, [4.0, 4.0], [45.0, 25.0])
    fs = 20e6
    h = paths_to_taps(paths, 1e9, fs, max_taps=16)
    h = h / np.max(np.abs(h))   # 正規化主徑為 1(估測只關心相對結構)
    x, y = make_io_signals(h, n_samples=300, snr_db=40)
    res = lms_estimate(x, y, n_taps=16, mu=0.7, tol=1e-3, max_iter=400)
    print(f"converged={res['converged']} iters={res['iters']} "
          f"final NMSE={res['error_history'][-1]:.2e}")
    print(f"true|h| peak idx = {np.argmax(np.abs(h))}, "
          f"est|h| peak idx = {np.argmax(np.abs(res['h_est']))}")

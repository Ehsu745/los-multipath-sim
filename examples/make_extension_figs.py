"""產生延伸功能展示圖: 二次反射路徑 + 時變通道/ICI 分析。

用法:
  python make_extension_figs.py          # 中文版 (預設)
  python make_extension_figs.py --lang en  # 英文版,輸出 *_en.png
"""
import sys
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.sans-serif"] = ["Noto Sans CJK TC", "Noto Sans CJK JP",
                                          "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from geometry import Room, all_paths
from timevarying import (doppler_shifts, time_varying_taps,
                         ici_power_vs_doppler, ici_matrix)

LANG = "en" if "--lang" in sys.argv and \
    sys.argv[sys.argv.index("--lang") + 1] == "en" else "zh"
SUF = "_en" if LANG == "en" else ""

T = {
    "zh": {
        "sup2": "延伸 ②: 鏡像法二次反射 — 逼近真實室內通道",
        "o1": "一次反射 (報告原版, 5 路徑)", "o2": "二次反射延伸 (13 路徑)",
        "sup3": "延伸 ③: 時變通道 → 都卜勒 → OFDM ICI (可接 SIMO-OFDM 專案)",
        "b1": "① 都卜勒功率譜 (2.4GHz, v=30m/s)",
        "b1x": "都卜勒頻移 f_d (Hz)", "b1y": "|增益|",
        "b2": "② 時變通道包絡 |h(t)| (深衰落)",
        "b2x": "時間 (ms)", "b2y": "正規化增益 (dB)",
        "b3": "③ OFDM ICI: ISR vs 正規化都卜勒",
        "b3leg": "本場景 f_d/Δf={v:.3f}",
        "b3x": "f_d / Δf", "b3y": "ICI-to-Signal Ratio (dB)",
        "b4": "④ ICI 洩漏矩陣 |H[k,l]| (dB)",
        "b4x": "發送子載波 l", "b4y": "接收子載波 k",
    },
    "en": {
        "sup2": "Extension ②: Second-order reflections (method of images) — toward a realistic indoor channel",
        "o1": "First-order (original, 5 paths)", "o2": "Second-order extension (13 paths)",
        "sup3": "Extension ③: Time-varying channel → Doppler → OFDM ICI (links to SIMO-OFDM project)",
        "b1": "① Doppler power spectrum (2.4GHz, v=30m/s)",
        "b1x": "Doppler shift f_d (Hz)", "b1y": "|gain|",
        "b2": "② Time-varying channel envelope |h(t)| (deep fading)",
        "b2x": "time (ms)", "b2y": "normalized gain (dB)",
        "b3": "③ OFDM ICI: ISR vs normalized Doppler",
        "b3leg": "this scenario f_d/Δf={v:.3f}",
        "b3x": "f_d / Δf", "b3y": "ICI-to-Signal Ratio (dB)",
        "b4": "④ ICI leakage matrix |H[k,l]| (dB)",
        "b4x": "Tx subcarrier l", "b4y": "Rx subcarrier k",
    },
}[LANG]

room = Room(50, 50)
tx, rx = np.array([4.0, 4.0]), np.array([45.0, 25.0])

# ---- 圖 A: 一次 vs 二次反射 ----
fig, axes = plt.subplots(1, 2, figsize=(13, 6))
for ax, order, title in [(axes[0], 1, T["o1"]), (axes[1], 2, T["o2"])]:
    ax.add_patch(plt.Rectangle((0, 0), 50, 50, fill=False, ec="k", lw=2))
    paths = all_paths(room, tx, rx, order=order)
    cmap = plt.cm.tab20(np.linspace(0, 1, len(paths)))
    for p, c in zip(paths, cmap):
        pts = np.array(p["points"])
        ls = "-" if p["type"] == "LOS" else "--"
        lw = 2.5 if p["type"] == "LOS" else 1.1
        ax.plot(pts[:, 0], pts[:, 1], ls, color=c, lw=lw)
        for q in pts[1:-1]:
            ax.plot(q[0], q[1], "o", color=c, ms=5)
    ax.plot(*tx, "s", color="blue", ms=14)
    ax.plot(*rx, "^", color="red", ms=14)
    ax.set_xlim(-3, 53); ax.set_ylim(-3, 53); ax.set_aspect("equal")
    ax.set_title(title, fontsize=12)
fig.suptitle(T["sup2"], fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(f"../assets/ext_second_order{SUF}.png", dpi=130, bbox_inches="tight")
print(f"saved ext_second_order{SUF}.png")

# ---- 圖 B: 時變通道 + ICI ----
fig, axes = plt.subplots(2, 2, figsize=(13, 9))
f0, v = 2.4e9, [30.0, 0.0]
dop = doppler_shifts(room, rx, tx, v, f0, order=2)

ax = axes[0, 0]
fds = [d[1] for d in dop]; gains = [abs(d[2]) for d in dop]
ax.stem(fds, gains, basefmt=" ")
ax.set_title(T["b1"]); ax.set_xlabel(T["b1x"]); ax.set_ylabel(T["b1y"])
ax.grid(alpha=0.3)

ax = axes[0, 1]
t = np.linspace(0, 0.02, 2000)
ht = time_varying_taps(dop, t)
ax.plot(t * 1e3, 20 * np.log10(np.abs(ht) / np.max(np.abs(ht))), "b-", lw=1)
ax.set_title(T["b2"]); ax.set_xlabel(T["b2x"]); ax.set_ylabel(T["b2y"])
ax.grid(alpha=0.3)

ax = axes[1, 0]
fn, isr = ici_power_vs_doppler(15e3, np.linspace(0.001, 0.4, 100))
ax.plot(fn, isr, "r-", lw=2)
max_fd = max(abs(d[1]) for d in dop)
ax.axvline(max_fd / 15e3, color="gray", ls=":",
           label=T["b3leg"].format(v=max_fd / 15e3))
ax.set_title(T["b3"]); ax.set_xlabel(T["b3x"]); ax.set_ylabel(T["b3y"])
ax.legend(fontsize=8); ax.grid(alpha=0.3)

ax = axes[1, 1]
H = ici_matrix(dop, 15e3, n_sub=32, t_sym=1 / 15e3 * 8)
im = ax.imshow(20 * np.log10(H / H.max() + 1e-6), cmap="viridis",
               vmin=-40, vmax=0, aspect="auto")
ax.set_title(T["b4"]); ax.set_xlabel(T["b4x"]); ax.set_ylabel(T["b4y"])
plt.colorbar(im, ax=ax, fraction=0.046)

fig.suptitle(T["sup3"], fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig(f"../assets/ext_ici{SUF}.png", dpi=130, bbox_inches="tight")
print(f"saved ext_ici{SUF}.png")

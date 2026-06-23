"""產生延伸功能展示圖: 二次反射路徑 + 時變通道/ICI 分析。"""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.sans-serif"] = ["Noto Sans CJK TC", "Noto Sans CJK JP",
                                          "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from geometry import Room, all_paths
from timevarying import (doppler_shifts, time_varying_taps,
                         ici_power_vs_doppler, ici_matrix)

room = Room(50, 50)
tx, rx = np.array([4.0, 4.0]), np.array([45.0, 25.0])

# ---- 圖 A: 一次 vs 二次反射 ----
fig, axes = plt.subplots(1, 2, figsize=(13, 6))
for ax, order, title in [(axes[0], 1, "一次反射 (報告原版, 5 路徑)"),
                         (axes[1], 2, "二次反射延伸 (13 路徑)")]:
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
    ax.set_title(f"{title}", fontsize=12)
fig.suptitle("延伸 ②: 鏡像法二次反射 — 逼近真實室內通道",
             fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig("../assets/ext_second_order.png", dpi=130, bbox_inches="tight")
print("saved ext_second_order.png")

# ---- 圖 B: 時變通道 + ICI ----
fig, axes = plt.subplots(2, 2, figsize=(13, 9))
f0, v = 2.4e9, [30.0, 0.0]
dop = doppler_shifts(room, rx, tx, v, f0, order=2)

# B1: 都卜勒譜
ax = axes[0, 0]
names = [d[0] for d in dop]; fds = [d[1] for d in dop]; gains = [abs(d[2]) for d in dop]
ax.stem(fds, gains, basefmt=" ")
ax.set_title("① 都卜勒功率譜 (2.4GHz, v=30m/s)")
ax.set_xlabel("都卜勒頻移 f_d (Hz)"); ax.set_ylabel("|增益|")
ax.grid(alpha=0.3)

# B2: 時變通道包絡 h(t)
ax = axes[0, 1]
t = np.linspace(0, 0.02, 2000)
ht = time_varying_taps(dop, t)
ax.plot(t * 1e3, 20 * np.log10(np.abs(ht) / np.max(np.abs(ht))), "b-", lw=1)
ax.set_title("② 時變通道包絡 |h(t)| (深衰落)")
ax.set_xlabel("時間 (ms)"); ax.set_ylabel("正規化增益 (dB)")
ax.grid(alpha=0.3)

# B3: ISR vs 正規化都卜勒
ax = axes[1, 0]
fn, isr = ici_power_vs_doppler(15e3, np.linspace(0.001, 0.4, 100))
ax.plot(fn, isr, "r-", lw=2)
max_fd = max(abs(d[1]) for d in dop)
ax.axvline(max_fd / 15e3, color="gray", ls=":", label=f"本場景 f_d/Δf={max_fd/15e3:.3f}")
ax.set_title("③ OFDM ICI: ISR vs 正規化都卜勒")
ax.set_xlabel("f_d / Δf"); ax.set_ylabel("ICI-to-Signal Ratio (dB)")
ax.legend(fontsize=8); ax.grid(alpha=0.3)

# B4: ICI 洩漏矩陣
ax = axes[1, 1]
H = ici_matrix(dop, 15e3, n_sub=32, t_sym=1 / 15e3 * 8)  # 放大都卜勒效果以利觀察
im = ax.imshow(20 * np.log10(H / H.max() + 1e-6), cmap="viridis",
               vmin=-40, vmax=0, aspect="auto")
ax.set_title("④ ICI 洩漏矩陣 |H[k,l]| (dB)")
ax.set_xlabel("發送子載波 l"); ax.set_ylabel("接收子載波 k")
plt.colorbar(im, ax=ax, fraction=0.046)

fig.suptitle("延伸 ③: 時變通道 → 都卜勒 → OFDM ICI (可接 SIMO-OFDM 專案)",
             fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig("../assets/ext_ici.png", dpi=130, bbox_inches="tight")
print("saved ext_ici.png")

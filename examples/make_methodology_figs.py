"""產生量測方法學修正的展示圖 (四象限)。

用法: python make_methodology_figs.py [--lang en]
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
from geometry import Room
from measurement import (freq_sweep_regression, ensemble_path_loss,
                         ensemble_path_loss_fresnel, fresnel_vs_angle)

LANG = "en" if "--lang" in sys.argv and \
    sys.argv[sys.argv.index("--lang") + 1] == "en" else "zh"
SUF = "_en" if LANG == "en" else ""

L = {
    "zh": {
        "sup": "LOS 量測方法學修正 — 從單點假象到統計量",
        "q1": "① 頻率掃描回歸 (取代兩點斜率)",
        "q1x": "頻率 (Hz, log)", "q1y": "接收功率 (dBm)",
        "q1los": "LOS: {s:.1f} dB/decade", "q1mp": "多路徑: {s:.1f} dB/dec (σ={r:.1f}dB)",
        "q2": "② Ensemble 路徑損耗 (理想 Γ=-1)",
        "q2x": "T-R 距離 (m, log)", "q2y": "接收功率 (dBm)",
        "q2leg": "n={n:.2f}, σ={s:.1f}dB (非物理 n<2)",
        "q3": "③ Ensemble 路徑損耗 (Fresnel 修正)",
        "q3leg": "n={n:.2f}, σ={s:.1f}dB (回到自由空間)",
        "q4": "④ Fresnel 反射係數 vs 入射角",
        "q4x": "入射角 (度)", "q4y": "|Γ| 反射係數",
        "q4ideal": "理想導體 |Γ|=1",
    },
    "en": {
        "sup": "LOS Measurement Methodology Correction — from single-point artifact to statistics",
        "q1": "① Frequency-sweep regression (vs two-point slope)",
        "q1x": "frequency (Hz, log)", "q1y": "received power (dBm)",
        "q1los": "LOS: {s:.1f} dB/decade", "q1mp": "multipath: {s:.1f} dB/dec (σ={r:.1f}dB)",
        "q2": "② Ensemble path loss (ideal Γ=-1)",
        "q2x": "T-R distance (m, log)", "q2y": "received power (dBm)",
        "q2leg": "n={n:.2f}, σ={s:.1f}dB (unphysical n<2)",
        "q3": "③ Ensemble path loss (Fresnel-corrected)",
        "q3leg": "n={n:.2f}, σ={s:.1f}dB (back to free space)",
        "q4": "④ Fresnel reflection coeff. vs incidence angle",
        "q4x": "incidence angle (deg)", "q4y": "|Γ| reflection coeff.",
        "q4ideal": "ideal conductor |Γ|=1",
    },
}[LANG]

room = Room(50, 50)
tx, rx = [4.0, 4.0], [45.0, 25.0]
fig, ax = plt.subplots(2, 2, figsize=(13, 9))

# ① 頻率掃描回歸
a = ax[0, 0]
rlos = freq_sweep_regression(room, tx, rx, los_only=True)
rmp = freq_sweep_regression(room, tx, rx, los_only=False)
a.semilogx(rlos["freqs"], rlos["prx_dbm"], "b-", lw=2,
           label=L["q1los"].format(s=rlos["slope_db_per_decade"]))
a.semilogx(rmp["freqs"], rmp["prx_dbm"], "r.", ms=4, alpha=0.6,
           label=L["q1mp"].format(s=rmp["slope_db_per_decade"],
                                  r=rmp["residual_std_db"]))
# 回歸線
lf = np.log10(rmp["freqs"])
a.semilogx(rmp["freqs"], rmp["slope_db_per_decade"] * lf + rmp["intercept"],
           "r--", lw=1)
a.set_title(L["q1"]); a.set_xlabel(L["q1x"]); a.set_ylabel(L["q1y"])
a.legend(fontsize=8); a.grid(alpha=0.3, which="both")

# ② ensemble 理想 Γ
a = ax[0, 1]
ri = ensemble_path_loss(room, 1e9, n_configs=400)
a.semilogx(ri["dists"], ri["prx_dbm"], "o", ms=3, alpha=0.35, color="#d62728")
logd = np.log10(ri["dists"])
sl = np.polyfit(logd, ri["prx_dbm"], 1)
a.semilogx(np.sort(ri["dists"]),
           np.polyval(sl, np.log10(np.sort(ri["dists"]))), "k-", lw=2,
           label=L["q2leg"].format(n=ri["path_loss_exponent"],
                                   s=ri["shadowing_std_db"]))
a.set_title(L["q2"]); a.set_xlabel(L["q2x"]); a.set_ylabel(L["q2y"])
a.legend(fontsize=8); a.grid(alpha=0.3, which="both")

# ③ ensemble Fresnel
a = ax[1, 0]
rf = ensemble_path_loss_fresnel(room, 1e9, n_configs=400)
a.semilogx(rf["dists"], rf["prx_dbm"], "o", ms=3, alpha=0.35, color="#2ca02c")
logd = np.log10(rf["dists"])
sl = np.polyfit(logd, rf["prx_dbm"], 1)
a.semilogx(np.sort(rf["dists"]),
           np.polyval(sl, np.log10(np.sort(rf["dists"]))), "k-", lw=2,
           label=L["q3leg"].format(n=rf["path_loss_exponent"],
                                   s=rf["shadowing_std_db"]))
a.set_title(L["q3"]); a.set_xlabel(L["q2x"]); a.set_ylabel(L["q2y"])
a.legend(fontsize=8); a.grid(alpha=0.3, which="both")

# ④ Fresnel vs 角度
a = ax[1, 1]
for eps, lbl, col in [(4.44, "concrete εr=4.44", "#1f77b4"),
                      (2.5, "drywall εr=2.5", "#ff7f0e")]:
    ang, g_te = fresnel_vs_angle(eps_r=eps, polarization="TE")
    a.plot(ang, g_te, "-", color=col, lw=1.8, label=f"TE, {lbl}")
_, g_tm = fresnel_vs_angle(eps_r=4.44, polarization="TM")
a.plot(ang, g_tm, "--", color="#1f77b4", lw=1.4, label="TM, concrete")
a.axhline(1.0, color="gray", ls=":", lw=1, label=L["q4ideal"])
a.set_title(L["q4"]); a.set_xlabel(L["q4x"]); a.set_ylabel(L["q4y"])
a.set_ylim(0, 1.05); a.legend(fontsize=7); a.grid(alpha=0.3)

fig.suptitle(L["sup"], fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.96])
out = os.path.join(os.path.dirname(__file__), "..", "assets",
                   f"methodology{SUF}.png")
fig.savefig(out, dpi=130, bbox_inches="tight")
print(f"saved methodology{SUF}.png")

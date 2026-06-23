"""
gui.py — 互動式四象限多路徑模擬 GUI

復現報告主畫面:可拖動發射端 T 與接收端 R,四張圖即時更新。
  左上: 反射路徑傳播圖 (T→四面牆反射→R)
  右上: 接收功率 vs T 位置 (三頻率)
  右下: 接收端複數空間的六反射 + LOS 相量合成 Ar
  左下: 多路徑通道估測誤差收斂 (NLMS, Error% < 1e-3 停止)

操作: 滑鼠拖動藍色 T 點或紅色 R 點,放開後重算。

CLI 友善設計: 也可 `python gui.py --no-gui` 直接輸出靜態快照 PNG,
適合無頭環境(如 Raspberry Pi / SSH / 備審截圖)。
"""

from __future__ import annotations
import sys
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

# 中文字型 (Noto CJK),避免方框亂碼
matplotlib.rcParams["font.sans-serif"] = ["Noto Sans CJK TC", "Noto Sans CJK JP",
                                          "Noto Sans CJK SC", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from geometry import Room, all_paths
from channel import (combined_field, path_phasors, power_vs_position,
                     received_power_dbm, wavelength)
from estimation import paths_to_taps, make_io_signals, lms_estimate

ROOM = Room(50, 50)
FREQS = [(100e6, "100 MHz"), (1e9, "1 GHz"), (10e9, "10 GHz")]
COLORS = {"LOS": "#1f77b4", "refl-left": "#ff7f0e", "refl-right": "#2ca02c",
          "refl-bottom": "#d62728", "refl-top": "#9467bd"}

# 圖內文字 (中英雙語)
LABELS = {
    "zh": {
        "suptitle": "室內多路徑傳播模擬 (LOS + 六反射)  —  拖動 T / R 即時更新",
        "q1": "① 反射路徑傳播圖", "tx": "T (發射)", "rx": "R (接收)",
        "q2": "② 接收功率 vs T 位置 (三頻率)", "dist": "T–R 距離 (m)",
        "prx": "接收功率 (dBm)",
        "q3": "③ 接收端複數相量合成 Ar",
        "q4_base": "④ 多路徑通道估測誤差 (NLMS)",
        "q4_conv": "④ 通道估測誤差 — {st} @ {it} epoch",
        "converged": "已收斂自動停止", "not_conv": "未收斂",
        "err": "Error% (NMSE)", "thresh": "停止門檻 1e-3",
        "iter": "迭代 (epoch)", "nmse": "正規化均方誤差",
    },
    "en": {
        "suptitle": "Indoor Multipath Propagation (LOS + reflections)  —  drag T / R to update",
        "q1": "① Reflection paths", "tx": "T (Tx)", "rx": "R (Rx)",
        "q2": "② Received power vs T position (3 freqs)", "dist": "T–R distance (m)",
        "prx": "Received power (dBm)",
        "q3": "③ Phasor combining at Rx → Ar",
        "q4_base": "④ Multipath channel estimation (NLMS)",
        "q4_conv": "④ Channel estimation error — {st} @ {it} epoch",
        "converged": "converged, auto-stopped", "not_conv": "not converged",
        "err": "Error% (NMSE)", "thresh": "stop threshold 1e-3",
        "iter": "iteration (epoch)", "nmse": "normalized MSE",
    },
}


class MultipathGUI:
    def __init__(self, tx=(4, 4), rx=(45, 25), lang="zh"):
        self.tx = np.array(tx, float)
        self.rx = np.array(rx, float)
        self.L = LABELS.get(lang, LABELS["zh"])
        self.drag = None
        self.fig, self.ax = plt.subplots(2, 2, figsize=(13, 9))
        self.fig.suptitle(self.L["suptitle"], fontsize=13, fontweight="bold")
        self.fig.canvas.mpl_connect("button_press_event", self.on_press)
        self.fig.canvas.mpl_connect("button_release_event", self.on_release)
        self.fig.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.redraw()

    # ---------- 四張圖 ----------
    def draw_paths(self, ax):
        ax.clear()
        ax.set_title(self.L["q1"])
        ax.set_xlim(-2, ROOM.width + 2); ax.set_ylim(-2, ROOM.height + 2)
        ax.set_aspect("equal")
        ax.add_patch(plt.Rectangle((0, 0), ROOM.width, ROOM.height,
                                   fill=False, ec="k", lw=2))
        paths = all_paths(ROOM, self.tx, self.rx)
        for p in paths:
            pts = np.array(p["points"])
            c = COLORS.get(p["name"], "gray")
            ls = "-" if p["type"] == "LOS" else "--"
            lw = 2.2 if p["type"] == "LOS" else 1.3
            ax.plot(pts[:, 0], pts[:, 1], ls, color=c, lw=lw,
                    label=p["name"], zorder=2)
            if p["reflection"] is not None:
                r = p["reflection"]
                ax.plot(r[0], r[1], "o", color=c, ms=6, zorder=3)
        ax.plot(*self.tx, "s", color="blue", ms=13, label=self.L["tx"], zorder=5)
        ax.plot(*self.rx, "^", color="red", ms=13, label=self.L["rx"], zorder=5)
        ax.legend(loc="upper right", fontsize=7, ncol=2)

    def draw_power(self, ax):
        ax.clear()
        ax.set_title(self.L["q2"])
        # T 沿一條斜線軌跡掃過房間
        N = 60
        path = np.linspace([2, 2], [ROOM.width - 2, ROOM.height - 2], N)
        pw, dists = power_vs_position(ROOM, self.rx, path, [f for f, _ in FREQS])
        order = np.argsort(dists)
        for (f, label) in FREQS:
            ax.plot(dists[order], pw[f][order], label=label, lw=1.6)
        # 目前 T 的位置標記
        cur_d = np.linalg.norm(self.tx - self.rx)
        ax.axvline(cur_d, color="gray", ls=":", lw=1)
        ax.set_xlabel(self.L["dist"]); ax.set_ylabel(self.L["prx"])
        ax.legend(fontsize=8); ax.grid(alpha=0.3)

    def draw_phasor(self, ax):
        ax.clear()
        ax.set_title(self.L["q3"])
        paths = all_paths(ROOM, self.tx, self.rx)
        phasors, names = path_phasors(paths, 1e9)
        # 逐路徑首尾相接畫向量合成,沿途記錄每個轉折點以正確定範圍
        origin = 0 + 0j
        verts = [0 + 0j]
        for ph, nm in zip(phasors, names):
            c = COLORS.get(nm, "gray")
            ax.annotate("", xy=(origin.real + ph.real, origin.imag + ph.imag),
                        xytext=(origin.real, origin.imag),
                        arrowprops=dict(arrowstyle="->", color=c, lw=1.5))
            origin += ph
            verts.append(origin)
        ax.plot([0, origin.real], [0, origin.imag], "k-", lw=2.5,
                label=f"Ar = {abs(origin):.2e}")
        ax.plot(origin.real, origin.imag, "k*", ms=14)
        # 範圍取所有轉折點的最大絕對座標,確保每個箭頭都框得進去
        lim = max(max(abs(v.real), abs(v.imag)) for v in verts) * 1.25 + 1e-12
        ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
        ax.set_aspect("equal"); ax.axhline(0, color="gray", lw=0.5)
        ax.axvline(0, color="gray", lw=0.5)
        ax.set_xlabel("Re"); ax.set_ylabel("Im")
        ax.legend(fontsize=8, loc="upper left")

    def draw_estimation(self, ax):
        ax.clear()
        ax.set_title(self.L["q4_base"])
        paths = all_paths(ROOM, self.tx, self.rx)
        h = paths_to_taps(paths, 1e9, fs=20e6, max_taps=16)
        peak = np.max(np.abs(h)) + 1e-30
        h = h / peak
        x, y = make_io_signals(h, n_samples=300, snr_db=40)
        res = lms_estimate(x, y, n_taps=16, mu=0.7, tol=1e-3, max_iter=200)
        err = res["error_history"]
        ax.semilogy(np.arange(1, len(err) + 1), err, "b-o", ms=3,
                    label=self.L["err"])
        ax.axhline(1e-3, color="red", ls="--", label=self.L["thresh"])
        status = self.L["converged"] if res["converged"] else self.L["not_conv"]
        ax.set_xlabel(self.L["iter"]); ax.set_ylabel(self.L["nmse"])
        ax.set_title(self.L["q4_conv"].format(st=status, it=res["iters"]))
        ax.legend(fontsize=8); ax.grid(alpha=0.3, which="both")

    def redraw(self):
        self.draw_paths(self.ax[0, 0])
        self.draw_power(self.ax[0, 1])
        self.draw_estimation(self.ax[1, 0])
        self.draw_phasor(self.ax[1, 1])
        self.fig.tight_layout(rect=[0, 0, 1, 0.96])
        self.fig.canvas.draw_idle()

    # ---------- 互動 ----------
    def on_press(self, event):
        if event.inaxes != self.ax[0, 0] or event.xdata is None:
            return
        p = np.array([event.xdata, event.ydata])
        if np.linalg.norm(p - self.tx) < 3:
            self.drag = "tx"
        elif np.linalg.norm(p - self.rx) < 3:
            self.drag = "rx"

    def on_motion(self, event):
        if self.drag is None or event.inaxes != self.ax[0, 0]:
            return
        if event.xdata is None:
            return
        p = np.clip([event.xdata, event.ydata], 0.5,
                    [ROOM.width - 0.5, ROOM.height - 0.5])
        setattr(self, self.drag, p)
        self.draw_paths(self.ax[0, 0])
        self.fig.canvas.draw_idle()

    def on_release(self, event):
        if self.drag is not None:
            self.drag = None
            self.redraw()

    def show(self):
        plt.show()

    def snapshot(self, path):
        self.redraw()
        self.fig.savefig(path, dpi=130, bbox_inches="tight")
        print(f"saved snapshot -> {path}")


def main():
    lang = "zh"
    if "--lang" in sys.argv:
        lang = sys.argv[sys.argv.index("--lang") + 1]
    if "--no-gui" in sys.argv:
        matplotlib.use("Agg")
        g = MultipathGUI(lang=lang)
        out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv \
            else "snapshot.png"
        g.snapshot(out)
    else:
        g = MultipathGUI(lang=lang)
        g.show()


if __name__ == "__main__":
    main()

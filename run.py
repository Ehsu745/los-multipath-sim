#!/usr/bin/env python3
"""
run.py — 統一 CLI 入口

範例:
  python run.py paths      --tx 4 4 --rx 45 25 --order 2
  python run.py power      --rx 45 25
  python run.py estimate
  python run.py packet
  python run.py doppler    --vx 30 --vy 0 --freq 2.4e9
  python run.py gui                       # 互動 GUI (需顯示環境)
  python run.py snapshot   --out main.png # 無頭環境輸出四象限快照
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def cmd_paths(a):
    from geometry import Room, all_paths
    room = Room(a.room, a.room)
    for p in all_paths(room, a.tx, a.rx, order=a.order):
        r = p["reflection"]
        rs = f"r1=({r[0]:.1f},{r[1]:.1f})" if r is not None else ""
        print(f"{p['name']:18s} ord={p['order']} len={p['length']:6.2f} m  {rs}")


def cmd_power(a):
    from geometry import Room, all_paths
    from channel import received_power_dbm
    room = Room(a.room, a.room)
    paths = all_paths(room, a.tx, a.rx, order=a.order)
    for f, lab in [(100e6, "100MHz"), (1e9, "1GHz"), (10e9, "10GHz")]:
        print(f"{lab:7s} Prx = {received_power_dbm(paths, f):.2f} dBm")


def cmd_estimate(a):
    from geometry import Room, all_paths
    from estimation import paths_to_taps, make_io_signals, lms_estimate
    import numpy as np
    room = Room(a.room, a.room)
    paths = all_paths(room, a.tx, a.rx, order=a.order)
    h = paths_to_taps(paths, 1e9, fs=20e6, max_taps=16)
    h = h / (np.max(np.abs(h)) + 1e-30)
    x, y = make_io_signals(h, n_samples=300, snr_db=a.snr)
    res = lms_estimate(x, y, n_taps=16, mu=0.7, tol=1e-3, max_iter=200)
    print(f"converged={res['converged']} epochs={res['iters']} "
          f"final NMSE={res['error_history'][-1]:.2e}")


def cmd_packet(a):
    from packet import simulate_link
    res = simulate_link(a.base, a.node1, a.node2,
                        init_energy_j=2.0, packet_rate_hz=100, n=2.0)
    print(f"d(base,node1)={res['d_base_node1']:.2f}  "
          f"d(node1,node2)={res['d_node1_node2']:.2f}")
    for nm in ("node1", "node2"):
        print(f"{nm}: {res[nm]['energy_per_pkt']*1e6:.1f} uJ/pkt  "
              f"life={res[nm]['lifetime_s']:.3f} s")


def cmd_doppler(a):
    from geometry import Room
    from timevarying import doppler_shifts, ici_power_vs_doppler
    import numpy as np
    room = Room(a.room, a.room)
    dop = doppler_shifts(room, a.rx, a.tx, [a.vx, a.vy], a.freq, order=a.order)
    for nm, fd, g in dop:
        print(f"{nm:18s} f_d={fd:+8.2f} Hz  |g|={abs(g):.3e}")
    mx = max(abs(fd) for _, fd, _ in dop)
    print(f"max |f_d|={mx:.1f} Hz, f_d/Δf(15kHz)={mx/15e3:.4f}")


def cmd_gui(a):
    sys.argv = ["gui.py"]
    import gui
    gui.main()


def cmd_snapshot(a):
    sys.argv = ["gui.py", "--no-gui", "--out", a.out]
    import gui
    gui.main()


def main():
    p = argparse.ArgumentParser(description="室內多路徑傳播模擬器")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--tx", type=float, nargs=2, default=[4, 4])
        sp.add_argument("--rx", type=float, nargs=2, default=[45, 25])
        sp.add_argument("--room", type=float, default=50)
        sp.add_argument("--order", type=int, default=1, choices=[1, 2])

    sp = sub.add_parser("paths"); add_common(sp); sp.set_defaults(fn=cmd_paths)
    sp = sub.add_parser("power"); add_common(sp); sp.set_defaults(fn=cmd_power)
    sp = sub.add_parser("estimate"); add_common(sp)
    sp.add_argument("--snr", type=float, default=40); sp.set_defaults(fn=cmd_estimate)
    sp = sub.add_parser("packet")
    sp.add_argument("--base", type=float, nargs=2, default=[200, 200])
    sp.add_argument("--node1", type=float, nargs=2, default=[191.18, 88.02])
    sp.add_argument("--node2", type=float, nargs=2, default=[300, 300])
    sp.set_defaults(fn=cmd_packet)
    sp = sub.add_parser("doppler"); add_common(sp)
    sp.add_argument("--vx", type=float, default=30); sp.add_argument("--vy", type=float, default=0)
    sp.add_argument("--freq", type=float, default=2.4e9); sp.set_defaults(fn=cmd_doppler)
    sp = sub.add_parser("gui"); sp.set_defaults(fn=cmd_gui)
    sp = sub.add_parser("snapshot")
    sp.add_argument("--out", default="snapshot.png"); sp.set_defaults(fn=cmd_snapshot)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

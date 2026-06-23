"""
packet.py — 無線通道封包傳輸與能量消耗 (報告封包傳輸視圖)

報告描述: base station + node1/node2,可拖動觀察傳輸距離、剩餘能量、
運行時間。這是無線感測網路 (WSN) 的經典能量模型。

能量模型 (first-order radio model, Heinzelman et al.):
  傳送 k bit 到距離 d:
      E_tx(k,d) = E_elec·k + ε_amp·k·d^n
  接收 k bit:
      E_rx(k)   = E_elec·k
其中 n 為路徑損耗指數 (自由空間 n=2,多重反射室內 n≈3~4)。
"""

from __future__ import annotations
import numpy as np

# 典型參數 (nJ 尺度)
E_ELEC = 50e-9       # J/bit, 收發電路能耗
EPS_AMP = 100e-12    # J/bit/m^2, 放大器能耗 (自由空間)
PACKET_BITS = 4000   # 每封包 bit 數


def tx_energy(k_bits, dist, n=2.0, eps_amp=EPS_AMP):
    return E_ELEC * k_bits + eps_amp * k_bits * dist ** n


def rx_energy(k_bits):
    return E_ELEC * k_bits


def node_lifetime(initial_energy_j, energy_per_packet_j, packet_rate_hz):
    """估剩餘運行時間 (秒)。"""
    if energy_per_packet_j <= 0 or packet_rate_hz <= 0:
        return float("inf")
    n_packets = initial_energy_j / energy_per_packet_j
    return n_packets / packet_rate_hz


def simulate_link(base, node1, node2, init_energy_j=0.5,
                  packet_rate_hz=1000, n=2.0):
    """
    模擬 base→node1→node2 多跳鏈路的能量狀態。
    回傳每個節點的距離、每封包能耗、剩餘能量比例、運行時間。
    """
    base = np.asarray(base, float)
    node1 = np.asarray(node1, float)
    node2 = np.asarray(node2, float)

    d_b1 = np.linalg.norm(node1 - base)
    d_12 = np.linalg.norm(node2 - node1)
    d_b2 = np.linalg.norm(node2 - base)

    # node1: 接收 base 的封包 + 轉送給 node2
    e1 = rx_energy(PACKET_BITS) + tx_energy(PACKET_BITS, d_12, n)
    # node2: 接收 node1 + (直接回報 base)
    e2 = rx_energy(PACKET_BITS) + tx_energy(PACKET_BITS, d_b2, n)

    return dict(
        d_base_node1=d_b1, d_node1_node2=d_12, d_base_node2=d_b2,
        node1=dict(energy_per_pkt=e1,
                   lifetime_s=node_lifetime(init_energy_j, e1, packet_rate_hz)),
        node2=dict(energy_per_pkt=e2,
                   lifetime_s=node_lifetime(init_energy_j, e2, packet_rate_hz)),
    )


if __name__ == "__main__":
    # 對齊報告範例: base=(200,200), node1≈(191,88), node2=(300,300)
    # 報告中座標為抽象單位,運行時間約 0.9s;調整放大器係數使量級吻合
    res = simulate_link((200, 200), (191.18, 88.02), (300, 300),
                        init_energy_j=2.0, packet_rate_hz=100, n=2.0)
    print(f"d(base,node1) = {res['d_base_node1']:.2f} m")
    print(f"d(node1,node2)= {res['d_node1_node2']:.2f} m")
    print(f"node1: {res['node1']['energy_per_pkt']*1e6:.2f} uJ/pkt, "
          f"life={res['node1']['lifetime_s']:.3f} s")
    print(f"node2: {res['node2']['energy_per_pkt']*1e6:.2f} uJ/pkt, "
          f"life={res['node2']['lifetime_s']:.3f} s")

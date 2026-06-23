# 室內多路徑傳播理論 (THEORY)

本文件說明模擬器背後的物理與訊號處理模型。所有公式皆對應 `src/` 中的實作。

> 出處說明:本專案為《無線通訊電腦模擬實習》期末專題之**獨立重新實作**。
> 原專題由小組共同完成(原始 MATLAB 程式碼著作權屬小組,本人非第一作者),
> 本 repository 不含任何原始程式碼,而是依據公開的報告文件與簡報所描述之
> 物理模型,以 Python 從零重寫,並加入二次反射、時變通道/ICI 等延伸。

---

## 1. 鏡像法 (Method of Images) — `geometry.py`

理想平面反射牆的反射訊號,等效於從**發射端對該牆的鏡像**直線傳來。

設發射端 T、接收端 R,牆面為 `axis = value` 的直線。T 對牆的鏡像:

```
T'[axis] = 2·value − T[axis]    (另一軸不變)
```

反射點為 T'–R 連線與牆面的交點。以參數式 `P = T' + s·(R − T')` 求
`P[axis] = value` 解出 `s`,需 `0 < s < 1`(物理上反射點在兩端之間),
且反射點落在牆段範圍內。一次反射總路徑長等於鏡像距離 `|R − T'|`。

**二次反射**以遞迴鏡像實現:T 先對牆₁鏡像得 T′,再對牆₂鏡像得 T″,
路徑長 `|R − T″|`,兩個反射點由 R 往回逐段求交點並驗證。

矩形房間:一次反射最多 4 條(+LOS = 5);二次反射再加最多 8 條(共 13)。

---

## 2. 自由空間路徑損耗 (Friis) — `channel.py`

第 i 條路徑長度 `dᵢ` 造成的振幅增益(線性):

```
Gᵢ = λ / (4π·dᵢ)        λ = c / f
```

其中 c 為光速,f 為載波頻率。功率正比於 `G²`,因此

```
Prx(dB) ∝ 20·log₁₀(λ) − 20·log₁₀(4π·d) = −20·log₁₀(f) − 20·log₁₀(d) + const
```

→ **頻率每升 10 倍,功率降約 20 dB**;這就是模擬器圖②中
100 MHz / 1 GHz / 10 GHz 三條曲線分層的原因。

---

## 3. 複數相量合成 — `channel.py`

每條路徑在接收端的複數場:

```
aᵢ = Γᵢ · Gᵢ · exp(−j·k·dᵢ)        k = 2π/λ
```

LOS 的反射係數 Γ = 1;反射路徑 Γ = −|Γ|(理想導體 −1,可調)。
接收端總場為所有路徑相量和:

```
Ar = Σᵢ aᵢ
```

不同路徑因長度不同帶有不同相位,向量相加可能**建設性或破壞性干涉**——
這是多路徑衰落 (multipath fading) 的根源,對應模擬器圖③的向量合成。

---

## 4. 多路徑通道估測 (NLMS) — `estimation.py`

多路徑通道離散化為 FIR 濾波器,每條路徑是一個 tap:

```
延遲 index = round((dᵢ/c − t₀) / Ts)      Ts = 1/fs
tap 權重   = Γᵢ · Gᵢ · exp(−j·k·dᵢ)
```

已知輸入 x[n](QPSK)通過通道得輸出 y[n],用 **Normalized LMS** 反推 ĥ:

```
e[n]    = y[n] − ŵᴴ·x[n:n−L]
ŵ      ← ŵ + (μ / (‖x‖² + ε)) · e*[n] · x[n:n−L]
```

NLMS 的正規化步長對訊號尺度不敏感,`0 < μ < 2` 皆穩定收斂。
每個 epoch 計算正規化均方誤差 (NMSE);當 **NMSE < 1e-3 時自動停止**
(對應報告「Error% 低於 1e-3 自動停止」)。

---

## 5. 封包傳輸能量模型 (WSN) — `packet.py`

一階無線電能量模型 (Heinzelman et al.):

```
傳送 k bit 到距離 d:  E_tx = E_elec·k + ε_amp·k·dⁿ
接收 k bit:           E_rx = E_elec·k
```

n 為路徑損耗指數(自由空間 n=2,室內多重反射 n≈3~4)。節點剩餘運行
時間 = 初始能量 / 每封包能耗 / 封包率。距離越遠 → `dⁿ` 主導 → 能耗
急遽上升 → 壽命縮短,對應報告中 node1(需轉送、距離遠)較早耗盡。

---

## 6. 延伸:時變通道、都卜勒與 OFDM ICI — `timevarying.py`

當 T 以速度 **v** 移動,路徑長度隨時間變化,產生都卜勒頻移:

```
f_d,i = (v / λ)·cos(θᵢ)
```

θᵢ 為速度向量與路徑離開方向的夾角 → 朝向接收端為正、遠離為負。
時變通道 `h(t) = Σᵢ gᵢ·exp(j·2π·f_d,i·t)`,其包絡呈現深衰落。

**OFDM 載波間干擾 (ICI):** 子載波間距 Δf,符元長 `T_sym = 1/Δf`。
當通道在一個符元內變化(f_d 相對 Δf 不可忽略),子載波正交性破壞,
能量洩漏到鄰近子載波。線性近似的 ICI-to-Signal Ratio:

```
ISR ≈ (π · f_d / Δf)² / 3
```

→ 正規化都卜勒 `f_d/Δf` 越大,ICI 越嚴重。此模型與 SIMO-OFDM 專案的
`ICI_THEORY.md` 同源,可交叉引用。

---

## 參考

- T. S. Rappaport, *Wireless Communications: Principles and Practice*, 2/e
- W. C. Heinzelman et al., "Energy-Efficient Communication Protocol for
  Wireless Microsensor Networks," HICSS 2000
- A. Goldsmith, *Wireless Communications*, Cambridge University Press

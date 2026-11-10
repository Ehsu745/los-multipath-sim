# CLAUDE.md — los-multipath-sim

室內多路徑傳播模擬器。2D 鏡像法 ray tracing、Friis 路徑損耗、相量合成、
NLMS 通道估測、WSN 封包能量、Doppler/OFDM-ICI、量測方法學。
Python CLI + matplotlib GUI + 純 JS 瀏覽器版。

## 這個 repo 的脈絡在哪

進度、模型真相、各模組筆記都在 **worklog vault**（`../worklog`），不要在這裡
重寫，要讀它：

- 目前進度 / 待辦：`../worklog/LLM/DEV_STATUS.md`（Today / Ongoing）
- 模型與介面真相（source of truth）：`../worklog/Spec/`（Physics Model、CLI、Screens）
- 各模組實作筆記：`../worklog/Impl/`（Channel、Estimation、Geometry、Measurement、
  Packet、Time-Varying、GUI and Web）
- 參考來源：`../worklog/Reference/Sources.md`
- **作者偏好與專案內部定位**：`../worklog/LLM/PRIVATE_CONTEXT.md`（私有，先讀它）

vault 的命令（`/cmd-sync`、`/cmd-journal`、`/cmd-notes-sync`、`/git-workflow` 等）
已連結到 `.claude/skills/`，可直接使用。**衝突時的信任順序**：程式碼 > 今日對話與
DEV_STATUS > Spec 筆記 > 其他筆記。筆記與程式碼牴觸時，以程式碼為準並提醒跑
`/cmd-notes-sync`。

## 建置與驗證

```bash
pip install -r requirements.txt          # numpy, matplotlib
python run.py <cmd>                       # 驗證數值(paths/power/estimate/packet/doppler/measure)
python src/<module>.py                    # 各模組自測
python run.py snapshot                    # 無頭快照
```

無單元測試；以 `run.py` 的數值輸出和模組自測驗證。

## 模組結構（src/）

geometry（鏡像法幾何）· channel（Friis + 相量）· estimation（NLMS）·
packet（WSN 能量）· timevarying（Doppler/ICI）· measurement（量測方法學：
ensemble 回歸 + Fresnel）· gui（matplotlib 四象限）。
文件：`docs/THEORY.md`（物理推導）、`docs/METHODOLOGY.md`（量測修正）。

## ⚠️ 接手前必讀（容易踩雷）

1. **main 分支有保護**：不能直接 `git push` 到 main。一律開 branch → PR →
   核准後合併。禁 force push。遵循 `/git-workflow` skill。
2. **誠信邊界（重要）**：本 repo 是從原始 MATLAB 小組專題的**物理模型概念**
   獨立 Python 重寫，**不含任何原始 MATLAB 程式碼**。維護時絕不把原始碼或直接
   移植的邏輯放進來。README 的原創性聲明要維持一致。細節見 PRIVATE_CONTEXT。
3. **已是合作專案**：與原專題第一作者共同維護（collaborator）。README/履歷的
   措辭定位見 PRIVATE_CONTEXT，改動相關描述前先確認。

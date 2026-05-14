> 本文件记录开发人员（我）的开发构想。

---

## 2026-05-13 — 第二阶段收尾宣告完成

- **结论**：第二阶段收尾（见 **`第二阶段收尾计划.md`**）在文档层面已收口；主排期曾切换至 **`第三阶段开发计划.md`**（Electron 高可用 GUI）；第三阶段已按 **P0** 结案，**原 P1** 迁至 **`第四阶段开发计划.md`**；**A6 设定导入**等仍建议作为后续里程碑单列。
- **索引**：`DECISIONS.md` §1 文档表已更新第三/四阶段条目；`下一阶段开发计划.md` 标注为历史广义队列。

---

## 2026-05-13 — 第三阶段 M-A（步 1～2）：Electron 空壳 + 开发态加载 GUI

- **实现**：新增 **`src/electron/`**（独立 `package.json`、`tsconfig.main` / `tsconfig.preload`、Main `loadURL` 默认 `http://127.0.0.1:5173/`；`contextIsolation: true`、`nodeIntegration: false`、占位 `preload`；Vite 未监听时 **stderr + 系统警告框**）。  
- **文档**：`README.md` 前后端联调小节；**`GUI开发文档.md`** §1 表与修订记录。  
- **后续合并点**：按计划 §7.2 进入 **M-B（步 3～5）**：Main 拉起 `run_backend_stub`、健康门、退出清理。

---

## 2026-05-14 — 第三阶段 P0 步 8～11（安全窄 IPC、GUI 基址与 SSE、便携包、Playwright）

- **实现**：Electron `ipcMain` + `preload.getApiBase`（打包态绝对 API；开发态空串保留 Vite 代理）；生产包 DevTools 门控；`loadFile` 加载 `extraResources/gui`；GUI `apiBase` / `apiUrl`、SSE 建连退避与读流错误、`onBackendStatus` 顶栏提示；`electron-builder` portable；`src/gui` Playwright 烟测（双 `webServer` 拉后端 + Vite）。  
- **文档**：`README.md`、`ARCHITECTURE.md` §4 启动拓扑；`已完成/第三阶段开发计划.md` 修订记录。

---

## 2026-05-14 — 第三阶段结案归档 + 第四阶段主排期初稿

- **结论**：第三阶段按 **P0 已全部交付** 收口；计划正文迁入 **`已完成/第三阶段开发计划.md`**；根目录 **`第三阶段开发计划.md`** 改为重定向 stub。**原 §3 / §7.3 P1**（A7、MCP 加固、可选契约工程）整体迁入 **`第四阶段开发计划.md`**（初稿），不作为第三阶段未完成债务。  
- **文档**：`DECISIONS.md`、`重要子系统开发文档/GUI开发文档.md`、`重要子系统开发文档/API终极文档.md`、`README.md`、`已完成/README.md`、`已完成/第二阶段收尾计划.md`、`src/electron/package.json` 描述字段已跟进索引。

---

## 2026-05-14 — 第四阶段范围定案（§2 冻结 + 产品化 / Obs 指导文）

- **结论**：**`第四阶段开发计划.md`** 更新为**已定案**：主线顺序 **A7 → MCP → Obs**；契约 OpenAPI、A6、Electron 安装/签名/更新/真壳 E2E **顺延下阶段**。新增 **`重要子系统开发文档/产品化文档.md`**、**`Obs开发文档.md`**；**`DECISIONS.md`**、**`重要子系统开发文档/README.md`**、**`API终极文档.md`** §4.3、**`GUI开发文档.md`** 索引已跟进。  
- **§8**：初稿列为「性能与成本」讨论项；随后在 **同日下一则 DEVLOG** 定案为 **默认 A**，见该则。

---

## 2026-05-14 — 「性能」默认语义与 Harness 专文

- **结论**：**「性能」默认 = A（软件自身性能）**，排第四阶段 **§2 优先级 4、阶段后期**；**B** 由 **`重要子系统开发文档/Harness Engineering文档.md`** 承接，与主线解耦。  
- **文档**：**`第四阶段开发计划.md`** §8 已定案；新增 **`Harness Engineering文档.md`**；**`DECISIONS.md`**、**`重要子系统开发文档/README.md`**、**`Obs开发文档.md`** 修订互链。

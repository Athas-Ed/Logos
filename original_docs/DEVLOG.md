> 本文件记录开发人员（我）的开发构想。

---

## 2026-05-21 — F6 Q5/Q7 定案

- **Q5**：省略 `skill_id` **维持回退** `chat_inspire`（F6 不改 400）。  
- **Q7**：F6 竖切片 **`default_import_v0`**；定稿后 **`your_profile_v1`**（换 profile 资源即可）。

---

## 2026-05-21 — F6 Q5/Q7 讨论收口

- **Q5**：三态表（合法执行 / 未知 400 / **省略→回退 chat_inspire**）；F6 仍默认不改 400，可选 developer 与 product 分轨。  
- **Q7**：F6 做 **平台轨**（Runner、SSE、profile 机制）；具体 schema/render/pipeline yaml **随产品模板迭代**。  
- **确认**：Q1 进程内 Runner；Q3 SSE 扩展；Q6 M-UI 含 inspire；Q8 共用 LLM。

---

## 2026-05-21 — F6 §4 技术 FAQ 与产品确认

- **确认**：Q2 含 **晋升 KSFS**；Q3 **pipeline 分步 SSE**；Q4 **只读重叠 warnings**；Q8 **共用全局 LLM**。  
- **澄清**：Q1 `pipeline` 为范式，执行走 **进程内 PipelineRunner**（非设定导入 MCP 包）；Q3 为「共享 SSE 主干 + 范式扩展事件」。  
- **文档**：**`第六阶段开发计划.md` §4.1～4.2**；**`Skill形态与Prompt工程.md`** 增 `pipeline_profile`。

---

## 2026-05-21 — 第六阶段定案（A+B+E）

- **主轴**：**A** CD-2～CD-3（`PipelineRunner`、`import_setting` 后端）；**B** G5 `/cache` + 启动提醒 + M-UI；**E** `import_setting` GUI 竖切片。
- **文档**：**`第六阶段开发计划.md`** 重写为 F6-00～F6-09；§4 列 **Q1～Q8** 待技术确认（默认假设已写）。
- **不做 F6**：产品化 C、OpenAPI D、`ksfs_edit`、`paradigm_auto`、Plan Phase B。

---

## 2026-05-21 — 第五阶段归档 + 第六阶段 backlog 草案

- **归档**：**`第五阶段开发计划.md`** → **`已完成/第五阶段开发计划.md`**；根目录 stub；**`已完成/README.md`** 已索引。
- **第六阶段**：新增 **`第六阶段开发计划.md`**（未立项）；**§2** 汇总 F4/F5 顺延、CD-2～4、产品化、业务 Skill 等待办，供排期讨论。
- **索引**：**`DECISIONS.md`** §1 表、§14.2 修订为 F5 已落地项。

---

## 2026-05-21 — 第五阶段结案（F5-00～F5-10）

- **结论**：第五阶段 **产品主轴** 已落地 — 冷启动 **技能面板**（`/`）、产品 Skill manifest + `skill_id` 契约、PR 四范式分轨（`dialogue` / `react` / `plan` Phase A / `pipeline` 桩）、竖切片 **`lint_zh`**、**`chat_inspire`**、**`retrieve_qa`**（scoped react）、**`outline_plan`**（plan）。
- **验收（自动）**：`python -m pytest -q` → **146 passed, 1 skipped**；`src/gui` → **`npm run build`**、**`npm run test`**（7）、**`npm run test:e2e`**（6，含面板四卡 + lint 竖切片 + inspire 多轮）。
- **文档**：**`第五阶段开发计划.md`** §0.5 / F5-10 全勾选；**`PR开发文档.md`** §4 PR 轨结案；**`API-V0.2.md`** §3.1 对齐 `plan` 语义。
- **顺延**：G5 `/cache` 全功能、M-UI 定稿、设定导入 **pipeline** 全链、Electron 安装包/签名/真壳 E2E 全覆盖 → **F5 后**（见计划 §2.2、§6）。
- **契约**：第五阶段 HTTP 字段以 **`API-V0.2.md`** 为准；后续改 `api_v1` 须同 PR 更新契约测 + 提交说明 `契约：` 行。

---

## 2026-05-16 — 第五阶段产品主轴与地基评估入 DECISIONS

- **背景**：GUI 默认「万能 Chat + 全工具」与作家模式「任务/Skill 驱动」主轴错位；多标签/SSE/Prompt 回显等暴露**上层运行时**问题，下层 `pytest`（约 110 项）仍稳。
- **文档**：新增 **`重要子系统开发文档/任务与Skill驱动GUI定案.md`**、**`Skill形态与Prompt工程.md`**、**`第五阶段开发计划.md`**（T0～T3）；**`DECISIONS.md` §14** 与 **§14.4**（地基评估、风险、假设、PR 自检三条）。
- **结论（写入 §14.4）**：**不必推倒 `src/logos` 分层**；须补 **`skill_id` + scoped tools + 技能面板** 竖切片；G5/M-UI 冻结至 T1 后；第四阶段 G1～G4 **保留**为任务运行时。
- **下一步**：T1 — P2 单 Skill（如语病检查）端到端 + 可选契约 `skill_id`。

---

## 2026-05-16 — PR 范式定案：dialogue / react / plan / pipeline

- **动机**：部分 Skill 以对话为主，不应强制 ReAct JSON-only；PR 原构想为智能选范式，第五阶段改为 **Skill manifest 预绑定范式**，PR 确认并调度（远期 `paradigm_auto` 推断）。
- **文档**：**`重要子系统开发文档/范式路由与PR定案.md`**；**`Skill形态与Prompt工程.md` §4** 二维矩阵；`pr.py` 类型扩展为四范式，实现仍返回 `react`。
- **Prompt**：L2 按 `paradigms/*` + `persistence/*` + `skills/<id>/*` 拼装（范式文档 §6）。

---

## 2026-05-16 — 第五阶段计划重写 + PR 开发文档

- **废止**：第五阶段初版仅 T0～T3 简表。  
- **新排期**：**`第五阶段开发计划.md`** — **F5-00～F5-10**（Skill 注册表、契约 `skill_id`、技能面板、Task 向导、PR 轨、lint_zh/chat_inspire、阶段总验收）。  
- **PR 实施**：**`重要子系统开发文档/PR开发文档.md`** — PR-0～PR-6、§4 PR 轨最终验收、§1 最终效果。  
- **互链**：GUI 文档 §11.4、任务定案 §9、范式定案 §8、DECISIONS §14。

---

## 2026-05-14 — 第四阶段计划归档

- **结论**：**`第四阶段开发计划.md`** 已定案正文 **`git mv`** 至 **`original_docs/已完成/第四阶段开发计划.md`**；根目录 **`original_docs/第四阶段开发计划.md`** 改为**重定向 stub**。**`README.md`**、**`DECISIONS.md`**、**`第三阶段开发计划.md`**、**`已完成/README.md`** 及 **`重要子系统开发文档/`** 内互链已批量改为 **`已完成/第四阶段开发计划.md`**（或相对等价路径）。**S15**：**`README.md`** Stream 0 节已含 profiling 一行。
- **现行排期**：**`下一阶段开发计划.md`**（广义队列）；**第五阶段**主排期未定稿前不强制新文件名。

---

## 2026-05-14 — 第四阶段软件性能（§9.3）：S12～S14

- **S12 基线（场景 / 工具 / 数据）**
  - **场景 A（契约回归 + 冷启动）**：`python -m cProfile -s cumulative -m pytest tests/test_stream5_api.py -q` — 总时长约 **3s 级**（本机），**cumtime** 主要由 **pytest 收集 / importlib / 线程 join** 占据；用于「全量 API 测」冷启动对照，**不宜**单独解读为路由热点。
  - **场景 B（单测 SSE 一轮）**：`python -m cProfile -s cumulative -m pytest tests/test_stream5_api.py::test_api_v1_chat_sse_delta_and_done -q` — 约 **1.7s**，同上仍以 **import + pytest 壳** 为主。
  - **场景 C（热路径压测 · 推荐）**：仓库根 **`scripts/perf_baseline_bootstrap.py`**，循环 **`GET /api/v1/bootstrap`**（默认 200 次，可传参加大）；配合 `python -m cProfile -s tottime scripts/perf_baseline_bootstrap.py 1200`。本机 **1200 次** 总约 **4.5s**；**tottime** 前列为 **`httpx`/Starlette `TestClient`**、**`asyncio` I/O**、**依赖注入 `solve_dependencies`** 等框架层，**logos 路由体占比相对小**——结论：**后续 A 类优化**应优先用 **真实 ASGI 服务器 + wrk/hey** 或 **生产打包 Electron** 再压，本脚本用于**回归对比**与**低成本采样**。
  - **前端基线**：`cd src/gui && npm run build` — 本机一次约 **0.7s 级**（Vite 报告），**gzip 后 JS ~54KB**（仅作本地对比锚点）。
  - **原始数据**：cProfile 文本未入库；可自生成 `python -m cProfile -o prof.out scripts/perf_baseline_bootstrap.py 2000` 后用 **`pstats`** / **`snakeviz`** 解析 `prof.out`（路径自定，默认不入库）。
- **S13（Top1 可动刀的小步）**：在 **`api_v1._sse_frame`** 对 SSE `data:` JSON 使用 **`separators=(',', ':')`**（仍 **`ensure_ascii=False`**），减少帧体积与 **`json.dumps`** 少量开销；**不改变**事件名与字段语义。**验证**：`tests/test_stream5_api.py`、`tests/test_sse_chat_contract.py` 绿；`npm run build` 无回归。
- **S14（第二热点 · Obs 写链）**：在 **`obs/tool_chain.py`** 的 **`param_digest_for_log`**（嵌套 dict/list 序列化）与 **`emit_tool_chain_v1`** 行 JSON 同样使用紧凑 **`separators`**；高 **`audit`** / 多工具会话下维护轨字符串略短。**验证**：`tests/test_obs_tool_chain.py` 绿。
- **S15**：**`ARCHITECTURE.md`** 已增 **§4.1** 索引本基线；根 **`README.md`** 未改（若需对外「一键复现 profiling」再补链即可）。

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

---

## 2026-05-14 — 第四阶段 A7：S1～S3 收口

- **结论**：**S1**（CLI 骨架、`--help`、`--dry-run` 不写盘）、**S2**（`DraftPromotionPort` + mtime / 禁止静默覆盖 + 晋升后 HSI）已由 **`src/logos/tools/promote_draft.py`**、**`ports/draft_promotion.py`**、**`tools/draft_promotion_fs.py`** 与 **`tests/test_promote_draft_cli.py`**、**`tests/test_draft_promotion_fs.py`** 覆盖；**S3** 以仓库根 **`README.md`** 草稿晋升小节与 **`KSFS开发.md`** §7.1 / §8 互链收口；GUI 未新增首屏入口，与 **`第四阶段开发计划.md`** **G4** 可选薄封装分工一致。
- **排期**：后续 **MCP S4～S6** 已另记一则；主线下一项为 **S7**（Obs O1）。

---

## 2026-05-14 — 第四阶段 MCP：S4～S6 收口

- **结论**：**S4** 审计写入 **`重要子系统开发文档/MCP开发.md`** §8.1；**S5** 为 `build_v01_guarded_tool_registry` 增加 **MCP discover 进程内缓存**（`clear_mcp_discovery_cache` 可显式清空），并保持 **`test_mcp_stdio_process_leak`** 与 **`test_build_registry_reuses_mcp_discovery_cache`** 绿（本机若缺 `psutil` 则 L2 测跳过）；**S6** 对 **`skills.mcp_servers` 非列表** 在 `merged_dict_to_app_settings` **fail-fast**（`ValueError`），单测 **`test_mcp_servers_must_be_yaml_list`**。
- **排期**：**Obs S7～S10** 已另记一则；主线下一项为 **§9.3 软件性能（S12～）**（见 **`第四阶段开发计划.md`**）。

---

## 2026-05-14 — 第四阶段 Obs：S7～S10 收口 + S11 跳过

- **结论**：**S7～S10** 已落地：**`src/logos/harness/obs/tool_chain.py`** 提供冻结字段 **`logos_tool_chain_v1`**、``param_digest_for_log`` 脱敏；**`logos.agent.react`** + **`api_v1.chat`** 线程局部 profile 与步号；单测 **`tests/test_obs_tool_chain.py`**。**S11（Obs O4 GUI）** 本迭代 **跳过**：与 **`第四阶段开发计划.md`** **G1（设置与可发现性）** / **G2（CSP 等）** 同批做「日志根展示 / 打开 maint」更贴合 **`GUI开发文档.md`** IPC 边界，避免重复造薄壳。
- **排期**：下一里程碑 **S12**（软件性能基线），依赖 **S1～S10** 与 **S11 跳过** 已满足。

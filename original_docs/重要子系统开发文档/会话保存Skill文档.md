# 会话保存 Skill（摘要 · 待设计）

> **地位**：**持久化轨**占位说明；与 **档 B 本地会话缓存**（`DECISIONS.md` §13.4）分工明确——本 Skill **不负责** 日常多标签、跨重启 JSON 缓存。  
> **状态（2026-05-16）**：**当前不实现**；仅收束方向，供后续与 `KSFS开发.md`、`MCP开发.md` 对齐后展开全文规格。  
> **GUI**：用户 **显式指令** 时由前端触发；**ConversationLifecycle** 不内嵌 KSFS 语义。

---

## 1. 目标（摘要）

在用户命令下，将选定会话（或其中片段）**升格**为与 **KSFS / workspace** 相关的持久产物（具体形态待设计），例如：

- 导出为可落户草稿、绑定作品/项目元数据；
- 与 **设定导入**、**KSFS 修改** 等能力 **分入口**，不替代 `workspace/setting_entry/` 既定流水线。

**非目标（本 Skill 不做）**：

- 替代 GUI **档 B** 的 `userData/conversations/<id>.json`；
- 自动在归档/销毁时同步 KSFS；
- 会话列表、标签栏、缓存大小提醒（属 **GUI 缓存管理页**，见 `DECISIONS.md` §13.8）。

---

## 2. 与档 B / GUI 的边界

| 能力 | 归属 |
|------|------|
| 多标签、SSE、每会话 JSON、归档/销毁、缓存管理页 | **前端 ConversationLifecycle + Electron userData** |
| 跨重启恢复聊天 | **档 B JSON** |
| 用户说「保存到 KSFS / 作品库」等 | **本 Skill（持久化轨）**，按需调用 |

---

## 3. 预期分层（草案）

| 层级 | 职责 |
|------|------|
| **Skill（MCP 或宿主工具）** | Agent 可见入口；收会话引用或导出路径 → 调确定性写盘/晋升流程。 |
| **HDL / ports** | Schema、沙箱路径、`DraftPromotionPort` 等（复用 KSFS 既有闸门）。 |
| **I&I** | 若需 HTTP，另开契约轨；**不** 与 `POST /api/v1/chat` 会话 id 混用。 |

---

## 4. 恢复开发时的检查清单

1. 更新 **`DECISIONS.md` §13** 与本文，消除与 `KSFS开发.md` 冲突。  
2. 在 `skills/` 下新建独立包名（实现期再定）。  
3. GUI 仅增加「保存到…」类 **显式按钮/命令**，走 Agent + Skill，不读缓存目录裸路径。  
4. 契约 / S&G / Obs 变更走各自文档与 **`.cursor/rules/logos-api-contract.mdc`**。

---

*最后更新：2026-05-16 — 初版摘要占位。*

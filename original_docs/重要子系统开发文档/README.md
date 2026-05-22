# 重要子系统开发文档

> **地位**：实现细节多、需单独展开的子系统长文放在本目录，避免把 **`ARCHITECTURE.md`** 撑得过长。  
> **总纲**：**`../ARCHITECTURE.md`**；**KSFS / HDL 边界**以 **`KSFS开发.md`** 为**现行权威**。  
> **归档**：V0.1 总 SPEC / DEVPLAN 见 **`../已完成文档/`**（对照用，非现行主依据）。

---

## 现行主文档（优先阅读）

| 文件 | 内容 |
|------|------|
| [**`KSFS开发.md`**](KSFS开发.md) | KSFS 目录、**仅 `.md` 核心**、HSI/SVS、chunk、知识流、**设定导入 §7.3**、**`entity_template`** |
| [**`API-V0.2.md`**](API-V0.2.md) | **现行** HTTP 契约（`/api/v1/*`）、SSE 事件（含 `reasoning_delta`）、开发者端点 |
| [**`API终极文档.md`**](API终极文档.md) | **个人使用**场景下的 API 原则、可接受风险、改进优先级；不替代 V0.2 字段表 |
| [**`API-V0.1.md`**](API-V0.1.md) | V0.1 **归档**（对照用）；权威以 `API-V0.2.md` 为准 |
| [**`设定导入Skill开发.md`**](设定导入Skill开发.md) | 设定导入 Skill **封存规格**与恢复清单；与 `KSFS开发.md` §7.3、`DECISIONS.md` §12 配合 |
| [**`大纲规划skill.md`**](大纲规划skill.md) | **`outline_plan` 设计封存**；**开发暂停**，恢复前产品讨论定稿 |
| [**`会话保存Skill文档.md`**](会话保存Skill文档.md) | **持久化轨**占位：会话升格 KSFS/作品库（**当前不实现**）；与 `DECISIONS.md` §13 档 B 分工 |
| [**`MCP开发.md`**](MCP开发.md) | stdio MCP 多技能配置、渐进式披露与 Obs、进程测试分级、resources/prompts 与被动读取的定案建议 |
| [**`会话管理子系统开发文档.md`**](会话管理子系统开发文档.md) | **档 B 专项**：顶栏标签、`ConversationProvider`、归档/恢复与路由一致性；**自 F6 主排期挪出** |
| [**`任务与Skill驱动GUI定案.md`**](任务与Skill驱动GUI定案.md) | **第五阶段产品主轴**：技能面板、单任务三步、长对话 Skill、路由与 JSON、T0～T3 |
| [**`Skill形态与Prompt工程.md`**](Skill形态与Prompt工程.md) | 产品 Skill vs 工具 Skill；Prompt L1～L3；P0/P1/P2；范式×持久化矩阵 |
| [**`范式路由与PR定案.md`**](范式路由与PR定案.md) | **PR 语义定案**；四范式分工、Prompt 矩阵 |
| [**`PR开发文档.md`**](PR开发文档.md) | **PR 实施权威**：PR-0～PR-6 分步验收、PR 轨最终验收 |
| [**`配置驱动开发文档.md`**](配置驱动开发文档.md) | **CD 路线图**：浅层可改 vs 核心固定；CD-0～CD-4；与 F5 顺序及 touch 矩阵 |
| [**`GUI开发文档.md`**](GUI开发文档.md) | GUI + Electron 壳权威；**§11** T 轨、**§12** G 轨；与 **`产品化文档.md`** 分工见该文 §1 |
| [**`产品化文档.md`**](产品化文档.md) | Electron **下阶段**产品化：安装包、签名、`electron-updater`、真壳 E2E 等分步 A～F |
| [**`Obs开发文档.md`**](Obs开发文档.md) | **第四阶段** Obs 主线：调用链落盘、与 MCP 对齐、GUI 薄消费；分步 O1～O5 与验收 |
| [**`Harness Engineering文档.md`**](Harness%20Engineering文档.md) | **B 类**：LLM 输出质量、RAG、ReAct/CB/路由；与阶段主线解耦、持续迭代；**「性能」默认非指本文**（见 **`../已完成/第四阶段开发计划.md`** §8） |
| [**`../SPEC-DISPLAY-AND-LOGGING-V0.1.md`](../SPEC-DISPLAY-AND-LOGGING-V0.1.md)** | 展示与日志补充规格 |
| [**`../已完成/第五阶段开发计划.md`**](../已完成/第五阶段开发计划.md) | 第五阶段 F5-00～F5-10（**已归档**） |
| [**`../第六阶段开发计划.md`**](../第六阶段开发计划.md) | **现行**：F6-00～F6-09；主轴 **A（CD-2/3）+ B（G5/M-UI）+ E（import_setting）** |

---

## 按需增删的子文档（示例）

| 文件（示例） | 方向 |
|--------------|------|
| `Retrieval.md` | 融合排序、路由细节（若从总纲拆出） |
| `SG.md` | 沙箱、白名单、MCP 回收（若从总纲拆出） |

新建子文档时，在本 README **现行主文档**表格中增加一行即可。

---

*最后更新：2026-05-22 — 增补会话管理子系统开发文档索引。*

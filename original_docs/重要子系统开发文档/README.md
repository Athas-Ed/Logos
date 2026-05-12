# 重要子系统开发文档

> **地位**：实现细节多、需单独展开的子系统长文放在本目录，避免把 **`ARCHITECTURE.md`** 撑得过长。  
> **总纲**：**`../ARCHITECTURE.md`**；**KSFS / HDL 边界**以 **`KSFS开发.md`** 为**现行权威**。  
> **归档**：V0.1 总 SPEC / DEVPLAN 见 **`../已完成文档/`**（对照用，非现行主依据）。

---

## 现行主文档（优先阅读）

| 文件 | 内容 |
|------|------|
| [**`KSFS开发.md`**](KSFS开发.md) | KSFS 目录、**仅 `.md` 核心**、HSI/SVS、chunk、知识流、**设定导入 §7.3**、**`entity_template`** |
| [**`API-V0.1.md`**](API-V0.1.md) | HTTP 契约（chat / health 等）、SSE 事件 |
| [**`设定导入Skill开发.md`**](设定导入Skill开发.md) | 设定导入 Skill **封存规格**与恢复清单；与 `KSFS开发.md` §7.3、`DECISIONS.md` §12 配合 |
| [**`../SPEC-DISPLAY-AND-LOGGING-V0.1.md`](../SPEC-DISPLAY-AND-LOGGING-V0.1.md)** | 展示与日志补充规格 |

---

## 按需增删的子文档（示例）

| 文件（示例） | 方向 |
|--------------|------|
| `Retrieval.md` | 融合排序、路由细节（若从总纲拆出） |
| `SG.md` | 沙箱、白名单、MCP 回收（若从总纲拆出） |

新建子文档时，在本 README **现行主文档**表格中增加一行即可。

---

*最后更新：2026-05-12*

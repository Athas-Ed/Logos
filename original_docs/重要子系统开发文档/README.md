# 重要子系统开发文档

> 决策层 CB/PR、Retrieval、KSS/LKC、HSI、SVS、S&G 等模块**实现细节多、迭代快**时，在此目录拆分子文档记录，避免把 `ARCHITECTURE.md` 撑得过长。  
> **总纲**仍以仓库根侧 `ARCHITECTURE.md`（及对外 `docs/` 拷贝）为准；子文档写清日期与依赖的 SPEC 版本。  
> **V0.1 多 Agent 并行**：见 **`../DEVPLAN-V0.1-PARALLEL.md`**；**开工顺序**见该文件 **§7**。

## 建议子文档命名（按需创建）

| 文件（示例） | 内容方向 |
|--------------|----------|
| `CB.md` | 模板选择、历史窗口、预算分配、与 OM 的衔接 |
| `PR-ReAct.md` | JSON-only 协议、错误恢复、与 Game-writer 前代的差异 |
| `Retrieval.md` | HSI/SVS 路由、融合排序、返回 JSON schema |
| `KSS-LKC.md` | 同步流程、哈希与增量、与 KSFS 独立后的接口预留 |
| `HSI.md` | SQLite 表结构、迁移、与 LKC 文件一致性 |
| `SVS-Chroma.md` | Chroma 集合、嵌入驱动接口、重建与 Config 项 |
| `SG.md` | 沙箱路径、工具白名单、输出策略、**MCP 进程治理与回收** |
| `II-Composition.md` | I&I 组合根、端口与 Infrastructure 的装配顺序 |
| `API-V0.1.md` | HTTP 契约草案（chat / health） |

新建某子文档时，在本 README 上增加一行链接即可。

# KSFS 与叙事知识库

## 是什么

**KSFS**（Knowledge Storage File System）是 Logos 存放**游戏叙事设定**的目录树，也是系统的**唯一事实源**：检索、索引、晋升都以此为准，而不是以聊天历史或临时缓存为准。

每个叙事实体通常对应一个 **Markdown 文件**（`.md`），带 YAML front matter（如 `title`、`tags`）；系统分配的数字 **`id`** 写回 front matter，作为稳定身份。

## 与工作区的区别

| 位置 | 角色 |
|------|------|
| `paths.ksfs_root`（默认 `example_ksfs/`，含《西游记》示例数据） | 已「落户」的设定，参与 HSI/SVS |
| `workspace/pending_review/setting_entry/` | 设定导入或人工整理的**待晋升草稿** |
| `workspace/` 其他子目录 | 一般创作工件，非事实源 |

**不要**把未审核草稿直接当作 KSFS 事实源使用。

## 索引：HSI 与 SVS

从 KSFS 扫描构建两层索引（默认在 `.index/`，可重建）：

- **HSI**：SQLite 元数据（路径、mtime、正文哈希、`id`、title 等）。
- **SVS**：Chroma 向量库，按正文分块嵌入，供语义检索。
- **Sparse / Hybrid / KG**：规划中（参照检索子系统开发路线 R1～R4）。

检索前通常会增量同步 KSFS → HSI → SVS。各目录下的 `README.md` 不作为实体扫描。

## 设定导入与重叠提示

**设定导入** Skill 可将结构化批次渲染为 `pending_review/setting_entry/` 下的 Markdown。导入前可进行**只读重叠扫描**（批内重复、草稿覆盖、KSFS 路径冲突），结果以 warnings 形式呈现，**不由 LLM 判定**是否冲突。

## 草稿晋升

人审通过后，将 `pending_review/setting_entry/` 中选定草稿**复制**到 KSFS 对应路径，并触发 HSI 同步：

- **API**：`POST /api/v1/setting-entry/promote`（可选 `draft_relpaths`）
- **CLI**：`python -m logos.tools.promote_draft --workspace ./workspace --target-ksfs <KSFS根> --apply`
- **`--dry-run`**：仅预览，不写盘

晋升遵守 **mtime 校验**与**禁止静默覆盖**已有 KSFS 文件。

## 实体模板

`resources/entity_template/` 存放 JSON Schema、渲染规格与 pipeline 配置（如 `default_import_v0`），与 `ksfs_root` **分离**，避免与用户实体混扫。

**Git**：

- `resources/ksfs/` 下的个人创作实体默认 **.gitignore** 不入库（仅 README 可提交）
- `example_ksfs/` 下的《西游记》示例数据**已提交至仓库**，为开箱体验提供内容
- `workspace/` 下的草稿档案默认不入库

## 格式约定摘要

- 核心格式：**仅 `.md`** 进入 HDL 扫描；`.docx`/PDF 等需经独立 Skill 转为 Markdown 再落户。
- 变更检测哈希基于 **front matter 之后的正文**，不含 front matter 本身。
- 单机、单进程本机部署为默认假设。

## 相关文档

- [架构概览](../架构概览.md)
- [任务与 Skill 界面](任务与Skill界面.md)（设定导入 Skill）
- [HTTP API 概览](HTTP-API概览.md)（promote 端点）

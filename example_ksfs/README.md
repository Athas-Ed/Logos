---
id: "80000"
---

# 示例 KSFS — 西游记

本目录为一份基于《西游记》的示例叙事知识库，供快速演示和体验检索功能使用。

> ✅ 本目录**已提交至仓库**，默认 `config/defaults.yaml` 的 `paths.ksfs_root` 即指向此处，克隆仓库后可直接体验。

## 内容一览

| 分类 | 文件 | 说明 |
|------|------|------|
| 人物 | 孙悟空.md | 核心主角 |
| 人物 | 唐僧.md | 师父 |
| 人物 | 猪八戒.md | 二弟子 |
| 人物 | 白骨精.md | 经典妖怪 |
| 地点 | 花果山.md | 孙悟空出生地 |
| 地点 | 火焰山.md | 取经劫难之一 |
| 势力 | 取经团队.md | 师徒四人 |
| 势力 | 天庭.md | 三界主宰 |
| 概念 | 如意金箍棒.md | 孙悟空兵器 |
| 种族 | 妖族.md | 妖怪种族概论 |

## 数据规格

每篇实体文件遵循标准 KSFS 格式：YAML front matter（含 `id`、`title`、`tags`、`relations`）+ Markdown 正文。
关系字段预设了实体间关联（如人物 ↔ 地点、人物 ↔ 物品），可在 CozoDB KG 中验证路径查询。

## 启动方式

默认 `config/defaults.yaml` 的 `paths.ksfs_root` 已指向 `./example_ksfs`，GitHub 克隆后直接启动即可拥有可体验的示例内容。

- **Docker 体验**：`start.cmd` / `./start.sh`
- **本地开发**：`scripts/start_logos.cmd`（Windows）或手动分步启动

若有个人创作 KSFS，在 `config/local.yaml` 中覆写 `paths.ksfs_root` 指向你的目录即可。

## 面试用途

- 展示「KSFS 作为唯一事实源」的设计理念
- 验证三路融合检索（HSI + SVS + FTS5）端到端流程
- 配合 CozoDB 演示实体关系路径查询（如：孙悟空 → 持有 → 如意金箍棒 → 位于 → 花果山）

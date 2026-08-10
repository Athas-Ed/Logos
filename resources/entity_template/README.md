# `entity_template` — KSFS 实体形态契约

本目录存放 **实体模板**：约束 KSFS 中 **`.md` 实体**的结构（front matter、路径规则、章节骨架等），供 **设定导入**、未来 **KSFS 修改** 等能力按同一契约生成或校验文件。

> **现阶段（2026-05-12）**：**不实现**设定导入全链；已提交的 **`default_import_v0/`** 为 **封存用 MVP**，供下阶段开箱接续（见 **`original_docs/重要子系统开发文档/设定导入Skill开发.md`**）。本阶段 KSFS 开发**不依赖**加载该 profile。

## 与相邻目录的边界

| 目录 | 用途 |
|------|------|
| **`resources/prompts/`** | CB **对话**用 Prompt，不承载 JSON Schema / 落盘渲染规则。 |
| **`paths.ksfs_root`（默认 `example_ksfs/`）** | **事实源**：用户/项目的实体 `.md`；勿把契约文件放在此树下以免与扫描语义混淆。 |
| **`workspace/setting_entry/`** | **待落户草稿**：设定导入经渲染写出的 `.md`（晋升前）；**非**事实源、**非**本目录；与 `ksfs_root` 分离。说明见仓库根 **`workspace/setting_entry/README.md`**、`KSFS开发.md` §2、§7.3。 |
| **`resources/entity_template/`** | **本目录**：可提交的 **profile** 与子资源；版本化约定见 `original_docs/DECISIONS.md` §9。 |

## 推荐布局（实现期照此或显式偏离并改文档）

```text
resources/entity_template/
  <profile_name>/          # 例：MVP 见 default_import_v0/
    manifest.yaml          # 单一入口：schema、渲染、可选 llm 说明路径
    schema.json            # 或与 manifest 约定内嵌/生成
    ...                    # 渲染规格等
```

**MVP profile（封存，下阶段「设定导入」用）**：已提交 **`default_import_v0/`**（含 `manifest.yaml`、`schema.json`、`render_spec.yaml`、`llm_instructions.md` 与 **`examples/`** 金样）。说明见 **`original_docs/重要子系统开发文档/设定导入Skill开发.md`**；默认 profile 名见 `config/defaults.yaml` 的 **`paths.entity_template_profile`**（本阶段 KSFS 实现**可不加载**）。

权威说明：`original_docs/重要子系统开发文档/KSFS开发.md` §2、§7.3.5；排期与契约细节 `original_docs/下一阶段开发计划.md` §2.6。

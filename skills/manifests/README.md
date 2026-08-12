# 产品 Skill manifest（`skills/manifests/`）

与 **`skills/<包>/server.py`**（MCP **工具 Skill**）并列；本目录仅存放**产品 Skill** 的宿主 manifest，供 `logos.platform.skills_registry.get_skill_manifest` 加载。

## 约定（F5-01 写死）

| 项 | 值 |
|----|-----|
| 路径 | `<repo>/skills/manifests/<skill_id>.yaml` |
| 加载 API | `get_skill_manifest(skill_id)` → `SkillManifest` |
| L1 Blueprint | `skills/<skill_id>/DESIGN.md`（`blueprint_path` 可指向） |

## 必填字段

`skill_id`、`display_name`、`persistence_tier`、`paradigm`、`turn_policy`、`allowed_tools`、`prompt_runtime_key`、`input_schema`

## 可选字段（GUI）

| 字段 | 用途 |
|------|------|
| `description` | 技能面板卡片一句话摘要 |
| `ui_instructions` | 任务页 / 对话页 **「技能说明」** 区块正文（多行用 YAML `\|`）；经 `GET /api/v1/bootstrap` → `skills[].ui_instructions` 注入，**勿**再在 `src/gui` 按 skill_id 硬编码 |

说明见 **`docs/子系统文档/Skills与MCP扩展.md`**。

## 内置样例

- **`lint_zh.yaml`** — `dialogue` + `p2` + `turn_policy: single`
- **`chat_inspire.yaml`** — `dialogue` + `p2` + `turn_policy: multi`
- **`retrieve_qa.yaml`** — `react` + `allowed_tools: [retrieve, read_ksfs, kg_query]`（检索后读原文，F5-08）
- **`outline_plan.yaml`** — `react`（检索已有设定后产出结构化大纲；原 plan 范式演示已迁移至 react）

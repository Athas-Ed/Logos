# Profile `default_import_v0`

> **现阶段**：本 profile 为 **设定导入** 的 **封存用 MVP**；**当前里程碑不实现**导入全链，见 **`original_docs/重要子系统开发文档/设定导入Skill开发.md`**。

**MVP 实体模板 profile**：`manifest.yaml` 为单一入口；与 `KSFS开发.md` §7.3 对齐；排期与封存说明见 **`original_docs/重要子系统开发文档/设定导入Skill开发.md`**。

- **改字段请先动** `schema.json`，再同步 `llm_instructions.md` 与金样（或引入生成脚本），避免两套真理。
- **金样**：见 `examples/`；单测 golden diff 应以此目录为基准，正式定稿后可替换内容、保留结构。

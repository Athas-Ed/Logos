---
id: "10004"
---
# 个人 KSFS 知识库（可选，`paths.ksfs_root` 覆盖目标）

本目录用于存放**个人创作**的叙事设定实体 `.md`。默认 `paths.ksfs_root` 指向 `example_ksfs/`（克隆即用），有个人创作后将本路径填入 `config/local.yaml` 的 `paths.ksfs_root` 即可。

**请勿将个人 `.md` 创作提交到 Git**：除本说明外，树内实体文件已由 `.gitignore` 忽略。

- 约定见 [**docs/子系统文档/KSFS与叙事知识库.md**](../../docs/子系统文档/KSFS与叙事知识库.md)
- **开箱体验**：仓库根 **`example_ksfs/`** 含《西游记》示例数据，默认 `ksfs_root` 即指向它

**`.index/`**（默认在仓库根，已 gitignore）：HSI（`.high-speed_index`）与向量库（`.vector_index/`）。勿将索引目录与 KSFS 正文混放。

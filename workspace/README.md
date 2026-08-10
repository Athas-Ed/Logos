# workspace

本目录为 **工作空间**：草稿、工件、导入待审文件等；**不是** KSFS 事实源（事实源为配置项 **`paths.ksfs_root`**，默认 `example_ksfs/`）。

**档 B 会话 JSON**（任务/归档缓存）默认在 **`conversations/`** 子目录，由配置 **`paths.CONVERSATIONS_CACHE`**（默认 `./workspace/conversations`）控制。

子目录按用途划分，避免不同功能互相覆盖。默认 **除本 README 与 `setting_entry/README.md` 外** 仍由 `.gitignore` 忽略，便于本地随意实验而不误提交。

详见 **`docs/子系统文档/KSFS与叙事知识库.md`**。

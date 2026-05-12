# 金样（golden fixtures）

| 文件 | 用途 |
|------|------|
| `minimal_batch.json` | 最小合法批次（单 unit、无 suggestions）。 |
| `minimal_character_expected.md` | 与 `render_spec.yaml` 一致时，**期望**渲染出的单文件正文（供 golden diff）。 |
| `with_suggestions_batch.json` | 含 `suggestions[]` 的批次。 |
| `with_suggestions_expected.md` | 对应期望输出。 |

实现 A6 后，应用 **同一渲染逻辑** 对 `*_batch.json` 跑一遍，与 `*_expected.md` 做字节级或规范化后比较。

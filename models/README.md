# 本地模型目录（工具向）

嵌入等**非 Git 权重**放在 `tooling/` 下（该目录已被 `.gitignore` 忽略）。

## 默认建议路径（与 Config 一致即可）

（当前仓库已按此路径放置权重时可跳过拷贝步骤。）将本机已下载的 **BAAI/bge-small-zh-v1.5** 权重文件复制到：

```text
models/tooling/embeddings/bge-small-zh-v1.5/
```

实现侧通过 **嵌入驱动接口** 读取；具体路径由配置项指定（勿在代码中写死唯一模型）。若你使用其他布局，只要在 Config 中指向正确目录即可。

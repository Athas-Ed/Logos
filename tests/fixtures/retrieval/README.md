# 检索基准测试数据集

本目录包含用于评估 Logos 检索子系统（HSI / SVS / Sparse / 融合）的中文叙事基准集。

## 数据来源

所有内容均为**手工编写的原创架空设定**，包括：

- **Lore（传说/背景）**：琥珀钟楼、九号符文、碎星剑传说
- **Characters（角色）**：林夜、苏晴雪、铁骨、姜元启
- **Locations（地点）**：青城峰、旧城区、黑石关、熔火城
- **Items（物品）**：逐风长弓、符文动态共振模型、冰蚕丝、霜牙与火喙
- **Organizations（组织）**：符文学院、青岚宗

## 设计原则

- 纯中文叙事内容，包含专有名词、成语、古风/架空设定
- 每个文件含完整 front matter（`title`、`classification`、`tags`）
- 文件内容风格多样：有的 title=正文关键词，有的 title≠正文关键词
- 覆盖 4 个子分类、17 个文件，每个文件 200～1500 字
- 包含实体间引用关系（林夜↔逐风↔铁骨、苏晴雪↔姜元启↔符文学院 等）

## 查询集 (queries.json)

35 条查询，覆盖以下类型：

| 类型 | 数量 | 测试组件 |
|------|------|----------|
| `exact_title` | 10 | HSI |
| `title_extra` | 2 | HSI |
| `body_paraphrase` | 4 | SVS |
| `body_exact_phrase` | 13 | Sparse |
| `body_noun` | 1 | Sparse |
| `body_hybrid` | 4 | HSI+SVS+Sparse |
| `relation_paraphrase` | 1 | KG（未来） |

另有 2 条负样本（无预期命中）用于测试降级行为。

## 使用方式

```python
from tests.retrieval_benchmark import load_queries
queries = load_queries("tests/fixtures/retrieval/queries.json")
```

或通过 pytest：

```bash
# 全量基准
pytest tests/retrieval_benchmark.py -q

# 仅 sparse 相关
pytest tests/retrieval_benchmark.py -q -k "sparse"

# 仅语义（SVS）相关
pytest tests/retrieval_benchmark.py -q -k "svs or semantic"
```

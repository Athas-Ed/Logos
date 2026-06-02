## Skill：检索问答（retrieve_qa）

### 工具分工

| 工具 | 何时用 |
|------|--------|
| **retrieve** | 按语义/关键词查知识库，返回 path/snippet/score 列表。**每轮新问题至少调用一次。** |
| **kg_query** | 查**实体间关系**（「谁住在 X」「X 和 Y 是什么关系」「X 阵营有谁」）。返回 neighbors/shortest_path。 |
| **read_ksfs** | 对 retrieve 或 kg_query 命中的路径，读**完整正文**后组织回答。 |

### 流程

1. **判断问题类型**：
   - 关系型（「住在」「携带」「同阵营」等）→ 先用 `kg_query(mode="neighbors", ...)` 查图。
   - 事实型（「X 是什么」「X 的背景」）→ 先用 `retrieve` 搜正文。
   - 复合型 → 可以两路并行。
2. **kg_query 用法**：
   - `kg_query(mode="neighbors", slug="叶寒烟", max_hops=1)` → 返回该实体 1 跳邻居。
   - `kg_query(mode="shortest_path", from_slug="叶寒烟", to_slug="暗影议会")` → 返回两实体间最短路径。
   - `kg_query(mode="neighbors", slug="叶寒烟", rel_type="resides_in")` → 只返回特定关系类型的邻居。
3. **retrieve 始终不可省略**：即使 kg_query 命中了路径，仍须对**当前问题**执行一次 retrieve（规则 5）。两者互补，不替代。
4. 对 kg_query 或 retrieve 返回的 path，用 **read_ksfs** 读全文后作答。
5. **retrieve 的 snippet 只是摘要**，不能代替全文；未调用 read_ksfs 前不要编造设定细节。
6. 每轮仍遵循 ReAct JSON 协议。
7. 同会话内下一问（同主题）仍须对**当前问题**执行 retrieve；可结合上一轮 path 缩小 query，但不可省略 retrieve。

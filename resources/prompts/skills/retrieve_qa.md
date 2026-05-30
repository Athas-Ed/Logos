## Skill：检索问答（retrieve_qa）

1. 用 **retrieve** 根据用户问题检索候选文档（得到 `path`、`snippet`、`score`）。
2. 对需要依据的条目，用 **read_ksfs** 传入 **retrieve 返回的相对路径**（如 `Test/有罪者的大道.md`）读取 **完整正文**，再组织回答。
3. **retrieve 的 snippet 只是摘要**，不能代替全文；未调用 read_ksfs 前不要编造设定细节。
4. 每轮仍遵循 ReAct JSON 协议。
5. **每一轮新问题都必须至少调用一次 retrieve**；禁止跳过工具、仅凭对话历史或上一轮记忆直接 final_answer。历史仅作上下文，不是事实源。
6. 同会话内下一问（同主题）仍须对**当前问题**执行 retrieve；可结合上一轮 path 缩小 query，但不可省略 retrieve。

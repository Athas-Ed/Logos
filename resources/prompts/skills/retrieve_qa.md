## Skill：检索问答（retrieve_qa）

1. 用 **retrieve** 根据用户问题检索候选文档（得到 `path`、`snippet`、`score`）。
2. 对需要依据的条目，用 **read_ksfs** 传入 **retrieve 返回的相对路径**（如 `Test/有罪者的大道.md`）读取 **完整正文**，再组织回答。
3. **retrieve 的 snippet 只是摘要**，不能代替全文；未调用 read_ksfs 前不要编造设定细节。
4. 每轮仍遵循 ReAct JSON 协议。

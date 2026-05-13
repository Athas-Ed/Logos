# KSFS 开发约定（权威）

> **地位**：**KSFS 及与之相关的 HDL / Retrieval 边界** 的现行权威说明。若与 [`../已完成文档/SPEC-V0.1.md`](../已完成文档/SPEC-V0.1.md)（归档）中 KSS/LKC、`workspace` 为事实源等表述冲突，**以本文与 `ARCHITECTURE.md` / `GLOSSARY.md` / `DECISIONS.md` 为准**。  
> **状态**：架构已定案；实现分期落地，**以代码与测试为准**对齐本文。  
> **实现进度（摘要）**：已移除 LKC 产品路径；**`sync_ksfs_hsi`**（`logos.persistence`）自 **`ksfs_root`** 扫描 **`*.md`**（**跳过各层 `README.md`**），以 **仅正文 body** 的哈希 + **mtime** 增量写 HSI；**已实现** HSI **纯数字 id 发号**、front matter **`id:` 回写**、**§3.4** 声明 id 与 HSI **冲突时重发号并回写**；**`ensure_ksfs_hsi_registered`** 提供**进程内至多一次** KSFS→HSI 登记（默认在 **`FusedRetrievalService.query`** 首次调用前懒登记，可选 **`paths.sync_hsi_on_startup`** 于 FastAPI lifespan 启动即登记）。**`read_ksfs`** 只读 KSFS；上述同步与登记行为由 **`tests/test_stream2_persistence.py`** 覆盖。**定案**：KSFS **仅 `.md`** 入核心扫描；**`.docx`/PDF 不纳入 HDL 核心**（可选 Skill，见 **§3.0**、[`../DECISIONS.md`](../DECISIONS.md) §12）。**SVS**：**§5 分块**、**§5.5 `chunk_id`**、**Chroma 增量**（`sync_ksfs_svs_incremental` / `SvsEmbeddingStateStore`，见 **`tests/test_stream2_persistence.py`** 与 **`chroma_bootstrap`**）。**设定导入**语义见 **§7.3**；Skill 全链封存与恢复见 [**`设定导入Skill开发.md`**](设定导入Skill开发.md)（排期见 [`../下一阶段开发计划.md`](../下一阶段开发计划.md)）。

---

## 1. 目标与范围

- **KSFS**：Logos **HDL** 子系统，存放**叙事知识**的**唯一事实源**（个人向 Agent）。
- **用户**：游戏作家 / 编剧；以文字与 Markdown 实体为主。
- **不在本文**：GUI 像素级细节、完整 KG 算法（仅预留接口方向）。MCP 工具边界见 **`DECISIONS.md` §12** 与 **`设定导入Skill开发.md`**。

---

## 2. 目录与仓库边界

| 项 | 约定 |
|----|------|
| **KSFS 根** | **`paths.ksfs_root`**，默认 **`./resources/ksfs`**（相对仓库根）。 |
| **工作空间 `workspace/`** | **非**事实源；多用途子目录分区，避免互相覆盖。 |
| **待落户设定 `workspace/setting_entry/`** | **设定导入**（§7.3）经本地渲染产出的 **待晋升** `.md` **默认**落此（代码路径小写 `setting_entry`）。**不**视为已在 `ksfs_root` 落户或已完成 HSI 登记。说明见仓库内 **`workspace/setting_entry/README.md`**（若已按 `.gitignore` 例外提交）。 |
| **`.gitignore`** | **KSFS 树内用户内容**常整体忽略；仓库可保留 **`resources/ksfs/README.md`** 等说明。 |
| **`logs/`** | 仓库根；Obs 写入。 |
| **`.index/`** | **`.high-speed_index`**（HSI）、**`.vector_index/`**（Chroma）。勿混入与索引无关的旧实验目录。 |
| **图片（未来）** | 如 **`resources/image/`**（可配置）；与 KSFS 正文规则独立演进。 |
| **实体模板根** | **`resources/entity_template/`**（可提交）：提取规格、JSON Schema、渲染规格、`manifest.yaml` 等；**不在** `ksfs_root` 下，避免与用户实体混扫。详见 **§7.3.5**、[`../DECISIONS.md`](../DECISIONS.md) §9。 |

---

## 3. 文件类型与实体模型

| 项 | 定案 | 说明 |
|----|------|------|
| **核心格式** | **`.md`** | 一文件一实体；**各目录 `README.md`** 不进入 `iter_documents`（说明文）。 |
| **实体粒度** | **一源文件 = 一实体** | 演进若变，另文约定。 |
| **实体 ID** | **`id` 逻辑主键** | HSI 分配并回写 YAML；见 **§3.2**；草稿与合并见 **§3.4、§3.5、§7.3**。 |

### 3.0 核心路径与可选摄取（定案）

| 层级 | 定案 |
|------|------|
| **KSFS 事实源（核心）** | **仅 `.md`**；扫描与登记仅针对 Markdown 实体。 |
| **可选扩展** | **`.docx`/PDF/其他二进制** **不**纳入 HDL 核心；经 **独立 MCP Skill** 摄取（如抽文本 → §7.3 或辅助粘贴）。 |
| **`.txt`** | 入库前建议规整为 **`.md`** 再入 `ksfs_root`。 |

**废止**：旧「多格式 HDL 核心优先级表」撤销；多格式仅为 **`DECISIONS.md` §12.2** 可选能力。

### 3.1 展示字段 vs 身份

- **`title`、`tags` 等**：仅元数据；**不参与**身份拼接；改标题**不得**改 `id`。

### 3.2 实体 ID、HSI 登记与回写（定案）

| 项 | 定案 |
|----|------|
| **身份** | **`id`** 建议 SQLite `INTEGER PRIMARY KEY` 自增或等价；**`id:`** 写回 **front matter**；新建稿默认不手写 `id`。 |
| **路径** | **`rel_path`** 相对 `ksfs_root`；**移动/重命名**只更新 HSI（及 SVS 元数据）中路径，**`id` 不变**；chunk 以 **`entity_id`** 关联。 |
| **变更检测哈希（§4.2 用途 A）** | **仅 body**（front matter **之后**的 Markdown）；**不含** front matter。回写 `id:` 不改 body → 不触发正文类重嵌。实现：`sync_ksfs_hsi` / `_body_content_hash`。 |
| **自动登记** | **进程启动**或 **首次依赖 HSI/SVS 的路径之前** — **先发生者触发一次** — KSFS 扫描 + HSI 对账；**同进程默认仅一次**（除非显式重建索引）。 |
| **回写载体** | **front matter**；**不用** sidecar。 |
| **mtime** | **登记**与 **晋升到 KSFS** 须校验 mtime；不一致则**中止**并提示。 |
| **产品假设** | 私有库；不要求「只拷 `.md`、不拷 HSI」即可携。 |

### 3.3 部署假定（定案）

- **单人、单进程**本机；多 worker 另文。
- **懒加载 vs lifespan**：实现自选；须满足 §3.2「先发生者一次」。

### 3.4 导入稿中已带 `id`（定案）

- **`id` 与 HSI 无冲突** → 保留并登记。
- **冲突** → 清除文件内 `id`，重走落户（HSI 新发号）。

### 3.5 Skill 待落户草稿（定案）

- **默认**：**`workspace/setting_entry/`** 下由设定导入渲染的 `.md`，**不应**含持久 **`id:`**；落户后由 §3.2 回写。
- **占位**：草稿中可使用 **`id: 待分配`** 等非持久字面（实现期约定），直至晋升。
- **例外**：用户显式合并**已带持久 `id`** 的整文件进入工作区时，适用 **§3.4**。

---

## 4. 索引、变更检测与增量

- **可重建**：HSI、SVS、未来 KG 均可自 KSFS 全量重建。
- **未变**：用途 A 哈希（§3.2）+ **mtime** 与 HSI 一致 → 未变。
- **SVS**：chunk 级增量。
- **删除/重命名**：默认全量对账；**暂不墓碑**（§4.1 预留）。
- **并发**：不强制文件锁；下次同步再拾取外部编辑。

### 4.1 墓碑（可选，当前不实现）

显式记录删除元数据，利审计与多副本；单机全量对账已够用。详见历史讨论稿；若启用再补迁移与合并策略。

### 4.2 规范化正文（两用途，勿混）

| 用途 | 目标 |
|------|------|
| **A** | 变更检测 / 嵌入输入：body 轻量规范化后 SHA-256。 |
| **B** | 子串命中：`_normalize` 与 **`_normalize_query`** 同规则（小写、去空白与常见标点）→ `norm_text`。 |

**Agent 不得自行选用 A/B**；由索引/Retrieval 固定路径调用。

---

## 5. 分块（Chunk）

### 5.1 `chunk_markdown`（定案）

- 有 **ATX 标题**：每标题至下一标题为一块；不足 **`min_chars`**（默认 **120**）可与上一块合并。
- **无标题**：空行分段再合并；过长（约 **>1000 字**）新开块。

### 5.2 `ChunkRecord`（建议字段）

`rel_path`、`chunk_index`、`heading`、`heading_level`、`text`、`norm_text`、`tokens`。

### 5.3 `_tokenize`（定案）

正则 **`[\u4e00-\u9fffA-Za-z0-9_]+`**。

### 5.4 `_normalize`（定案）

见 §4.2 **B**。

### 5.5 `chunk_id`（定案）

1. `entity_id`、`chunk_index`、`norm_chunk`（用途 A 对 chunk 文本）。  
2. `payload = f"v1\n{entity_id}\n{chunk_index}\n{norm_chunk}"`  
3. **`chunk_id = "ck_" + sha256(utf-8).hexdigest()`**（或截断策略全局一致）。

---

## 6. HSI 与 KG 预留

HSI 为 KG **预留 JSON 列**（或等价）；schema 待 KG 子系统设计。

---

## 7. 知识流与工具边界

```text
KSFS —(只读原语，索引/检索管线)—→ Retrieval —→ CB —→ LLM
```

- **只读 KSFS** API 主要面向 Retrieval / 索引构建。
- **Agent**：以 **`retrieve`** 等消费检索；**默认禁止**直接写 KSFS。
- **浏览与读原文（S&G 内置工具）**：**`list_ksfs`** 在 **`paths.ksfs_root`** 下列目录（可配置 `max_entries` / 非默认 `recursive`）；**`read_ksfs`** 按相对路径读单文件。二者与 **`retrieve`** 同属 **`GuardedToolRegistry`** 白名单。
- **写入**：**`workspace/`**；设定导入草稿默认 **`workspace/setting_entry/`**；建议按会话/日期分子目录。
- **晋升**：人工确认；**`DraftPromotionPort`** 等；晋升前 **mtime**（§3.2）。

### 7.1 晋升端口（建议）

- `list_promotion_candidates(drafts_root, ksfs_root) -> list[PromotionItem]`（`drafts_root` 常含 **`setting_entry`**）
- `apply_promotion(items_selected_by_user) -> report`

CLI/GUI 共用窄端口，避免逻辑重复。

### 7.2 评审摘要

层次清晰；检索为边界；人审晋升；全文需求用 Retrieval 受控读，不开放任意读盘。

### 7.3 设定集导入：JSON、校验、人审、晋升（定案）

**入口**：以 **MCP Skill** 为主（见 `DECISIONS.md` §12）；本节为 **HDL 语义** 与边界。实现封存见 **`设定导入Skill开发.md`**。

#### 7.3.1 导入 vs 修改

| 能力 | 面向 |
|------|------|
| **设定导入** | **新建**或尚未落户单元；产物在 **`workspace/setting_entry/`**。 |
| **KSFS 修改**（未来） | **已落户**、有持久 **`id`**；**分规格、分入口**。 |

**重叠**：与已落户实体判重时（slug/标题/指纹/近邻等，实现定启发式）**不得静默覆盖**；提示转 **「修改」** 或显式承担重复。

#### 7.3.2 持久 `id`

仅文件在 **`ksfs_root`** 完成登记后由 HSI 发号；**§3.4** 与 **§3.5** 并存。

#### 7.3.3 流水线

1. 用户：Skill + 粘贴批次（可选 `source_label`、`batch_id`）。  
2. LLM：**结构化 JSON**（非仅自由 md）。  
3. 本地：**JSON Schema** → 沙箱路径 → **渲染** → **`workspace/setting_entry/`** 下 `.md`。  
4. **人审**。  
5. **晋升** `ksfs_root` → 登记与 `id` 回写。

#### 7.3.4 草稿 + 修改建议

- **必有**可晋升草稿。  
- **可选** `suggestions[]`，关联单元或 **`verbatim_quote`**。  
- **禁止**常态「仅有建议无草稿」。  
- md 中可有独立章节（如 **`## 修改建议`**）。

#### 7.3.5 双模板 / 单契约与目录

| 名称 | 面向 |
|------|------|
| **提取规格（Import profile）** | LLM；与 **JSON Schema 同源**（manifest 生成 schema + 提示片段）。 |
| **渲染规格（Render profile）** | 本地；`classification` + `slug` → **相对路径**（根在 **`setting_entry/`** 下约定子树）、front matter 键、章节布局。 |

**实体模板目录**：**`resources/entity_template/<profile>/`**（与 **`resources/prompts/`**、**`ksfs_root`** 三分离）。推荐 **`manifest.yaml`**、`schema.json`、`render_spec.yaml`、`llm_instructions.md`、`examples/`。

#### 7.3.6 软 / 硬约束

- **Prompt 黑白名单**：软约束。  
- **硬闸门**：Schema、本地渲染、沙箱。

#### 7.3.7 SSOT

**落户**且已登记的 KSFS 实体为设定类**权威**；外部 Word 等为稿或归档；**默认无** Word 节级映射。

---

## 8. 与代码目录的映射

- **`src/logos/persistence/`**：`ksfs_filesystem`、`hdl_sync.sync_ksfs_hsi`、`hsi_sqlite` 等。
- **`src/logos/tools/`**：系统原语。
- **`harness/sg_layer/factory.py`**：**`read_ksfs`** 等注册。

---

## 9. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-10 | 初稿及多轮细化：HSI、chunk、mtime、知识流、CLI 端口。 |
| 2026-05-11 | 核心仅 `.md`；§3.5；§7.3；**`resources/entity_template/`**；与 `DECISIONS.md` §12 对齐。 |
| 2026-05-12 | **`workspace/setting_entry/`**、封存说明链至 **`设定导入Skill开发.md`**；本会话与仓库对齐重写本文。 |

---

*本文与 `DECISIONS.md`、`ARCHITECTURE.md` 同步维护。*

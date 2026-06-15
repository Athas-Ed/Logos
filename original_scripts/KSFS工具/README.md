# KSFS 测试数据生成（本地工具，暂不提交 Git）

在仓库根目录执行：

```powershell
# 仅骨架（默认 20 角色 / 20 地点 / 20 道具；专名已为正常中文）
python scripts/KSFS工具/generate_test_ksfs.py --no-polish --force

# LLM 润色（叙述体扩写，非机械罗列）
python scripts/KSFS工具/generate_test_ksfs.py --polish --style wuxia --force

# 专名主题可与润色风格分离；固定随机种子便于复现
python scripts/KSFS工具/generate_test_ksfs.py --characters 100 --locations 20 --items 30 --name-theme wuxia --seed 7 --polish --force
```

## 说明

- 输出默认：`resources/ksfs/Test/{characters,locations,items}/`（已在 `.gitignore` 的 KSFS 树内）。
- **专名**：由 `name_pools.py` 按 `--name-theme`（默认跟 `--style`）组合生成，不用「测试角色-01」占位。
- **文件名**：默认 `--filename-mode title`，即 `characters/司徒断水.md`；front matter 内 `slug` 仍为 `char-001` 等稳定键。`--force` 会先清空三分类目录下旧实体 `.md`（避免 slug 旧文件残留）。
- 交织关系用真实人名/地名/道具名交叉引用；档案编号 `CHAR-001` 等保留作检索锚点。
- 不写持久 `id:`，由 `sync_ksfs_hsi` 在同步时发号回写。
- `--polish` 且无 `api_key` 时，会交互询问：**只写骨架** 或 **退出**。
- 润色默认每批 **10** 个实体；锚点校验失败则回退该文件骨架正文。
- 生成后请自行触发索引（例如 dev 后端 + `retrieve`）。

## 风格 / 专名主题

`plain` | `wuxia` | `sci-fi` | `noir`；润色可用 `--style-file`，专名可用 `--name-theme` 单独指定。

## 删文件后立刻对账索引

不启动后端、不 `retrieve`，直接同步 KSFS → HSI/SVS：

```powershell
python scripts/KSFS工具/sync_ksfs_now.py
python scripts/KSFS工具/sync_ksfs_now.py --hsi-only
```

关注输出里的 **删除陈旧路径**（HSI）与 **删除陈旧块数**（SVS）；大于 0 表示已清理已删 `.md` 的索引残留。

---

## 检索基准测试（retrieval_benchmark/）

一键测 **HSI / Sparse / HSI+SVS+Sparse** 各组件 Recall/MRR，在**临时目录**生成测试数据，**不碰真实 KSFS**。

```powershell
# 一键基准（生成测试集 → 索引 → 跑全部组件 → 出报告）
python scripts/KSFS工具/retrieval_benchmark/cli.py bench

# 指定风格与规模
python scripts/KSFS工具/retrieval_benchmark/cli.py bench --theme wuxia --characters 30 --save-dir ./my_report

# 仅生成测试集，供你修改 queries.json 后再跑
python scripts/KSFS工具/retrieval_benchmark/cli.py generate --out-dir ./my_bench --theme sci-fi --seed 7
python scripts/KSFS工具/retrieval_benchmark/cli.py bench --ksfs-dir ./my_bench/ksfs --queries ./my_bench/queries.json

# 查看/对比结果
python scripts/KSFS工具/retrieval_benchmark/cli.py report --results ./my_report/hsi+svs+sparse.json
python scripts/KSFS工具/retrieval_benchmark/cli.py report --results ./baseline.json --compare ./after_changes.json
```

详见 `retrieval_benchmark/cli.py --help` 或各子命令 `--help`。

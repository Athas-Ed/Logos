"""
一键检索基准测试 CLI — 在临时目录生成测试 KSFS，跑各组件组合的 Recall/MRR，不碰真实数据。

用法（在仓库根执行）::

    # 生成测试集 + 全量基准（HSI / Sparse / HSI+SVS+Sparse）
    python scripts/KSFS工具/retrieval_benchmark/cli.py bench

    # 仅跑 sparse 和全量
    python scripts/KSFS工具/retrieval_benchmark/cli.py bench --components hsi,sparse,hsi+svs+sparse

    # 自定义测试集规模
    python scripts/KSFS工具/retrieval_benchmark/cli.py bench --characters 10 --locations 5 --items 5

    # 指定风格（专名主题）
    python scripts/KSFS工具/retrieval_benchmark/cli.py bench --theme wuxia --seed 7

    # 使用已有测试集 + 已有 query
    python scripts/KSFS工具/retrieval_benchmark/cli.py bench --ksfs-dir my_ksfs --queries my_query.json

    # 两步式：先生成，再改 query 后跑
    python scripts/KSFS工具/retrieval_benchmark/cli.py generate --out-dir ./my_bench --characters 30 --theme sci-fi
    python scripts/KSFS工具/retrieval_benchmark/cli.py bench --ksfs-dir ./my_bench/ksfs --queries ./my_bench/queries.json

    # 结果对比
    python scripts/KSFS工具/retrieval_benchmark/cli.py report --results ./my_bench/hsi+svs+sparse.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── repo path bootstrap ────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

_TOOL_DIR = Path(__file__).resolve().parent
_PARENT_TOOL_DIR = _TOOL_DIR.parent
for d in (_TOOL_DIR, _PARENT_TOOL_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

# ── imports that need sys.path ─────────────────────────────────────────

from logos.infrastructure.retrieval.fused import FusedRetrievalService  # noqa: E402
from logos.persistence import (  # noqa: E402
    SqliteMetadataIndex,
    SqliteSparseIndex,
    sync_ksfs_hsi,
    sync_ksfs_sparse_incremental,
)
from logos.ports.metadata import MetadataRecord  # noqa: E402
from logos.ports.retrieval import Citation  # noqa: E402
from logos.ports.sparse import SparseQueryHit  # noqa: E402
from logos.ports.vector import VectorQueryHit  # noqa: E402

try:
    from name_pools import build_world_names
except ImportError:
    build_world_names = None  # type: ignore[assignment]

# ── constants ──────────────────────────────────────────────────────────

THEMES = ("plain", "wuxia", "sci-fi", "noir")

_DEFAULT_CHARS = 15
_DEFAULT_LOCS = 8
_DEFAULT_ITEMS = 8

# 基准历史目录
_HISTORY_DIR = Path(".benchmark_history")

# ── stubs (reused from test code) ──────────────────────────────────────

class _Fixed512Embedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.03] * 512 for _ in texts]

class _NoopSemanticStore:
    def upsert_chunks(self, **kwargs: Any) -> None:
        return None
    def delete_ids(self, ids: list[str]) -> None:
        return None
    def query(self, query_embedding: list[float], top_k: int) -> list[VectorQueryHit]:
        return []

class _EmptyMetadata:
    def upsert(self, records: list[MetadataRecord]) -> None:
        return None
    def search_paths(self, *, prefix: str | None, limit: int) -> list[MetadataRecord]:
        return []

class _NoopSparseIndex:
    def upsert_chunks(self, **kwargs: Any) -> None:
        return None
    def delete_ids(self, ids: list[str]) -> None:
        return None
    def delete_by_paths(self, source_paths: list[str]) -> None:
        return None
    def search(self, query_text: str, top_k: int) -> list[SparseQueryHit]:
        return []

# ── data types ─────────────────────────────────────────────────────────

@dataclass
class Query:
    id: str
    text: str
    expected_paths: list[str]
    type: str
    tags: list[str]

@dataclass
class QueryResult:
    query_id: str
    citations: list[Citation]
    latency_s: float

@dataclass
class BenchmarkResult:
    component_label: str
    queries: list[QueryResult] = field(default_factory=list)
    _query_map: dict[str, Query] = field(default_factory=dict)

    def recall_at(self, k: int) -> float:
        hits = 0
        total = 0
        for qr in self.queries:
            q = self._query_map.get(qr.query_id)
            if q is None or not q.expected_paths:
                continue
            total += 1
            top_paths = {c.path for c in qr.citations[:k]}
            if any(ep in top_paths for ep in q.expected_paths):
                hits += 1
        return hits / total if total > 0 else 0.0

    def mrr_at(self, k: int) -> float:
        s = 0.0
        total = 0
        for qr in self.queries:
            q = self._query_map.get(qr.query_id)
            if q is None or not q.expected_paths:
                continue
            total += 1
            for rank, cit in enumerate(qr.citations[:k], start=1):
                if cit.path in q.expected_paths:
                    s += 1.0 / rank
                    break
        return s / total if total > 0 else 0.0

    def summary_dict(self) -> dict[str, object]:
        return {
            "label": self.component_label,
            "recall_at_1": self.recall_at(1),
            "recall_at_3": self.recall_at(3),
            "recall_at_5": self.recall_at(5),
            "recall_at_8": self.recall_at(8),
            "mrr_at_8": self.mrr_at(8),
        }


# ══════════════════════════════════════════════════════════════════════
#  Part 1: 生成测试 KSFS + queries.json
# ══════════════════════════════════════════════════════════════════════

def _fallback_names(num_chars: int, num_locs: int, num_items: int, seed: int) -> tuple[list[str], list[str], list[str]]:
    """当 name_pools 不可用时的降级名表。"""
    rng = random.Random(seed)
    surnames = "林赵沈顾周陆唐韩宋白程萧叶慕容".split()
    given = (
        "婉清 暮寒 承安 听雨 子衿 景和 思远 若兰 怀瑾 "
        "知微 映雪 修齐 明远 清和 予安 嘉木 云舒 望舒"
    ).split()
    loc_a = "青阳 临江 云梦 栖霞 白鹿 长汀 桃溪 北辰 南浦 西岭".split()
    loc_b = "镇 城 港 谷 驿 坊 书院 哨站 庄园 集市".split()
    item_a = "寒铁 旧铜 秘银 松纹 鲸脂 砂金 琉璃 竹编 鹿皮 炭墨".split()
    item_b = "短剑 长刀 信物 地图 药匣 灯笼 罗盘 印章 护符 名册".split()

    chars = [f"{rng.choice(surnames)}{rng.choice(given)}" for _ in range(num_chars)]
    locs = [f"{rng.choice(loc_a)}{rng.choice(loc_b)}" for _ in range(num_locs)]
    items_list = [f"{rng.choice(item_a)}{rng.choice(item_b)}" for _ in range(num_items)]
    return chars, locs, items_list


def _generate_ksfs(
    out_dir: Path,
    *,
    num_characters: int,
    num_locations: int,
    num_items: int,
    theme: str,
    seed: int,
) -> tuple[list[dict[str, Any]], list[Query]]:
    """在 ``out_dir`` 下生成 KSFS .md 文件，返回 (entity_info_list, queries)。"""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) 生成专名
    if build_world_names is not None:
        names = build_world_names(
            theme=theme,
            num_characters=num_characters,
            num_locations=num_locations,
            num_items=num_items,
            seed=seed,
        )
        char_names = names.characters
        loc_names = names.locations
        item_names = names.items
    else:
        char_names, loc_names, item_names = _fallback_names(
            num_characters, num_locations, num_items, seed,
        )

    rng = random.Random(seed + 10)

    # 2) 构建实体列表
    all_entities: list[dict[str, Any]] = []

    # --- characters ---
    for i, name in enumerate(char_names):
        tags = rng.sample(["游侠", "术士", "铁匠", "学者", "将领", "药师", "刺客", "商人", "官吏", "隐士"],
                          k=rng.randint(1, 3))
        detail = _char_detail(name, rng)
        all_entities.append({
            "classification": "character",
            "title": name,
            "tags": tags,
            "body": detail,
            "rel_path": f"characters/{name}.md",
            "keywords": [name] + [t for t in tags if len(t) >= 2],
        })

    # --- locations ---
    for i, name in enumerate(loc_names):
        tags = rng.sample(["城市", "关隘", "门派", "遗迹", "港口", "森林", "沙漠", "山脉", "洞穴", "圣地"],
                          k=rng.randint(1, 3))
        detail = _loc_detail(name, rng)
        all_entities.append({
            "classification": "location",
            "title": name,
            "tags": tags,
            "body": detail,
            "rel_path": f"locations/{name}.md",
            "keywords": [name] + [t for t in tags if len(t) >= 2],
        })

    # --- items ---
    for i, name in enumerate(item_names):
        tags = rng.sample(["武器", "防具", "道具", "书籍", "材料", "法器", "饰品", "工具", "食品", "秘宝"],
                          k=rng.randint(1, 3))
        detail = _item_detail(name, rng)
        all_entities.append({
            "classification": "item",
            "title": name,
            "tags": tags,
            "body": detail,
            "rel_path": f"items/{name}.md",
            "keywords": [name] + [t for t in tags if len(t) >= 2],
        })

    # 3) 写入 .md 文件
    for ent in all_entities:
        _write_md(out_dir, ent)

    # 4) 自动生成 queries.json
    queries = _auto_queries(all_entities, rng)

    return all_entities, queries


def _write_md(out_dir: Path, ent: dict[str, Any]) -> None:
    """写一个 .md 文件。"""
    path = out_dir / ent["rel_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    tags_yaml = ", ".join(ent["tags"])
    fm = (
        f"---\n"
        f"title: {ent['title']}\n"
        f"tags: [{tags_yaml}]\n"
        f"classification: {ent['classification']}\n"
        f"---\n\n"
    )
    path.write_text(fm + ent["body"].strip() + "\n", encoding="utf-8")


def _char_detail(name: str, rng: random.Random) -> str:
    keywords = [name]
    items = ["随身携带一柄", "擅长使用", "据传拥有一件"]
    weaps = ["古剑", "长弓", "短刃", "铁锤", "法杖", "暗器"]
    return (
        f"# {name}\n\n"
        f"{name}是{_where_from(rng)}的一位{'赫赫有名' if rng.random() > 0.5 else '低调隐居'}"
        f"的{_role(rng)}。\n\n"
        f"## 早年经历\n\n"
        f"{name}自幼便展现出非凡的{_talent(rng)}天赋。"
        f"据记载，ta在{rng.randint(8, 16)}岁那年第一次展现能力时，"
        f"周围的人都为之惊叹。\n\n"
        f"## 标志性装备\n\n"
        f"{name}{rng.choice(items)}{rng.choice(weaps)}，名为「{_weapon_name(rng)}」。"
        f"这件武器在其手中发挥出了远超寻常的威力。\n\n"
        f"## 著名事迹\n\n"
        f"{name}最被人称道的事迹是独自深入{_danger_place(rng)}，"
        f"在绝境中找到了{_treasure(rng)}。此后声望日隆。\n"
    )


def _loc_detail(name: str, rng: random.Random) -> str:
    feat = rng.choice(["云雾缭绕", "四季如春", "险峻异常", "幽深静谧", "繁华热闹"])
    return (
        f"# {name}\n\n"
        f"{name}位于{_region(rng)}，{feat}，是一处著名的{rng.choice(['名胜', '险地', '秘境', '要冲', '圣地'])}。\n\n"
        f"## 地理特征\n\n"
        f"{name}占地面积约{rng.randint(100, 5000)}亩，"
        f"四周{_surround(rng)}。\n\n"
        f"## 重要建筑\n\n"
        f"此处最引人注目的建筑是{rng.choice(['一座高塔', '一座大殿', '一座石碑', '一处泉眼', '一方祭坛'])}，"
        f"据说已有{rng.randint(100, 2000)}年历史。\n\n"
        f"## 传说\n\n"
        f"相传在远古时期，{name}曾是{_legend_event(rng)}的所在地。"
        f"至今仍能在{rng.choice(['石壁', '地面', '古树', '水底'])}上看到当年的痕迹。\n"
    )


def _item_detail(name: str, rng: random.Random) -> str:
    mat = rng.choice(["玄铁", "寒玉", "紫檀", "陨铁", "灵木", "冰晶", "龙骨"])
    return (
        f"# {name}\n\n"
        f"{name}是一件极其珍贵的{rng.choice(['法器', '武器', '宝物', '文献', '工具'])}。\n\n"
        f"## 外观描述\n\n"
        f"{name}通体由{mat}打造而成，表面刻有{rng.choice(['繁复的符文', '精细的纹路', '古老的铭文', '神秘的图案'])}。"
        f"在{rng.choice(['月光', '日光', '烛火', '暗处'])}下会发出{rng.choice(['幽蓝', '淡金', '银白', '赤红'])}的光泽。\n\n"
        f"## 制作工艺\n\n"
        f"相传{name}由{rng.choice(['上古匠人', '矮人大师', '精灵工匠', '隐世高人'])}耗费三年心血打造而成。"
        f"其制作工艺早已失传。\n\n"
        f"## 特殊效果\n\n"
        f"持有{name}的人可以获得{rng.choice(['力量增幅', '感知提升', '防护加强', '速度加快', '智慧启迪'])}的效果。"
        f"但若心术不正之人使用，则会遭到反噬。\n"
    )


def _where_from(rng: random.Random) -> str:
    return rng.choice(["北方边境", "南方水乡", "西域大漠", "东海之滨", "中部平原"])

def _role(rng: random.Random) -> str:
    return rng.choice(["游侠", "剑客", "术士", "医师", "铁匠", "学者", "猎人", "镖师"])

def _talent(rng: random.Random) -> str:
    return rng.choice(["剑术", "符法", "医术", "锻造", "弓术", "兵法", "机关"])

def _weapon_name(rng: random.Random) -> str:
    a = rng.choice(["霜寒", "惊雷", "落日", "追风", "破云", "断水", "星辉"])
    b = rng.choice(["剑", "弓", "刃", "锤", "杖", "枪", "针"])
    return f"{a}{b}"

def _danger_place(rng: random.Random) -> str:
    return rng.choice(["黑暗森林", "死亡沙漠", "冰封雪原", "毒雾沼泽", "火山熔洞"])

def _treasure(rng: random.Random) -> str:
    return rng.choice(["一枚古玉", "一本秘籍", "一颗灵珠", "一柄残剑", "一张地图"])

def _region(rng: random.Random) -> str:
    return rng.choice(["天池山脉", "落日平原", "苍茫海域", "无尽森林", "赤焰戈壁"])

def _surround(rng: random.Random) -> str:
    return rng.choice(["群山环抱", "碧水环绕", "密林遮蔽", "悬崖峭壁", "开阔平坦"])

def _legend_event(rng: random.Random) -> str:
    return rng.choice(["仙魔大战", "龙族迁徙", "建国大典", "星陨天降", "大洪水"])


def _auto_queries(entities: list[dict[str, Any]], rng: random.Random) -> list[Query]:
    """自动生成 queries.json。

    为每个 entity 生成：
    - 一条 exact_title query（title 原文）
    - 可选一条 body_exact_phrase（从正文取一个短语）
    - 少量跨实体 hybrid query
    """
    queries: list[Query] = []
    qid = 0

    def next_id() -> str:
        nonlocal qid
        qid += 1
        return f"Q{qid:03d}"

    for ent in entities:
        title = ent["title"]
        path = ent["rel_path"]

        # exact_title
        queries.append(Query(
            id=next_id(),
            text=title,
            expected_paths=[path],
            type="exact_title",
            tags=["hsi", "smoke"],
        ))

        # title_extra — title + 一个随机词
        extra = rng.choice(ent["tags"]) if ent["tags"] else ent["keywords"][-1]
        queries.append(Query(
            id=next_id(),
            text=f"{title} {extra}",
            expected_paths=[path],
            type="title_extra",
            tags=["hsi"],
        ))

        # body_exact_phrase — 从正文中取一个非 title 的 2-4 字词
        body = ent["body"]
        phrases = _extract_key_phrases(body)
        if phrases:
            phrase = rng.choice(phrases)
            queries.append(Query(
                id=next_id(),
                text=phrase,
                expected_paths=[path],
                type="body_exact_phrase",
                tags=["sparse", "fts"],
            ))

    # 少量跨实体 hybrid query（引用关系）
    if len(entities) >= 3:
        # 取第一个角色 + 第一个地点
        chars = [e for e in entities if e["classification"] == "character"]
        locs = [e for e in entities if e["classification"] == "location"]
        items_e = [e for e in entities if e["classification"] == "item"]
        if chars and locs:
            c = chars[0]
            l = locs[0]
            queries.append(Query(
                id=next_id(),
                text=f"{c['title']} {l['title']}",
                expected_paths=[c["rel_path"], l["rel_path"]],
                type="body_hybrid",
                tags=["hsi", "svs", "sparse"],
            ))
            if items_e:
                it = items_e[0]
                queries.append(Query(
                    id=next_id(),
                    text=f"{c['title']}的{it['title']}",
                    expected_paths=[c["rel_path"], it["rel_path"]],
                    type="body_hybrid",
                    tags=["hsi", "svs", "sparse"],
                ))

    return queries


def _extract_key_phrases(text: str) -> list[str]:
    """从正文中提取 2-4 字中文短语作为 keyword query 候选。"""
    import re
    # 匹配连续 2-6 个汉字
    candidates = re.findall(r"[\u4e00-\u9fff]{2,6}", text)
    # 去重、过滤常见停用词
    seen: set[str] = set()
    out: list[str] = []
    skip = {"以下", "以上", "这些", "那些", "位于", "因为", "所以", "但是", "然而", "虽然",
            "可以", "能够", "已经", "成为", "具有", "包括", "关于", "根据", "按照"}
    for c in candidates:
        if c not in seen and c not in skip and len(c) >= 2:
            seen.add(c)
            out.append(c)
    return out


# ══════════════════════════════════════════════════════════════════════
#  Part 2: 运行基准测试
# ══════════════════════════════════════════════════════════════════════

def load_queries(path: Path) -> tuple[list[Query], dict[str, Query]]:
    """加载 queries.json → (list[Query], map_by_id)。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: list[Query] = []
    qmap: dict[str, Query] = {}
    for item in raw:
        q = Query(
            id=str(item["id"]),
            text=str(item["text"]),
            expected_paths=[str(p) for p in item.get("expected_paths", [])],
            type=str(item.get("type", "")),
            tags=[str(t) for t in item.get("tags", [])],
        )
        out.append(q)
        qmap[q.id] = q
    return out, qmap


def make_retrieval_service(
    ksfs_root: Path,
    index_root: Path,
    components: str,
) -> FusedRetrievalService:
    """创建指定组件的融合检索服务（与 tests/retrieval_benchmark.py 一致）。"""
    hsi_db = index_root / ".high-speed_index"
    svs_state = index_root / ".svs_chunk_index.sqlite"
    sparse_db = index_root / ".sparse_fts.sqlite"

    meta: Any = SqliteMetadataIndex(hsi_db)
    embedder = _Fixed512Embedder()

    parts = components.split("+")
    use_hsi = "hsi" in parts
    use_svs = "svs" in parts
    use_sparse = "sparse" in parts

    store: Any = _NoopSemanticStore()
    if not use_hsi:
        meta = _EmptyMetadata()
    sparse_index: Any = None
    sparse_db_path: Path | None = None
    if use_sparse:
        sparse_index = SqliteSparseIndex(sparse_db)
        sparse_db_path = sparse_db

    return FusedRetrievalService(
        metadata_index=meta,
        semantic_store=store,
        embedder=embedder,
        sparse_index=sparse_index,
        lazy_hsi_ksfs_root=ksfs_root,
        lazy_hsi_db_path=hsi_db,
        lazy_svs_state_db=svs_state if use_svs else None,
        lazy_sparse_db_path=sparse_db_path,
        refresh_indexes_on_query=True,
    )


def run_benchmark(
    retrieval: FusedRetrievalService,
    queries: list[Query],
    top_k: int = 8,
    *,
    label: str = "",
) -> BenchmarkResult:
    """执行所有 query，收集命中 + 延迟。"""
    result = BenchmarkResult(component_label=label)
    for q in queries:
        result._query_map[q.id] = q
        t0 = time.perf_counter()
        cites = retrieval.query(text=q.text, top_k=top_k)
        dt = time.perf_counter() - t0
        result.queries.append(
            QueryResult(query_id=q.id, citations=cites, latency_s=dt)
        )
    return result


def format_terminal_report(result: BenchmarkResult) -> str:
    """生成终端友好报告。"""
    lines: list[str] = []
    lines.append("")
    lines.append(f"{'=' * 60}")
    lines.append(f"  {result.component_label}")
    lines.append(f"{'=' * 60}")
    lines.append(f"  {'指标':<16} {'值':<10}")
    lines.append(f"  {'-'*26}")
    for k in (1, 3, 5, 8):
        lines.append(f"  {'Recall@' + str(k):<16} {result.recall_at(k):.3f}")
    lines.append(f"  {'MRR@8':<16} {result.mrr_at(8):.3f}")
    lines.append("")
    lines.append(f"  {'Query':<8} {'类型':<18} {'Top-1 Path':<30} {'延迟(ms)':<10}")
    lines.append(f"  {'-'*66}")
    for qr in result.queries:
        q = result._query_map.get(qr.query_id)
        if q is None:
            continue
        top_path = qr.citations[0].path if qr.citations else "(无)"
        lines.append(f"  {q.id:<8} {q.type:<18} {top_path:<30} {qr.latency_s*1000:.1f}")
    lines.append("")
    return "\n".join(lines)


def save_json(result: BenchmarkResult, path: Path) -> None:
    """保存结果为 JSON。"""
    data = {
        "label": result.component_label,
        "recall_at_1": result.recall_at(1),
        "recall_at_3": result.recall_at(3),
        "recall_at_5": result.recall_at(5),
        "recall_at_8": result.recall_at(8),
        "mrr_at_8": result.mrr_at(8),
        "queries": [
            {
                "query_id": qr.query_id,
                "citations": [
                    {"path": c.path, "snippet": c.snippet, "score": c.score}
                    for c in qr.citations
                ],
                "latency_s": qr.latency_s,
            }
            for qr in result.queries
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_report_md(result: BenchmarkResult, path: Path) -> None:
    """保存 Markdown 报告。"""
    lines: list[str] = []
    lines.append(f"# 基准报告: {result.component_label}")
    lines.append("")
    lines.append(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## 汇总指标")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|-----|")
    for k in (1, 3, 5, 8):
        lines.append(f"| Recall@{k} | {result.recall_at(k):.3f} |")
    lines.append(f"| MRR@8 | {result.mrr_at(8):.3f} |")
    lines.append("")
    lines.append("## 逐查询详情")
    lines.append("")
    lines.append("| Query | 类型 | Top-1 Path | 延迟(ms) |")
    lines.append("|-------|------|------------|----------|")
    for qr in result.queries:
        q = result._query_map.get(qr.query_id)
        if q is None:
            continue
        top_path = qr.citations[0].path if qr.citations else "(无)"
        lines.append(f"| {q.id} | {q.type} | {top_path} | {qr.latency_s*1000:.1f} |")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── 历史追踪 ──────────────────────────────────────────────────────────

_HISTORY_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"


def save_history(
    result: BenchmarkResult,
    *,
    track_dir: Path = _HISTORY_DIR,
) -> Path:
    """将基准结果存入 ``track_dir/<timestamp>/`` 并更新 ``_summary.json``。"""
    ts = time.strftime(_HISTORY_TIMESTAMP_FORMAT)
    run_dir = track_dir / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    label = result.component_label.replace("+", "_")

    # 保存完整 JSON
    json_path = run_dir / f"{label}.json"
    save_json(result, json_path)

    # 保存 Markdown 报告
    md_path = run_dir / f"{label}.md"
    save_report_md(result, md_path)

    # 更新汇总文件
    summary_path = track_dir / "_summary.json"
    if summary_path.is_file():
        history = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        history = []
    history.append({
        "timestamp": ts,
        "component": label,
        "label": result.component_label,
        **result.summary_dict(),
    })
    summary_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return run_dir


def load_history_summaries(
    track_dir: Path = _HISTORY_DIR,
) -> list[dict[str, object]]:
    """读取 ``_summary.json``，按时间升序返回。"""
    summary_path = track_dir / "_summary.json"
    if not summary_path.is_file():
        return []
    return json.loads(summary_path.read_text(encoding="utf-8"))


def format_history_report(history: list[dict[str, object]]) -> str:
    """生成多轮基线演进对比表（Markdown）。"""
    lines: list[str] = []
    lines.append("# 检索基准演进")
    lines.append("")
    lines.append("| 时间 | 组件 | Recall@1 | Recall@3 | Recall@5 | Recall@8 | MRR@8 |")
    lines.append("|------|------|----------|----------|----------|----------|-------|")
    for entry in history:
        ts = str(entry.get("timestamp", "?"))
        comp = str(entry.get("label", entry.get("component", "?")))
        r1 = f"{entry.get('recall_at_1', 0):.3f}"
        r3 = f"{entry.get('recall_at_3', 0):.3f}"
        r5 = f"{entry.get('recall_at_5', 0):.3f}"
        r8 = f"{entry.get('recall_at_8', 0):.3f}"
        mr = f"{entry.get('mrr_at_8', 0):.3f}"
        lines.append(f"| {ts} | {comp} | {r1} | {r3} | {r5} | {r8} | {mr} |")
    lines.append("")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
#  Part 3: CLI
# ══════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="检索基准 CLI — 在临时目录生成测试 KSFS 并跑各组件 Recall/MRR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # --- bench (一键) ---
    b = sub.add_parser("bench", help="生成测试集 + 跑基准（一步到位）")
    b.add_argument("--characters", type=int, default=_DEFAULT_CHARS, help="角色数量")
    b.add_argument("--locations", type=int, default=_DEFAULT_LOCS, help="地点数量")
    b.add_argument("--items", type=int, default=_DEFAULT_ITEMS, help="物品数量")
    b.add_argument("--theme", choices=THEMES, default="plain", help="专名主题")
    b.add_argument("--seed", type=int, default=42, help="随机种子")
    b.add_argument("--work-dir", type=Path, default=None,
                   help="工作目录（默认 tmp 自动清理）")
    b.add_argument("--components", type=str, default="hsi,sparse,hsi+svs+sparse",
                   help="组件组合（逗号分隔，如 hsi,sparse,hsi+svs+sparse）")
    b.add_argument("--ksfs-dir", type=Path, default=None,
                   help="使用已有 KSFS 目录（不自动生成）")
    b.add_argument("--queries", type=Path, default=None,
                   help="使用已有 queries.json（默认自动生成）")
    b.add_argument("--top-k", type=int, default=8, help="top_k")
    b.add_argument("--save-dir", type=Path, default=None,
                   help="保存 JSON 结果与 MD 报告的目录（默认不保存）")
    b.add_argument("--silent", action="store_true", help="不打印逐 query 详情")
    b.add_argument("--track", action="store_true",
                   help="将结果归入 .benchmark_history/ 历史追踪（与 --save-dir 叠加）")

    # --- generate (仅生成) ---
    g = sub.add_parser("generate", help="仅生成测试 KSFS + queries.json，不跑基准")
    g.add_argument("--out-dir", type=Path, required=True, help="输出目录")
    g.add_argument("--characters", type=int, default=_DEFAULT_CHARS)
    g.add_argument("--locations", type=int, default=_DEFAULT_LOCS)
    g.add_argument("--items", type=int, default=_DEFAULT_ITEMS)
    g.add_argument("--theme", choices=THEMES, default="plain")
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--force", action="store_true", help="覆盖已有目录")

    # --- report (查看结果) ---
    r = sub.add_parser("report", help="查看已有基准结果 JSON")
    r.add_argument("--results", type=Path, required=True, help="结果 JSON 文件路径")
    r.add_argument("--compare", type=Path, default=None, help="对比另一个结果 JSON")

    # --- history (演进历史) ---
    h = sub.add_parser("history", help="查看 .benchmark_history/ 中所有历史基线演进")
    h.add_argument("--track-dir", type=Path, default=_HISTORY_DIR,
                   help="历史目录（默认 .benchmark_history/）")
    h.add_argument("--md", action="store_true", help="输出 Markdown 格式（默认终端文本）")

    return p


def cmd_bench(args: argparse.Namespace) -> int:
    """``bench`` 子命令。"""
    import tempfile

    # 准备 KSFS 和 queries
    if args.ksfs_dir is not None:
        ksfs_root = args.ksfs_dir.resolve()
        if not ksfs_root.is_dir():
            print(f"指定的 KSFS 目录不存在: {ksfs_root}", file=sys.stderr)
            return 1
        if args.queries is not None:
            queries_path = args.queries.resolve()
        else:
            queries_path = ksfs_root.parent / "queries.json"
            if not queries_path.is_file():
                print(f"未找到 queries.json（尝试 {queries_path}），请用 --queries 指定",
                      file=sys.stderr)
                return 1
        queries, qmap = load_queries(queries_path)
        entities = None
        print(f"使用已有 KSFS: {ksfs_root}")
        print(f"使用已有 queries: {queries_path} ({len(queries)} 条)")
    else:
        # 在临时目录生成
        if args.work_dir is not None:
            work_dir = args.work_dir.resolve()
            work_dir.mkdir(parents=True, exist_ok=True)
        else:
            work_dir = Path(tempfile.mkdtemp(prefix="logos_bench_"))
        ksfs_root = work_dir / "ksfs"
        queries_path = work_dir / "queries.json"

        print(f"生成测试 KSFS（{args.theme} 风格, seed={args.seed}）...")
        print(f"  角色 {args.characters} / 地点 {args.locations} / 物品 {args.items}")
        entities, queries = _generate_ksfs(
            ksfs_root,
            num_characters=args.characters,
            num_locations=args.locations,
            num_items=args.items,
            theme=args.theme,
            seed=args.seed,
        )
        queries_path.write_text(
            json.dumps(
                [{"id": q.id, "text": q.text, "expected_paths": q.expected_paths,
                  "type": q.type, "tags": q.tags}
                 for q in queries],
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  → 生成 {len(queries)} 条 query，已写入 {queries_path}")
        qmap = {q.id: q for q in queries}

    # 跑各组件组合
    components = [c.strip() for c in args.components.split(",")]
    print(f"\n组件组合: {components}")
    print(f"top_k = {args.top_k}")

    results: list[BenchmarkResult] = []
    for comp in components:
        print(f"\n{'─' * 50}")
        print(f"  运行: {comp}")
        print(f"{'─' * 50}")
        index_root = (ksfs_root.parent if args.work_dir else Path(tempfile.mkdtemp(prefix="logos_idx_"))) / ".index"

        # 每个组件组合用独立的 index 目录，避免缓存干扰
        if args.work_dir:
            index_root = args.work_dir / ".index" / comp.replace("+", "_")
        else:
            index_root = Path(tempfile.mkdtemp(prefix=f"logos_idx_{comp.replace('+', '_')}_")) / ".index"

        svc = make_retrieval_service(
            ksfs_root=ksfs_root,
            index_root=index_root,
            components=comp,
        )
        result = run_benchmark(svc, queries, top_k=args.top_k, label=comp)
        results.append(result)

        print(format_terminal_report(result) if not args.silent else "")
        print(f"  Recall@8: {result.recall_at(8):.3f}   MRR@8: {result.mrr_at(8):.3f}")

    # 保存
    if args.save_dir:
        save_dir = args.save_dir.resolve()
        save_dir.mkdir(parents=True, exist_ok=True)
        for result in results:
            label = result.component_label.replace("+", "_")
            save_json(result, save_dir / f"{label}.json")
            save_report_md(result, save_dir / f"{label}.md")
        print(f"\n结果已保存到: {save_dir}")

    # 对比摘要
    if len(results) >= 2:
        print(f"\n{'=' * 60}")
        print("  组件对比摘要")
        print(f"{'=' * 60}")
        print(f"  {'组件':<24} {'Recall@1':<10} {'Recall@3':<10} {'Recall@8':<10} {'MRR@8':<10}")
        print(f"  {'-'*64}")
        for r in results:
            print(f"  {r.component_label:<24} {r.recall_at(1):<10.3f} {r.recall_at(3):<10.3f}"
                  f" {r.recall_at(8):<10.3f} {r.mrr_at(8):<10.3f}")

    # 历史追踪
    if args.track:
        for r in results:
            saved = save_history(r)
            print(f"\n  [归档] {saved}")
        print("  提示: 使用 `python cli.py history` 查看演进。")

    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    """``generate`` 子命令。"""
    out_dir = args.out_dir.resolve()
    if out_dir.exists() and not args.force:
        print(f"输出目录已存在: {out_dir}（用 --force 覆盖）", file=sys.stderr)
        return 1
    ksfs_root = out_dir / "ksfs"
    queries_path = out_dir / "queries.json"

    print(f"生成测试 KSFS → {out_dir}")
    print(f"  风格: {args.theme}")
    print(f"  角色 {args.characters} / 地点 {args.locations} / 物品 {args.items}")
    entities, queries = _generate_ksfs(
        ksfs_root,
        num_characters=args.characters,
        num_locations=args.locations,
        num_items=args.items,
        theme=args.theme,
        seed=args.seed,
    )
    queries_path.write_text(
        json.dumps(
            [{"id": q.id, "text": q.text, "expected_paths": q.expected_paths,
              "type": q.type, "tags": q.tags}
             for q in queries],
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  生成 {len(queries)} 条 query")
    print(f"  KSFS: {ksfs_root}/")
    print(f"  queries: {queries_path}")
    print("完成！可继续编辑查询集，然后运行:")
    print(f"  python scripts/KSFS工具/retrieval_benchmark/cli.py bench --ksfs-dir {ksfs_root} --queries {queries_path}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """``report`` 子命令。"""
    path = args.results.resolve()
    if not path.is_file():
        print(f"结果文件不存在: {path}", file=sys.stderr)
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    label = data.get("label", path.stem)
    print(f"\n{'=' * 50}")
    print(f"  {label}")
    print(f"{'=' * 50}")
    for k in (1, 3, 5, 8):
        print(f"  Recall@{k}: {data.get(f'recall_at_{k}', 'N/A'):.3f}")
    print(f"  MRR@8:   {data.get('mrr_at_8', 'N/A'):.3f}")

    if args.compare is not None:
        cmp_path = args.compare.resolve()
        if not cmp_path.is_file():
            print(f"对比文件不存在: {cmp_path}", file=sys.stderr)
            return 1
        cmp_data = json.loads(cmp_path.read_text(encoding="utf-8"))
        cmp_label = cmp_data.get("label", cmp_path.stem)
        print(f"\n  对比: {label} vs {cmp_label}")
        for k in (1, 3, 5, 8):
            a = data.get(f"recall_at_{k}", 0)
            b = cmp_data.get(f"recall_at_{k}", 0)
            delta = a - b
            print(f"    Recall@{k}: {a:.3f} vs {b:.3f}  ({'+' if delta >= 0 else ''}{delta:.3f})")
        a = data.get("mrr_at_8", 0)
        b = cmp_data.get("mrr_at_8", 0)
        delta = a - b
        print(f"    MRR@8:   {a:.3f} vs {b:.3f}  ({'+' if delta >= 0 else ''}{delta:.3f})")

    return 0


def cmd_history(args: argparse.Namespace) -> int:
    """``history`` 子命令：展示所有历史基线演进。"""
    history = load_history_summaries(args.track_dir)
    if not history:
        print("未找到历史记录。先用 `bench --track` 跑一次基线。", file=sys.stderr)
        return 1

    if args.md:
        print(format_history_report(history))
    else:
        print(f"\n{'=' * 60}")
        print("  检索基准演进历史")
        print(f"{'=' * 60}")
        print(f"  {'时间':<18} {'组件':<20} {'R@1':<6} {'R@3':<6} {'R@5':<6} {'R@8':<6} {'MRR@8':<7}")
        print(f"  {'-'*75}")
        for entry in history:
            ts = str(entry.get("timestamp", "?"))
            comp = str(entry.get("label", entry.get("component", "?")))[:18]
            r1 = f"{entry.get('recall_at_1', 0):.3f}"
            r3 = f"{entry.get('recall_at_3', 0):.3f}"
            r5 = f"{entry.get('recall_at_5', 0):.3f}"
            r8 = f"{entry.get('recall_at_8', 0):.3f}"
            mr = f"{entry.get('mrr_at_8', 0):.3f}"
            print(f"  {ts:<18} {comp:<20} {r1:<6} {r3:<6} {r5:<6} {r8:<6} {mr:<7}")
        print("")

    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "bench":
        return cmd_bench(args)
    elif args.command == "generate":
        return cmd_generate(args)
    elif args.command == "report":
        return cmd_report(args)
    elif args.command == "history":
        return cmd_history(args)
    print(f"未知命令: {args.command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

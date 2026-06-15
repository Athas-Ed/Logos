"""生成 KSFS 测试用 Markdown：脚本骨架 + 可选 LLM 润色正文。

在仓库根目录执行（需已 ``pip install -e .`` 或 dev 依赖）::

    python scripts/KSFS工具/generate_test_ksfs.py --help
    python scripts/KSFS工具/generate_test_ksfs.py --no-polish
    python scripts/KSFS工具/generate_test_ksfs.py --polish --style wuxia

润色使用 ``config/local.yaml`` 中的 ``llm.*``（与 ``run_dev_backend`` 相同）。
生成后请自行触发 HSI/SVS 同步（例如启动后端并 ``retrieve``）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOL_DIR = Path(__file__).resolve().parent
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from logos.infrastructure.llm import build_chat_llm_from_settings
from name_pools import WorldNames, build_world_names
from logos.platform.config.loader import load_app_settings
from logos.ports.llm import ChatMessage

STYLE_PRESETS: dict[str, str] = {
    "plain": "现代写实设定集口吻：像策划案人物/地点小传，自然流畅，避免公文腔与机械罗列。",
    "wuxia": "武侠世界设定集：有江湖气，可读性好，不过分文言，少用「测试」「锚点」等元话语。",
    "sci-fi": "科幻世界观设定：后勤档案与人事叙述结合，术语克制，读起来像正式档案而非填空表。",
    "noir": "都市悬疑档案腔：偏观察、线索与氛围，句子有画面感，仍保持设定词条可读性。",
}

_SOURCE_LABEL = "ksfs-test-generator"
_BATCH_TAG = "test-fixture"
_SUBDIR = {
    "character": "characters",
    "location": "locations",
    "item": "items",
}
_WIN_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class EntitySpec:
    classification: str
    slug: str
    title: str
    tags: list[str]
    skeleton_body: str
    file_stem: str = ""
    anchors: list[str] = field(default_factory=list)

    def rel_path(self) -> str:
        stem = self.file_stem or self.slug
        return f"{_SUBDIR[self.classification]}/{stem}.md"

    def render_md(self, body: str) -> str:
        tags_yaml = ", ".join(self.tags)
        fm = (
            f"---\n"
            f"title: {self.title}\n"
            f"tags: [{tags_yaml}]\n"
            f"classification: {self.classification}\n"
            f"slug: {self.slug}\n"
            f"source_label: {_SOURCE_LABEL}\n"
            f"---\n\n"
        )
        return fm + body.strip() + "\n"


def _slug(prefix: str, index: int) -> str:
    return f"{prefix}-{index:03d}"


def _sanitize_filename_stem(title: str) -> str:
    """Windows 安全文件名（保留中文），不含扩展名。"""
    s = _WIN_FORBIDDEN.sub("", title.strip())
    s = s.rstrip(" .")
    if not s:
        s = "未命名"
    if len(s) > 180:
        s = s[:180].rstrip(" .")
    return s


def _assign_file_stems(entities: list[EntitySpec], filename_mode: str) -> None:
    used_by_sub: dict[str, set[str]] = {}
    for ent in entities:
        sub = _SUBDIR[ent.classification]
        if filename_mode == "slug":
            stem = ent.slug
        elif filename_mode == "hybrid":
            stem = f"{ent.slug}-{_sanitize_filename_stem(ent.title)}"
        else:
            stem = _sanitize_filename_stem(ent.title)
        taken = used_by_sub.setdefault(sub, set())
        base = stem
        n = 2
        while stem in taken:
            stem = f"{base}-{n}"
            n += 1
        taken.add(stem)
        ent.file_stem = stem


def _purge_entity_md(root: Path) -> int:
    """删除 characters/locations/items 下实体 .md（保留 README）。"""
    removed = 0
    for sub in _SUBDIR.values():
        d = root / sub
        if not d.is_dir():
            continue
        for p in d.glob("*.md"):
            if p.name.lower() == "readme.md":
                continue
            p.unlink()
            removed += 1
    return removed


def _char_home_index(char_index: int, num_locations: int) -> int:
    if num_locations <= 0:
        return 0
    return (char_index - 1) % num_locations


def _char_item_index(char_index: int, num_items: int) -> int:
    if num_items <= 0:
        return 0
    return (char_index - 1) % num_items


def _build_entities(
    *,
    num_characters: int,
    num_locations: int,
    num_items: int,
    world: WorldNames,
) -> list[EntitySpec]:
    nc, nl, ni = num_characters, num_locations, num_items

    char_by_loc: dict[int, list[str]] = {j: [] for j in range(nl)}
    for ci in range(1, nc + 1):
        if nl > 0:
            char_by_loc[_char_home_index(ci, nl)].append(world.characters[ci - 1])

    locations: list[EntitySpec] = []
    for i in range(1, nl + 1):
        title = world.locations[i - 1]
        slug = _slug("loc", i)
        residents = char_by_loc.get(i - 1, [])
        resident_line = "、".join(residents[:8])
        if len(residents) > 8:
            resident_line += " 等人"
        code = f"LOC-{i:03d}"
        skeleton = (
            f"## {title}\n\n"
            f"{title}是测试集「茄枝」中的一处场景设定。常驻人物包括："
            f"{resident_line or '（暂无登记角色）'}。"
            f"与周边地点、道具线索相互引用，便于检索联调。内部档案编号 {code}。\n"
        )
        anchors = [title, code]
        anchors.extend(residents[:5])
        locations.append(
            EntitySpec(
                classification="location",
                slug=slug,
                title=title,
                tags=[_BATCH_TAG, "location", f"loc-{i:03d}"],
                skeleton_body=skeleton,
                anchors=anchors,
            )
        )

    items: list[EntitySpec] = []
    for i in range(1, ni + 1):
        title = world.items[i - 1]
        slug = _slug("item", i)
        owner_idx = (i - 1) % max(nc, 1)
        loc_idx = (i - 1) % max(nl, 1)
        owner = world.characters[owner_idx] if nc > 0 else ""
        loc = world.locations[loc_idx] if nl > 0 else ""
        code = f"ITEM-{i:03d}"
        skeleton = (
            f"## {title}\n\n"
            f"道具「{title}」与{owner or '某角色'}、{loc or '某地点'}的线索相连，"
            f"在人物小传中会被再次提及。档案编号 {code}。\n"
        )
        anchors = [title, code]
        if owner:
            anchors.append(owner)
        if loc:
            anchors.append(loc)
        items.append(
            EntitySpec(
                classification="item",
                slug=slug,
                title=title,
                tags=[_BATCH_TAG, "item", f"item-{i:03d}"],
                skeleton_body=skeleton,
                anchors=anchors,
            )
        )

    characters: list[EntitySpec] = []
    for i in range(1, nc + 1):
        title = world.characters[i - 1]
        slug = _slug("char", i)
        home = world.locations[_char_home_index(i, nl)] if nl > 0 else ""
        item_title = (
            world.items[_char_item_index(i, ni)] if ni > 0 else ""
        )
        if nc > 1:
            ally_a = world.characters[i % nc]
            ally_b = world.characters[(i + 1) % nc]
        else:
            ally_a = ally_b = title
        code = f"CHAR-{i:03d}"
        parts = [
            f"## {title}\n\n",
            f"{title}",
        ]
        if home:
            parts.append(f"主要活动于{home}。")
        if item_title:
            parts.append(f"常与「{item_title}」相关。")
        if nc > 1:
            parts.append(f"与{ally_a}、{ally_b}等人物往来。")
        parts.append(f"内部档案编号 {code}。")
        skeleton = "".join(parts) + "\n"
        anchors = [title, code]
        if home:
            anchors.append(home)
        if item_title:
            anchors.append(item_title)
        if nc > 1:
            anchors.extend([ally_a, ally_b])
        characters.append(
            EntitySpec(
                classification="character",
                slug=slug,
                title=title,
                tags=[_BATCH_TAG, "character", f"char-{i:03d}"],
                skeleton_body=skeleton,
                anchors=anchors,
            )
        )

    return locations + items + characters


def _load_style_prompt(args: argparse.Namespace) -> str:
    if args.style_file:
        return Path(args.style_file).read_text(encoding="utf-8").strip()
    preset = STYLE_PRESETS.get(args.style, "")
    if not preset:
        known = ", ".join(sorted(STYLE_PRESETS))
        raise SystemExit(f"未知 --style={args.style!r}，可选: {known}")
    return preset


def _resolve_output_root(args: argparse.Namespace) -> Path:
    out = Path(args.output)
    if not out.is_absolute():
        out = (_REPO_ROOT / out).resolve()
    return out


def _existing_md_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return [p for p in root.rglob("*.md") if p.name.lower() != "readme.md"]


def _prompt_no_api_key() -> str:
    print(
        "\n警告：未配置 llm.api_key（config/local.yaml 或 LOGOS_LLM__API_KEY）。"
        "无法调用远程模型润色正文。\n"
        "  [1] 只写骨架（等同 --no-polish，继续生成）\n"
        "  [2] 暂时不做（退出）\n",
        file=sys.stderr,
    )
    while True:
        choice = input("请选择 [1/2]: ").strip()
        if choice in ("1", "2"):
            return choice
        print("请输入 1 或 2。", file=sys.stderr)


def _anchors_ok(body: str, anchors: list[str]) -> list[str]:
    missing: list[str] = []
    for a in anchors:
        token = a.strip()
        if not token or token.startswith("（"):
            continue
        if token not in body:
            missing.append(token)
    return missing


def _parse_polish_json(raw: str) -> dict[str, str]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    units = data.get("units") if isinstance(data, dict) else data
    if not isinstance(units, list):
        raise ValueError("响应缺少 units 数组")
    out: dict[str, str] = {}
    for item in units:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug", "")).strip()
        body = str(item.get("body", "")).strip()
        if slug and body:
            out[slug] = body
    return out


def _polish_batch(
    llm: Any,
    *,
    entities: list[EntitySpec],
    style_text: str,
    min_chars: int,
) -> dict[str, str]:
    payload = [
        {
            "slug": e.slug,
            "classification": e.classification,
            "title": e.title,
            "facts": e.skeleton_body,
            "required_terms": e.anchors,
        }
        for e in entities
    ]
    system = (
        "你是游戏叙事设定编辑。请把每条 facts 扩写成**自然、好读**的设定正文（Markdown），"
        "像在写设定集词条，而不是把条目原样改写成更长的列表。\n"
        f"风格：{style_text}\n"
        "写法要求：\n"
        "- 用 2～4 段叙述为主，可再加 1～2 个 ### 小节（如「概况」「关联」）；\n"
        "- 语气具体、有人味，避免「测试用」「锚点」「交织测试」等元话语；\n"
        "- 专有名词（人名、地名、道具名、档案编号）须自然嵌入句中，不要机械堆砌。\n"
        "硬性规则：\n"
        "1. 仅输出 JSON：{\"units\":[{\"slug\":\"...\",\"body\":\"...\"}, ...]}。\n"
        "2. body 以 ``## {title}`` 为一级标题（与输入 title 完全一致）。\n"
        "3. required_terms 中每一项必须在 body 里**原样出现至少一次**（一字不差）。\n"
        "4. 不得新增 required_terms 以外的人名、地名、道具名。\n"
        f"5. 每个 body 不少于 {min_chars} 个汉字（可略多）。\n"
        "6. 不要 YAML front matter。\n"
    )
    user = (
        "请润色以下实体（扩写为自然叙述），仅返回 JSON：\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    messages = [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=user),
    ]
    raw = llm.complete(messages, json_mode=True)
    return _parse_polish_json(raw)


def _write_dataset_readme(root: Path, *, counts: dict[str, int], polished: bool) -> None:
    readme = root / "README.md"
    mode = "骨架 + LLM 润色正文" if polished else "仅骨架"
    readme.write_text(
        f"---\n"
        f"title: KSFS 测试集说明\n"
        f"---\n\n"
        f"# KSFS 测试数据（`{_SOURCE_LABEL}`）\n\n"
        f"- 生成方式：{mode}\n"
        f"- 角色：{counts.get('character', 0)}，地点：{counts.get('location', 0)}，"
        f"道具：{counts.get('item', 0)}\n"
        f"- 本目录 README 不参与实体扫描。\n"
        f"- 可整目录删除后重新运行 ``scripts/KSFS工具/generate_test_ksfs.py``。\n"
        f"- 写入后请触发 ``sync_ksfs_hsi`` / ``retrieve`` 以建立索引。\n",
        encoding="utf-8",
    )


def _write_entities(
    root: Path,
    entities: list[EntitySpec],
    bodies: dict[str, str],
    *,
    warnings: list[str],
) -> int:
    written = 0
    for ent in entities:
        body = bodies.get(ent.slug, ent.skeleton_body)
        missing = _anchors_ok(body, ent.anchors)
        if missing:
            warnings.append(
                f"{ent.rel_path()}: 润色缺少锚点 {missing!r}，已回退骨架正文"
            )
            body = ent.skeleton_body
        dest = root / ent.rel_path()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(ent.render_md(body), encoding="utf-8")
        written += 1
    return written


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="生成 KSFS 测试 Markdown（骨架 + 可选 LLM 润色正文）",
    )
    p.add_argument(
        "--output",
        default="resources/ksfs/Test",
        help="输出根目录（相对仓库根），默认 resources/ksfs/Test",
    )
    p.add_argument("--characters", type=int, default=20, metavar="N")
    p.add_argument("--locations", type=int, default=20, metavar="N")
    p.add_argument("--items", type=int, default=20, metavar="N")
    polish = p.add_mutually_exclusive_group()
    polish.add_argument(
        "--polish",
        action="store_true",
        help="调用 LLM 润色正文（需 api_key）",
    )
    polish.add_argument(
        "--no-polish",
        action="store_true",
        help="仅写骨架（默认）",
    )
    p.add_argument(
        "--style",
        default="plain",
        choices=sorted(STYLE_PRESETS),
        help="润色风格预设",
    )
    p.add_argument(
        "--name-theme",
        default=None,
        choices=["plain", "wuxia", "sci-fi", "noir"],
        help="专名池主题（默认与 --style 相同）",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="专名组合随机种子（同参数可复现）",
    )
    p.add_argument(
        "--style-file",
        type=Path,
        default=None,
        help="自定义风格说明（Markdown/纯文本），覆盖 --style",
    )
    p.add_argument("--batch-size", type=int, default=10, help="润色批大小")
    p.add_argument("--sleep-ms", type=int, default=500, help="批间休眠毫秒")
    p.add_argument("--min-body-chars", type=int, default=200, help="润色正文最少字符")
    p.add_argument("--force", action="store_true", help="覆盖已有 .md 实体文件")
    p.add_argument(
        "--filename-mode",
        default="title",
        choices=["title", "slug", "hybrid"],
        help="文件名：title=纯中文标题（默认），slug=char-001，hybrid=前缀+标题",
    )
    p.add_argument(
        "--config-dir",
        type=Path,
        default=None,
        help="配置目录（含 defaults.yaml / local.yaml）",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for name, val in (
        ("characters", args.characters),
        ("locations", args.locations),
        ("items", args.items),
    ):
        if val < 0:
            raise SystemExit(f"--{name} 不能为负数")

    want_polish = bool(args.polish)
    if not args.polish and not args.no_polish:
        want_polish = False

    root = _resolve_output_root(args)
    settings = load_app_settings(args.config_dir)
    ksfs_root = Path(settings.ksfs_root)
    if not ksfs_root.is_absolute():
        ksfs_root = (_REPO_ROOT / ksfs_root).resolve()
    try:
        root.relative_to(ksfs_root)
    except ValueError:
        print(
            f"警告：--output={root} 不在 paths.ksfs_root={ksfs_root} 之下，"
            "检索/sync 可能扫不到这些文件。",
            file=sys.stderr,
        )

    existing = _existing_md_files(root)
    if existing and not args.force:
        print(
            f"拒绝写入：{root} 下已有 {len(existing)} 个实体 .md。"
            "使用 --force 覆盖。",
            file=sys.stderr,
        )
        return 2
    if existing and args.force:
        n_removed = _purge_entity_md(root)
        if n_removed:
            print(f"已清理旧实体文件 {n_removed} 个。", file=sys.stderr)

    name_theme = args.name_theme or args.style
    world = build_world_names(
        theme=name_theme,
        num_characters=args.characters,
        num_locations=args.locations,
        num_items=args.items,
        seed=args.seed,
    )
    entities = _build_entities(
        num_characters=args.characters,
        num_locations=args.locations,
        num_items=args.items,
        world=world,
    )
    if not entities:
        print("未生成任何实体（数量均为 0）。", file=sys.stderr)
        return 1

    _assign_file_stems(entities, args.filename_mode)

    llm = None
    if want_polish:
        llm = build_chat_llm_from_settings(settings)
        if llm is None:
            choice = _prompt_no_api_key()
            if choice == "2":
                return 0
            want_polish = False

    bodies: dict[str, str] = {e.slug: e.skeleton_body for e in entities}
    warnings: list[str] = []

    if want_polish and llm is not None:
        style_text = _load_style_prompt(args)
        batch_size = max(1, args.batch_size)
        batches = [
            entities[i : i + batch_size] for i in range(0, len(entities), batch_size)
        ]
        for idx, batch in enumerate(batches, start=1):
            print(
                f"润色批次 {idx}/{len(batches)}（{len(batch)} 个实体）…",
                file=sys.stderr,
            )
            try:
                got = _polish_batch(
                    llm,
                    entities=batch,
                    style_text=style_text,
                    min_chars=args.min_body_chars,
                )
            except Exception as exc:
                warnings.append(f"批次 {idx} 失败: {exc!r}，该批回退骨架")
                continue
            for ent in batch:
                if ent.slug in got:
                    bodies[ent.slug] = got[ent.slug]
                else:
                    warnings.append(f"{ent.slug}: 响应缺少条目，保留骨架")
            if args.sleep_ms > 0 and idx < len(batches):
                time.sleep(args.sleep_ms / 1000.0)

    counts = {
        "character": args.characters,
        "location": args.locations,
        "item": args.items,
    }
    _write_dataset_readme(root, counts=counts, polished=want_polish)
    n = _write_entities(root, entities, bodies, warnings=warnings)

    print(f"已写入 {n} 个实体 → {root}")
    print(f"专名主题：{name_theme}（seed={args.seed}）")
    print(f"文件名模式：{args.filename_mode}")
    if want_polish:
        print("模式：骨架 + LLM 润色")
    else:
        print("模式：仅骨架（专名已为正常中文，可直接用于检索联调）")
    if warnings:
        print("警告：", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
    print(
        "下一步：启动后端并对 KSFS 执行 retrieve，或运行 HSI 同步以建立索引。",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

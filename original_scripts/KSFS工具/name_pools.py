"""测试集专用名：按主题组合姓/名、地名、道具名，避免「测试角色-01」式占位。"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorldNames:
    characters: list[str]
    locations: list[str]
    items: list[str]


_THEMES = ("plain", "wuxia", "sci-fi", "noir")


def _pick(pool: list[str], index: int, *, salt: int = 0) -> str:
    return pool[(index + salt) % len(pool)]


def _unique_fill(
    maker: object,
    count: int,
    *,
    seed: int,
    max_tries: int = 10000,
) -> list[str]:
    if count <= 0:
        return []
    rng = random.Random(seed)
    seen: set[str] = set()
    out: list[str] = []
    i = 0
    tries = 0
    while len(out) < count and tries < max_tries:
        name = maker(i, rng)  # type: ignore[operator]
        tries += 1
        i += 1
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    while len(out) < count:
        out.append(f"{maker(len(out), rng)}·{len(out) + 1}")  # type: ignore[operator]
    return out


def build_world_names(
    *,
    theme: str,
    num_characters: int,
    num_locations: int,
    num_items: int,
    seed: int = 42,
) -> WorldNames:
    """按主题与数量生成互不重复的中文专名列表。"""
    t = theme if theme in _THEMES else "plain"
    if t == "wuxia":
        return _world_wuxia(
            num_characters=num_characters,
            num_locations=num_locations,
            num_items=num_items,
            seed=seed,
        )
    if t == "sci-fi":
        return _world_sci_fi(
            num_characters=num_characters,
            num_locations=num_locations,
            num_items=num_items,
            seed=seed,
        )
    if t == "noir":
        return _world_noir(
            num_characters=num_characters,
            num_locations=num_locations,
            num_items=num_items,
            seed=seed,
        )
    return _world_plain(
        num_characters=num_characters,
        num_locations=num_locations,
        num_items=num_items,
        seed=seed,
    )


def _world_plain(*, num_characters: int, num_locations: int, num_items: int, seed: int) -> WorldNames:
    surnames = "林赵沈顾周陆唐韩宋白程".split()
    given = (
        "婉清 暮寒 承安 听雨 子衿 景和 思远 若兰 怀瑾 乐言 "
        "知微 映雪 修齐 明远 清和 予安 嘉木 云舒 望舒 北辰"
    ).split()

    def char(i: int, rng: random.Random) -> str:
        a = _pick(surnames, i, salt=rng.randint(0, 7))
        b = _pick(given, i // len(surnames), salt=rng.randint(0, 11))
        return f"{a}{b}"

    loc_adj = "青阳 临江 云梦 栖霞 白鹿 长汀 桃溪 北辰 南浦 西岭".split()
    loc_noun = "镇 城 港 谷 驿 坊 书院 哨站 庄园 集市".split()

    def loc(i: int, rng: random.Random) -> str:
        return f"{_pick(loc_adj, i, salt=rng.randint(0, 3))}{_pick(loc_noun, i // 3, salt=1)}"

    item_adj = "寒铁 旧铜 秘银 松纹 鲸脂 砂金 琉璃 竹编 鹿皮 炭墨".split()
    item_noun = "短剑 长刀 信物 地图 药匣 灯笼 罗盘 印章 护符 名册".split()

    def item(i: int, rng: random.Random) -> str:
        return f"{_pick(item_adj, i, salt=rng.randint(0, 5))}{_pick(item_noun, i // 2)}"

    return WorldNames(
        characters=_unique_fill(char, num_characters, seed=seed),
        locations=_unique_fill(loc, num_locations, seed=seed + 1),
        items=_unique_fill(item, num_items, seed=seed + 2),
    )


def _world_wuxia(*, num_characters: int, num_locations: int, num_items: int, seed: int) -> WorldNames:
    surnames = [
        "令狐",
        "萧",
        "慕容",
        "上官",
        "欧阳",
        "司徒",
        "诸葛",
        "东方",
        "独孤",
        "叶",
        "沈",
        "陆",
    ]
    given = (
        "惊鸿 断水 听雪 逐风 藏锋 挽弓 照夜 行歌 无尘 归舟 "
        "青萝 寒烟 落雁 乘云 问剑 栖梧 枕石 漱玉 凌霄 照影"
    ).split()

    def char(i: int, rng: random.Random) -> str:
        return f"{_pick(surnames, i, salt=rng.randint(0, 5))}{_pick(given, i, salt=rng.randint(0, 9))}"

    loc_a = "青城 峨眉 昆仑 武当 华山 嵩山 终南 雁荡 点苍 怒海".split()
    loc_b = "峰 崖 谷 观 寺 镖局 剑庐 茶棚 渡口 旧寨".split()

    def loc(i: int, rng: random.Random) -> str:
        return f"{_pick(loc_a, i)}{_pick(loc_b, i // 2, salt=rng.randint(0, 4))}"

    item_a = "秋水 断魂 惊鸿 落霞 听风 无名 寒月 流云 赤霄 青冥".split()
    item_b = "剑 刀 扇 针 箫 甲 囊 谱 令 绳".split()

    def item(i: int, rng: random.Random) -> str:
        return f"{_pick(item_a, i)}{_pick(item_b, i // 3)}"

    return WorldNames(
        characters=_unique_fill(char, num_characters, seed=seed),
        locations=_unique_fill(loc, num_locations, seed=seed + 1),
        items=_unique_fill(item, num_items, seed=seed + 2),
    )


def _world_sci_fi(*, num_characters: int, num_locations: int, num_items: int, seed: int) -> WorldNames:
    family = list("陈林周吴郑王冯褚卫蒋沈韩杨朱秦尤许何吕施张")
    given = (
        "拓 宁 澜 澈 屿 晗 栎 珩 芮 淳 骁 昀 珂 晟 遥 "
        "珞 宸 简 攸 黎 珂 朔 湛 屿 笙"
    ).split()

    def char(i: int, rng: random.Random) -> str:
        return f"{_pick(family, i)}{_pick(given, i // 2, salt=rng.randint(0, 9))}"

    loc_p = "轨道 环带 中继 殖民 深空 近地 气闸 引力 同步 废弃".split()
    loc_s = "站 港 舱 走廊 矿区 观测台 物流枢 避难层 试验环 码头".split()

    def loc(i: int, rng: random.Random) -> str:
        return f"{_pick(loc_p, i)}{_pick(loc_s, i // 2, salt=1)}"

    item_p = "便携 军用 民用 实验 封存 冗余 量子 离子 纳米 全息".split()
    item_s = "终端 密钥 滤芯 面罩 推进包 导航核 样本匣 信标 扳手 档案条".split()

    def item(i: int, rng: random.Random) -> str:
        return f"{_pick(item_p, i, salt=2)}{_pick(item_s, i // 2)}"

    return WorldNames(
        characters=_unique_fill(char, num_characters, seed=seed),
        locations=_unique_fill(loc, num_locations, seed=seed + 1),
        items=_unique_fill(item, num_items, seed=seed + 2),
    )


def _world_noir(*, num_characters: int, num_locations: int, num_items: int, seed: int) -> WorldNames:
    surnames = "陆沈许唐顾钟梁宋韩白程".split()
    given = (
        "沉舟 望野 听潮 照棠 归晚 知秋 闻笛 枕河 行简 未晞 "
        "疏桐 明澈 晚照 栖迟 亦安 闻笙 清越 予怀 北辰 映川"
    ).split()

    def char(i: int, rng: random.Random) -> str:
        return f"{_pick(surnames, i)}{_pick(given, i, salt=rng.randint(0, 6))}"

    loc_a = "雨巷 旧码头 城北 河滨 钟楼 纸厂 旅馆 酒吧 档案 电厂".split()
    loc_b = "街 分局 仓库 阁楼 站台 后院 暗室 天台 岔口 诊所".split()

    def loc(i: int, rng: random.Random) -> str:
        return f"{_pick(loc_a, i)}{_pick(loc_b, i // 2)}"

    item_a = "褪色 潮湿 匿名 破损 镀铬 静音 备用 加密 夜光 空白".split()
    item_b = "照片 录音带 钥匙 信封 打火机 账本 车票 怀表 名片 胶卷".split()

    def item(i: int, rng: random.Random) -> str:
        return f"{_pick(item_a, i)}{_pick(item_b, i // 3, salt=1)}"

    return WorldNames(
        characters=_unique_fill(char, num_characters, seed=seed),
        locations=_unique_fill(loc, num_locations, seed=seed + 1),
        items=_unique_fill(item, num_items, seed=seed + 2),
    )

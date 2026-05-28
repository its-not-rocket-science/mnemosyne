#!/usr/bin/env python3
"""
harvest_language_data.py — CEFR vocabulary and grammar harvester for Mnemosyne.

Vocabulary sources (all free / open-licence):
  FrequencyWords  github.com/hermitdave/FrequencyWords  CC BY-SA 3.0
                  OpenSubtitles-derived frequency lists per language.
                  CEFR band assigned by frequency rank.
  JLPT            Community N5-N1 word lists (ja); mapped A1-C1.
  HSK             Official HSK 1-6 lists (zh); mapped A1-C2.
  Wiktionary API  Definitions for harvested headwords (rate-limited).

Grammar sources:
  Curated rules authored from CEFR framework descriptors and standard
  language-teaching references.  One rule = one teachable grammar point.

CEFR bands by frequency rank (approximation based on Nation 2001 / Schmitt 2000):
  A1 : rank   1– 500   (core everyday vocabulary)
  A2 : rank 501–1 500
  B1 : rank 1501–3 500
  B2 : rank 3501–7 500
  C1 : rank 7501–12 000
  C2 : rank 12 001+    (stored only up to 15 000 to keep data manageable)

Usage:
  python scripts/harvest_language_data.py
  python scripts/harvest_language_data.py --languages es fr de ja
  python scripts/harvest_language_data.py --levels A1 A2 B1
  python scripts/harvest_language_data.py --skip-vocab       # grammar rules only
  python scripts/harvest_language_data.py --skip-grammar     # vocabulary only
  python scripts/harvest_language_data.py --skip-definitions # no Wiktionary calls
  python scripts/harvest_language_data.py --dry-run          # print counts, no writes

Requires:
  pip install httpx asyncpg sqlalchemy[asyncio] tqdm
  DATABASE_URL env var (postgresql+asyncpg://...)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Iterator

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("harvest")

# ── Constants ────────────────────────────────────────────────────────────────

SOURCE_VOCAB    = "FrequencyWords/OpenSubtitles"
SOURCE_JLPT     = "JLPT Community Lists"
SOURCE_HSK      = "HSK Official Lists"
SOURCE_GRAMMAR  = "CEFR Framework / Curated"
SOURCE_CURATED  = "Plugin Curated / Manual"

# FrequencyWords language codes → Mnemosyne BCP-47 codes
# github.com/hermitdave/FrequencyWords/tree/master/content/2018
_FW_LANG_MAP: dict[str, str] = {
    "es": "es",
    "fr": "fr",
    "de": "de",
    "it": "it",
    "pt": "pt",
    "ru": "ru",
    "ar": "ar",
    "he": "he",
    "hi": "hi",   # Hindi — FrequencyWords OpenSubtitles 2018
    "tr": "tr",   # Turkish — FrequencyWords OpenSubtitles 2018
    "fi": "fi",   # Finnish — FrequencyWords OpenSubtitles 2018
    # ja and zh use specialised sources below
}

_FREQ_URL = (
    "https://raw.githubusercontent.com/hermitdave/FrequencyWords"
    "/master/content/2018/{fw_lang}/{fw_lang}_50k.txt"
)

# CEFR rank thresholds (upper bound, inclusive)
_CEFR_THRESHOLDS: list[tuple[int, str]] = [
    (500,   "A1"),
    (1500,  "A2"),
    (3500,  "B1"),
    (7500,  "B2"),
    (12000, "C1"),
    (15000, "C2"),  # harvest up to 15k; above that stop
]

_WIKTIONARY_API = "https://en.wiktionary.org/w/api.php"
_WIKT_RATE_S    = 0.3   # seconds between Wiktionary calls

# ── CEFR band helper ─────────────────────────────────────────────────────────

def cefr_for_rank(rank: int) -> str | None:
    for limit, level in _CEFR_THRESHOLDS:
        if rank <= limit:
            return level
    return None   # above harvest ceiling

# ── Wiktionary definitions ────────────────────────────────────────────────────

async def fetch_definition(client: httpx.AsyncClient, word: str, lang_code: str) -> str | None:
    """Return a short definition from the English Wiktionary for *word*.

    Uses the Wiktionary extract API which returns a plain-text summary.
    Returns None on any error so failures are non-fatal.
    """
    try:
        resp = await client.get(
            _WIKTIONARY_API,
            params={
                "action": "query",
                "prop":   "extracts",
                "exintro": "1",
                "explaintext": "1",
                "exsentences": "2",
                "titles": word,
                "format": "json",
                "redirects": "1",
            },
            timeout=8.0,
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            extract = page.get("extract", "").strip()
            if extract and not extract.startswith("=="):
                # Trim to first sentence
                first = extract.split("\n")[0][:300]
                if first:
                    return first
    except Exception:
        pass
    await asyncio.sleep(_WIKT_RATE_S)
    return None

# ── Frequency-list harvester (FrequencyWords) ─────────────────────────────────

async def fetch_freq_list(client: httpx.AsyncClient, fw_lang: str) -> list[tuple[int, str]]:
    """Download a FrequencyWords 50k list and return [(rank, word), ...]."""
    url = _FREQ_URL.format(fw_lang=fw_lang)
    log.info("  downloading %s", url)
    try:
        resp = await client.get(url, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("  ✗ failed to fetch %s: %s", url, exc)
        return []

    results: list[tuple[int, str]] = []
    for rank, line in enumerate(resp.text.splitlines(), start=1):
        parts = line.strip().split()
        if not parts:
            continue
        word = parts[0].lower()
        # Skip purely numeric tokens and very short strings
        if word.isdigit() or len(word) < 2:
            continue
        results.append((rank, word))
        if rank >= 15000:
            break
    return results

# ── JLPT inline data (Japanese) ──────────────────────────────────────────────
# N5 ≈ A1, N4 ≈ A2, N3 ≈ B1, N2 ≈ B2, N1 ≈ C1
# Condensed representative lists; the full N1-N5 lists contain ~10 000 entries.
# Source: jlpt.jp official vocabulary criteria + JLPT Study community lists.

_JLPT: dict[str, list[str]] = {
    "A1": [  # N5
        "私", "あなた", "彼", "彼女", "私たち", "これ", "それ", "あれ",
        "何", "誰", "どこ", "いつ", "どれ", "どの",
        "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "百", "千",
        "今日", "明日", "昨日", "今", "毎日", "何時", "何分",
        "行く", "来る", "食べる", "飲む", "見る", "聞く", "読む", "書く",
        "話す", "する", "ある", "いる", "思う", "言う", "分かる", "知る",
        "起きる", "寝る", "買う", "売る", "開ける", "閉める", "入る", "出る",
        "大きい", "小さい", "新しい", "古い", "高い", "安い", "長い", "短い",
        "良い", "悪い", "暑い", "寒い", "白い", "黒い", "赤い", "青い",
        "家", "学校", "会社", "駅", "空港", "病院", "銀行", "郵便局",
        "部屋", "ドア", "窓", "椅子", "机", "本", "新聞", "雑誌",
        "水", "お茶", "コーヒー", "牛乳", "ジュース", "ご飯", "パン", "肉", "魚",
        "電車", "バス", "タクシー", "自動車", "自転車",
        "お父さん", "お母さん", "兄", "姉", "弟", "妹", "友達", "先生",
        "円", "時間", "分", "秒", "年", "月", "週", "日",
        "春", "夏", "秋", "冬", "天気", "雨", "雪", "晴れ",
        "名前", "住所", "電話番号", "言語", "日本語", "英語",
        "ありがとう", "すみません", "はい", "いいえ",
    ],
    "A2": [  # N4
        "会う", "遊ぶ", "泳ぐ", "歌う", "教える", "覚える", "送る",
        "借りる", "貸す", "変える", "続ける", "決める", "始める", "終わる",
        "手伝う", "使う", "呼ぶ", "渡す", "走る", "止まる", "動く",
        "準備する", "練習する", "勉強する", "仕事する", "卒業する",
        "普通", "特別", "大切", "必要", "便利", "親切", "丁寧",
        "自分", "他人", "みんな", "お互い",
        "気持ち", "心", "考え", "意見", "理由", "方法", "問題",
        "生活", "生徒", "社員", "部長", "店員",
        "建物", "階段", "エレベーター", "廊下",
        "朝", "昼", "夜", "午前", "午後", "夕方",
        "地図", "道", "橋", "山", "川", "海", "池",
        "映画", "音楽", "スポーツ", "旅行", "趣味",
        "お金", "値段", "予算",
        "色", "形", "大きさ", "重さ",
    ],
    "B1": [  # N3
        "確認する", "説明する", "比較する", "判断する", "調べる",
        "申し込む", "参加する", "提出する", "連絡する", "報告する",
        "困る", "迷う", "驚く", "喜ぶ", "悲しむ", "怒る", "心配する",
        "相談する", "頼む", "断る", "約束する",
        "計画", "目標", "結果", "原因", "影響", "効果",
        "環境", "社会", "文化", "歴史", "政治", "経済",
        "技術", "情報", "インターネット", "データ",
        "制度", "規則", "法律", "権利", "義務",
        "健康", "病気", "症状", "治療", "薬",
        "体験", "経験", "知識", "能力", "技能",
        "関係", "立場", "役割", "責任",
    ],
    "B2": [  # N2
        "主張する", "批判する", "評価する", "分析する", "検討する",
        "実現する", "達成する", "解決する", "改善する", "維持する",
        "発展", "変化", "状況", "傾向", "課題", "対策",
        "議論", "討論", "合意", "妥協", "交渉",
        "貢献", "協力", "支援", "援助", "協調",
        "根拠", "証拠", "論理", "前提", "結論",
        "感情", "態度", "姿勢", "観点", "視点",
        "複雑", "詳細", "具体的", "抽象的", "典型的",
    ],
    "C1": [  # N1
        "概念", "理論", "仮説", "検証", "実証",
        "体系", "構造", "メカニズム", "プロセス",
        "矛盾", "逆説", "曖昧", "微妙", "繊細",
        "本質", "特性", "属性", "要素", "側面",
        "促進", "抑制", "阻害", "刺激", "誘発",
        "統合", "分化", "調和", "均衡", "安定",
        "批評", "解釈", "翻訳", "変換", "変革",
        "膨大", "深刻", "顕著", "漠然", "明確",
    ],
}

# ── HSK inline data (Chinese) ─────────────────────────────────────────────────
# HSK1≈A1, HSK2≈A2, HSK3≈B1, HSK4≈B2, HSK5≈C1, HSK6≈C2
# Source: Hanban/CLTC official HSK vocabulary standards.

_HSK: dict[str, list[str]] = {
    "A1": [  # HSK 1 (150 words)
        "爱", "八", "爸爸", "杯子", "北京", "本", "不", "不客气", "菜", "茶",
        "吃", "出租车", "打电话", "大", "的", "点", "电脑", "电视", "电影",
        "东西", "都", "读", "对不起", "多", "多少", "儿子", "二", "饭店",
        "飞机", "分钟", "高兴", "个", "工作", "狗", "汉语", "好", "号",
        "喝", "和", "很", "后面", "回", "会", "几", "家", "叫", "今天",
        "九", "开", "看", "看见", "块", "来", "老师", "了", "冷", "里",
        "两", "零", "六", "妈妈", "吗", "买", "猫", "么", "没", "没有",
        "们", "米饭", "明天", "名字", "哪", "哪儿", "那", "呢", "你",
        "年", "女儿", "朋友", "漂亮", "苹果", "七", "钱", "前面", "请",
        "去", "热", "人", "认识", "日", "三", "商店", "上", "上午",
        "少", "谁", "什么", "十", "时候", "是", "书", "水", "水果",
        "睡觉", "说", "四", "岁", "他", "她", "太", "天气", "听",
        "同学", "五", "我", "我的", "我们", "喜欢", "下", "下午",
        "下雨", "先生", "现在", "想", "小", "小姐", "写", "谢谢",
        "星期", "学生", "学习", "学校", "一", "衣服", "医生", "医院",
        "椅子", "有", "月", "再见", "在", "桌子", "怎么", "怎么样",
        "这", "中国", "中午", "住",
    ],
    "A2": [  # HSK 2 (150 words)
        "吧", "白", "百", "帮助", "报纸", "比", "别", "宾馆", "长", "唱歌",
        "出", "穿", "从", "错", "打篮球", "大家", "到", "得", "等", "弟弟",
        "第一", "懂", "对", "房间", "非常", "服务员", "高", "告诉", "哥哥",
        "给", "公共汽车", "公司", "贵", "过", "还", "黑", "红", "后来",
        "花", "画", "欢迎", "还是", "回答", "机场", "鸡蛋", "件", "教室",
        "姐姐", "介绍", "进", "近", "觉得", "开始", "考试", "可以",
        "口", "块", "快", "快乐", "离", "脸", "练习", "两", "了解",
        "路", "卖", "忙", "每", "妹妹", "门", "面条", "男", "您",
        "努力", "跑步", "便宜", "篮球", "去年", "让", "日记", "如果",
        "色", "身体", "生病", "生日", "时间", "事情", "手机", "说话",
        "送", "所以", "他们", "踢足球", "题", "跳舞", "题目", "外",
        "完", "晚上", "问", "问题", "笑", "新", "姓", "休息", "找",
        "着", "正在", "知道", "准备", "走", "最", "坐", "左边", "右边",
    ],
    "B1": [  # HSK 3 (~300 words, representative sample)
        "阿姨", "啊", "把", "班", "搬", "板", "办法", "办公室", "半", "帮",
        "被", "鼻子", "比较", "必须", "变化", "表示", "表演", "别人",
        "冰箱", "不但", "不过", "菜单", "参加", "层", "差", "超市",
        "成绩", "城市", "迟到", "除了", "春", "词语", "打扫", "打算",
        "带", "担心", "蛋糕", "当", "当然", "地方", "地图", "第", "典型",
        "掉", "动物", "端", "段", "饿", "发", "发现", "方便", "方向",
        "放", "放弃", "风", "符合", "附近", "复习", "刚才", "根据",
        "跟", "鼓励", "故事", "关", "关系", "管", "广场", "国家",
        "过去", "还是", "寒假", "河", "黑板", "护照", "花园", "欢迎",
        "环境", "会议", "活动", "活泼", "火车", "机会", "基本", "极",
        "季节", "加", "检查", "简单", "健康", "见面", "将来", "解决",
        "结束", "经常", "经过", "经历", "经验", "决定",
    ],
    "B2": [  # HSK 4 (~600 words, representative sample)
        "安慰", "暗", "把握", "摆", "包含", "保护", "保证", "表达", "不仅",
        "才能", "参考", "曾经", "成功", "成立", "程度", "充分", "出发",
        "传统", "打折", "大概", "代替", "当地", "到达", "道路", "得到",
        "等待", "调整", "顶", "动作", "独特", "对于", "发展", "繁荣",
        "方式", "分析", "否则", "干燥", "感动", "感激", "高度", "各",
        "工程师", "工资", "功能", "共同", "古代", "固定", "关注",
        "规律", "过程", "合理", "积极", "即使", "记忆", "技术", "继续",
        "建立", "教育", "接受", "结合", "解释", "进行", "精神",
        "竞争", "具体", "距离", "科学", "可能", "可惜", "克服",
        "来源", "理解", "联系", "流行", "逻辑", "目的", "目标",
        "内容", "能够", "努力", "判断", "普通", "其中", "情况",
        "认为", "任何", "任务", "社会", "设计", "生产", "实际",
        "使用", "事实", "适合", "收入", "受到", "水平", "顺利",
        "速度", "所以", "态度", "讨论", "特点", "提高", "体现",
        "条件", "通过", "推动", "完成", "未来", "文化", "问题",
        "相对", "效果", "选择", "研究", "已经", "以及", "影响",
        "优秀", "原来", "运动", "增加", "掌握", "政府", "支持",
        "主要", "注意", "资源", "自然",
    ],
    "C1": [  # HSK 5 (~1300 words, representative sample)
        "案例", "暴力", "本质", "比喻", "辩论", "标准", "补充", "财富",
        "策略", "产业", "超越", "成本", "承担", "承认", "冲突", "出现",
        "处理", "创新", "促进", "存在", "大量", "单独", "当局", "导致",
        "得出", "等等", "调查", "定义", "发挥", "法律", "反映", "繁荣",
        "方针", "复杂", "改革", "概念", "高效", "个人", "工业", "构成",
        "估计", "观念", "规模", "含义", "核心", "宏观", "假设", "检验",
        "角色", "结构", "仅仅", "经济", "竟然", "开发", "客观", "快速",
        "来得及", "理论", "利益", "立即", "利用", "临时", "灵活",
        "逻辑", "满足", "贸易", "明显", "模式", "目前", "内部",
        "能力", "平衡", "批评", "前提", "确保", "确认", "全面",
        "缺乏", "热门", "人才", "认识", "认知", "社区", "深入",
        "生态", "实施", "思想", "探索", "提倡", "体系", "调节",
        "通常", "突破", "推广", "外部", "完善", "稳定", "系统",
        "现象", "相关", "协调", "效率", "需求", "循环", "严格",
        "研发", "优化", "整合", "政策", "制度", "指标", "中心",
        "重要", "转变", "资金", "综合", "作用",
    ],
    "C2": [  # HSK 6 (~5000 words, representative sample)
        "辩证", "波动", "参照", "层次", "阐述", "超前", "抽象", "创举",
        "从属", "萃取", "错综", "大纲", "代价", "胆识", "当务之急",
        "道德观", "独到", "发人深省", "范畴", "反思", "纷繁", "丰碑",
        "负面", "赋予", "概括", "感召力", "高度凝练", "格局", "根基",
        "共识", "固有", "管辖", "过渡", "宏大", "宏观调控", "汇聚",
        "激发", "积淀", "极致", "剖析", "客观规律", "来龙去脉",
        "冷静客观", "理念", "历程", "辩论赛", "磨砺", "内涵", "凝聚",
        "批判性", "前瞻性", "深远", "审视", "升华", "实事求是",
        "视角", "梳理", "素质", "探讨", "提炼", "完整性", "完型",
        "未雨绸缪", "问题意识", "无可厚非", "稀缺", "系统性",
        "显著", "心理素质", "信念", "需要协调", "循序渐进",
        "演变", "意识形态", "因势利导", "影响深远", "与时俱进",
        "整体", "政治敏感", "重塑", "主观能动", "逐步完善",
    ],
}

# ── Latin inline vocabulary ───────────────────────────────────────────────────
# Curated from Wheelock's Latin, LLPSI, and DCC Core Latin Vocabulary (top 1000).
# Headwords in normalised form (no macrons) for DB consistency.

_LATIN_VOCAB: dict[str, list[tuple[str, str, str]]] = {
    # (lemma, pos, gloss)
    "A1": [
        ("sum",      "verb",  "to be, exist"),
        ("et",       "conj",  "and, also, even"),
        ("in",       "prep",  "in, on, into, against"),
        ("est",      "verb",  "is (3sg of esse)"),
        ("non",      "adv",   "not"),
        ("ad",       "prep",  "to, toward, near"),
        ("de",       "prep",  "from, down from, about"),
        ("qui",      "pron",  "who, which, that"),
        ("cum",      "prep",  "with, when, since"),
        ("sed",      "conj",  "but"),
        ("aut",      "conj",  "or (exclusive)"),
        ("ex",       "prep",  "out of, from"),
        ("ab",       "prep",  "from, away from, by"),
        ("si",       "conj",  "if"),
        ("ut",       "conj",  "that, so that, as"),
        ("per",      "prep",  "through, by means of"),
        ("hic",      "pron",  "this, these (near speaker)"),
        ("ille",     "pron",  "that, those (remote)"),
        ("ego",      "pron",  "I"),
        ("tu",       "pron",  "you (singular)"),
        ("nos",      "pron",  "we, us"),
        ("vos",      "pron",  "you (plural)"),
        ("is",       "pron",  "he, she, it, they"),
        ("res",      "noun",  "thing, matter, affair"),
        ("homo",     "noun",  "human being, person"),
        ("deus",     "noun",  "god, deity"),
        ("via",      "noun",  "road, way, street"),
        ("terra",    "noun",  "earth, land, ground"),
        ("aqua",     "noun",  "water"),
        ("vita",     "noun",  "life"),
        ("pater",    "noun",  "father"),
        ("mater",    "noun",  "mother"),
        ("filius",   "noun",  "son"),
        ("puella",   "noun",  "girl"),
        ("puer",     "noun",  "boy, child"),
        ("vir",      "noun",  "man, hero"),
        ("femina",   "noun",  "woman"),
        ("rex",      "noun",  "king"),
        ("urbs",     "noun",  "city"),
        ("amor",     "noun",  "love"),
        ("amo",      "verb",  "to love"),
        ("do",       "verb",  "to give"),
        ("dico",     "verb",  "to say, speak"),
        ("facio",    "verb",  "to make, do"),
        ("video",    "verb",  "to see"),
        ("venio",    "verb",  "to come"),
        ("eo",       "verb",  "to go"),
        ("habeo",    "verb",  "to have, hold"),
        ("possum",   "verb",  "to be able, can"),
        ("magnus",   "adj",   "great, large, big"),
        ("bonus",    "adj",   "good"),
        ("malus",    "adj",   "bad, evil"),
        ("novus",    "adj",   "new"),
        ("multus",   "adj",   "much, many"),
        ("omnis",    "adj",   "all, every"),
        ("unus",     "adj",   "one"),
        ("duo",      "adj",   "two"),
        ("tres",     "adj",   "three"),
    ],
    "A2": [
        ("dico",     "verb",  "to say, speak, tell"),
        ("scribo",   "verb",  "to write"),
        ("lego",     "verb",  "to read, choose, gather"),
        ("audio",    "verb",  "to hear, listen"),
        ("pono",     "verb",  "to put, place, set"),
        ("porto",    "verb",  "to carry"),
        ("laudo",    "verb",  "to praise"),
        ("voco",     "verb",  "to call, summon"),
        ("mitto",    "verb",  "to send"),
        ("capio",    "verb",  "to take, seize, capture"),
        ("regio",    "noun",  "region, territory, district"),
        ("corpus",   "noun",  "body"),
        ("mens",     "noun",  "mind, intention"),
        ("mors",     "noun",  "death"),
        ("pax",      "noun",  "peace"),
        ("bellum",   "noun",  "war"),
        ("tempus",   "noun",  "time, season"),
        ("locus",    "noun",  "place, position, passage"),
        ("populus",  "noun",  "people, nation"),
        ("dominus",  "noun",  "lord, master, owner"),
        ("miles",    "noun",  "soldier"),
        ("civis",    "noun",  "citizen"),
        ("lex",      "noun",  "law, rule"),
        ("gloria",   "noun",  "glory, fame, honour"),
        ("fortuna",  "noun",  "fortune, luck, fate"),
        ("animus",   "noun",  "spirit, soul, courage, mind"),
        ("nomen",    "noun",  "name"),
        ("verbum",   "noun",  "word"),
        ("liber",    "noun",  "book"),
        ("magnus",   "adj",   "great, large"),
        ("parvus",   "adj",   "small, little"),
        ("longus",   "adj",   "long"),
        ("antiquus", "adj",   "ancient, old"),
        ("verus",    "adj",   "true, real"),
        ("clarus",   "adj",   "clear, bright, famous"),
        ("liber",    "adj",   "free"),
        ("semper",   "adv",   "always"),
        ("nunc",     "adv",   "now"),
        ("saepe",    "adv",   "often"),
        ("iam",      "adv",   "already, soon, now"),
        ("tum",      "adv",   "then, at that time"),
    ],
    "B1": [
        ("impero",   "verb",  "to command, rule over"),
        ("peto",     "verb",  "to seek, aim at, attack"),
        ("relinquo", "verb",  "to leave behind, abandon"),
        ("vinco",    "verb",  "to conquer, overcome"),
        ("gero",     "verb",  "to carry on, wage, wear"),
        ("ago",      "verb",  "to drive, do, lead, act"),
        ("accipio",  "verb",  "to receive, accept"),
        ("cognosco", "verb",  "to learn, recognise, investigate"),
        ("timeo",    "verb",  "to fear, be afraid of"),
        ("moveo",    "verb",  "to move, stir, affect"),
        ("senatus",  "noun",  "senate"),
        ("exercitus","noun",  "army"),
        ("imperium", "noun",  "command, power, empire"),
        ("virtus",   "noun",  "virtue, courage, excellence"),
        ("patria",   "noun",  "fatherland, native country"),
        ("causa",    "noun",  "cause, reason, case, sake"),
        ("ratio",    "noun",  "reason, method, account"),
        ("fides",    "noun",  "faith, trust, loyalty"),
        ("socius",   "noun",  "ally, companion"),
        ("hostis",   "noun",  "enemy (public), stranger"),
        ("iter",     "noun",  "journey, route, march"),
        ("mons",     "noun",  "mountain, hill"),
        ("flumen",   "noun",  "river, stream"),
        ("caelum",   "noun",  "sky, heaven, weather"),
        ("natura",   "noun",  "nature, character, quality"),
        ("gratia",   "noun",  "grace, favour, gratitude"),
        ("potestas", "noun",  "power, authority, opportunity"),
        ("consul",   "noun",  "consul (highest Roman magistrate)"),
        ("altus",    "adj",   "high, deep, lofty"),
        ("gravis",   "adj",   "heavy, serious, important"),
        ("plenus",   "adj",   "full, filled with"),
        ("talis",    "adj",   "such, of such a kind"),
        ("idem",     "pron",  "the same"),
        ("ipse",     "pron",  "self, himself, herself, itself"),
        ("dum",      "conj",  "while, as long as, until"),
        ("quia",     "conj",  "because, since"),
        ("quod",     "conj",  "because, the fact that"),
        ("ergo",     "adv",   "therefore, consequently"),
        ("tamen",    "adv",   "nevertheless, still, however"),
        ("autem",    "conj",  "but, however, moreover"),
    ],
}

# ── Koine Greek inline vocabulary ─────────────────────────────────────────────
# Curated from Mounce's Basics of Biblical Greek and Trenchard's Complete
# Vocabulary Guide to the Greek New Testament.
# Headwords in normalised form (diacritics stripped, lowercase) matching _LEXICON keys.

_GRC_VOCAB: dict[str, list[tuple[str, str, str]]] = {
    # (lemma, pos, gloss)
    "A1": [
        ("και",       "conj",  "and, also, even, but"),
        ("ο",         "det",   "the (masc nom sg)"),
        ("εν",        "prep",  "in, on, among, by"),
        ("δε",        "conj",  "but, and, now (post-positive)"),
        ("αυτος",     "pron",  "he, she, it; self; same"),
        ("οτι",       "conj",  "that, because, for"),
        ("εις",       "prep",  "into, to, toward, for"),
        ("εκ",        "prep",  "out of, from (with gen)"),
        ("επι",       "prep",  "on, upon, at, over, against"),
        ("ου",        "adv",   "not (before consonant)"),
        ("εγω",       "pron",  "I"),
        ("συ",        "pron",  "you (singular)"),
        ("θεος",      "noun",  "God, god, deity"),
        ("λογος",     "noun",  "word, reason, message"),
        ("κυριος",    "noun",  "lord, master, owner; the Lord"),
        ("ανθρωπος",  "noun",  "man, human being, person"),
        ("χριστος",   "noun",  "Christ, the Anointed One"),
        ("ιησους",    "noun",  "Jesus (Hebrew Yeshua)"),
        ("πνευμα",    "noun",  "spirit, Spirit, wind, breath"),
        ("υιος",      "noun",  "son, descendant"),
        ("αδελφος",   "noun",  "brother, fellow believer"),
        ("πατηρ",     "noun",  "father"),
        ("αμαρτια",   "noun",  "sin, sinfulness"),
        ("αγαπη",     "noun",  "love (unconditional, divine)"),
        ("ζωη",       "noun",  "life"),
        ("κοσμος",    "noun",  "world, universe, adornment"),
        ("ειμι",      "verb",  "to be, exist"),
        ("λεγω",      "verb",  "to say, speak, tell"),
        ("εχω",       "verb",  "to have, hold"),
        ("ερχομαι",   "verb",  "to come, go"),
        ("ακουω",     "verb",  "to hear, listen to, obey"),
        ("βλεπω",     "verb",  "to see, look at, watch"),
        ("αγαπαω",    "verb",  "to love"),
        ("πιστευω",   "verb",  "to believe, trust, have faith in"),
        ("γινωσκω",   "verb",  "to know, learn, understand"),
        ("αγιος",     "adj",   "holy, set apart, saint"),
        ("καλος",     "adj",   "good, beautiful, noble"),
        ("πας",       "adj",   "all, every, whole"),
        ("πολυς",     "adj",   "much, many, large"),
        ("αλλος",     "adj",   "other, another (of same kind)"),
    ],
    "A2": [
        ("γαρ",       "conj",  "for, because, since (post-positive)"),
        ("ινα",       "conj",  "so that, in order that, that"),
        ("αλλα",      "conj",  "but, on the contrary"),
        ("ουν",       "conj",  "therefore, then, accordingly (post-positive)"),
        ("προς",      "prep",  "to, toward, with, against"),
        ("απο",       "prep",  "from, away from (with gen)"),
        ("περι",      "prep",  "about, concerning, around"),
        ("κατα",      "prep",  "according to, down from, against"),
        ("μετα",      "prep",  "with (gen), after (acc)"),
        ("δια",       "prep",  "through (gen), because of (acc)"),
        ("υπο",       "prep",  "by (agent, gen), under (acc)"),
        ("ουτος",     "pron",  "this, these, this person/thing"),
        ("εκεινος",   "pron",  "that, those, the famous"),
        ("τις",       "pron",  "who? what? which? (interrogative)"),
        ("τις",       "pron",  "someone, something (enclitic)"),
        ("αυτη",      "det",   "the (fem nom sg)"),
        ("αρχη",      "noun",  "beginning, rule, authority"),
        ("βασιλεια",  "noun",  "kingdom, reign, rule"),
        ("εκκλησια",  "noun",  "church, assembly, congregation"),
        ("ιουδαιος",  "noun",  "Jew, Jewish person, Judean"),
        ("νομος",     "noun",  "law, the Law (Torah)"),
        ("εργον",     "noun",  "work, deed, action"),
        ("πιστις",    "noun",  "faith, trust, belief"),
        ("καρδια",    "noun",  "heart (seat of inner life)"),
        ("σωμα",      "noun",  "body"),
        ("οικος",     "noun",  "house, household, family"),
        ("ονομα",     "noun",  "name"),
        ("δικαιοσυνη","noun",  "righteousness, justice"),
        ("χαρις",     "noun",  "grace, favour, thanks"),
        ("εντολη",    "noun",  "commandment, order"),
        ("εξερχομαι", "verb",  "to go out, come out, depart"),
        ("εισερχομαι","verb",  "to enter, go into, come in"),
        ("αποστελλω", "verb",  "to send (with authority), commission"),
        ("ποιεω",     "verb",  "to do, make, cause, create"),
        ("λαμβανω",   "verb",  "to take, receive, seize"),
        ("ευρισκω",   "verb",  "to find, discover, obtain"),
        ("γινομαι",   "verb",  "to become, happen, be, come into being"),
        ("απεκρινομαι","verb", "to answer, reply (+ dative)"),
        ("μεγας",     "adj",   "great, large, important"),
        ("πρωτος",    "adj",   "first, foremost, chief"),
        ("εσχατος",   "adj",   "last, final, uttermost"),
    ],
    "B1": [
        ("τε",        "conj",  "and, both...and (enclitic, literary)"),
        ("ει",        "conj",  "if, whether (with ind. or opt.)"),
        ("ωσπερ",     "conj",  "just as, even as"),
        ("καθως",     "conj",  "just as, as, in the same way"),
        ("οταν",      "conj",  "whenever, when (with subjunctive)"),
        ("υπερ",      "prep",  "on behalf of, for (gen); above (acc)"),
        ("παρα",      "prep",  "from beside (gen), beside (dat), contrary to (acc)"),
        ("θανατος",   "noun",  "death"),
        ("αιμα",      "noun",  "blood"),
        ("αιων",      "noun",  "age, eternity, eon; forever (εἰς τὸν αἰῶνα)"),
        ("γραφη",     "noun",  "writing, Scripture"),
        ("αποστολος", "noun",  "apostle, messenger, envoy"),
        ("προφητης",  "noun",  "prophet"),
        ("αγγελος",   "noun",  "angel, messenger"),
        ("διαθηκη",   "noun",  "covenant, testament, agreement"),
        ("ευαγγελιον","noun",  "good news, gospel"),
        ("δοξα",      "noun",  "glory, honour, splendour"),
        ("δυναμις",   "noun",  "power, ability, miracle"),
        ("αληθεια",   "noun",  "truth, reality"),
        ("ελπις",     "noun",  "hope, expectation"),
        ("ειρηνη",    "noun",  "peace, rest, health"),
        ("ψυχη",      "noun",  "soul, life, self"),
        ("σαρξ",      "noun",  "flesh, human nature, body"),
        ("αιτεω",     "verb",  "to ask for, request, demand"),
        ("θελω",      "verb",  "to will, wish, want, desire"),
        ("δυναμαι",   "verb",  "to be able, can, have power"),
        ("οιδα",      "verb",  "to know (intuitively), understand"),
        ("εγειρω",    "verb",  "to raise, arise, wake up"),
        ("αποθνησκω", "verb",  "to die"),
        ("καλεω",     "verb",  "to call, name, invite, summon"),
        ("γραφω",     "verb",  "to write"),
        ("κρινω",     "verb",  "to judge, decide, distinguish"),
        ("σωζω",      "verb",  "to save, rescue, heal, preserve"),
        ("δωρεαν",    "adv",   "freely, without charge, as a gift"),
        ("ουτως",     "adv",   "thus, in this way, so"),
        ("τοτε",      "adv",   "then, at that time"),
        ("παλιν",     "adv",   "again, once more, back"),
        ("αμην",      "adv",   "truly, verily, amen (Hebrew loan)"),
        ("νυν",       "adv",   "now, at this time, as it is"),
        ("νεκρος",    "adj",   "dead, corpse; dead person"),
        ("αιωνιος",   "adj",   "eternal, everlasting, age-long"),
    ],
}

# ── Curated grammar rules ──────────────────────────────────────────────────────

# Format per rule:
#   (category, name, description, examples)
#   examples: list of {"sentence": ..., "translation": ..., "note": ...}

_GRAMMAR: dict[str, dict[str, list[tuple[str, str, str, list[dict]]]]] = {

    # ── English (en) ───────────────────────────────────────────────────────────
    "en": {
        "A1": [
            ("articles", "Indefinite article a/an",
             "Use 'a' before consonant sounds, 'an' before vowel sounds.",
             [{"sentence": "I have a dog.", "translation": "", "note": "consonant sound"},
              {"sentence": "She is an engineer.", "translation": "", "note": "vowel sound"}]),
            ("articles", "Definite article the",
             "Use 'the' for specific or previously mentioned nouns.",
             [{"sentence": "The book is on the table.", "translation": "", "note": ""}]),
            ("verb_tenses", "Present Simple",
             "Habitual actions and general truths. Third-person singular adds -s/-es.",
             [{"sentence": "She works every day.", "translation": "", "note": "3rd person singular +s"},
              {"sentence": "Water boils at 100°C.", "translation": "", "note": "general truth"}]),
            ("verb_tenses", "Present Continuous",
             "Actions happening now. Formed with am/is/are + -ing.",
             [{"sentence": "I am reading a book.", "translation": "", "note": "action in progress"}]),
            ("pronouns", "Subject pronouns",
             "I, you, he, she, it, we, they replace nouns as sentence subjects.",
             [{"sentence": "He is my brother.", "translation": "", "note": ""}]),
            ("sentence_structure", "SVO word order",
             "English uses Subject–Verb–Object order in declarative sentences.",
             [{"sentence": "Maria likes coffee.", "translation": "", "note": "S=Maria, V=likes, O=coffee"}]),
        ],
        "A2": [
            ("verb_tenses", "Past Simple",
             "Completed actions at a specific past time. Regular verbs add -ed; irregular verbs vary.",
             [{"sentence": "I visited Paris last year.", "translation": "", "note": "regular verb"},
              {"sentence": "She went to the market.", "translation": "", "note": "irregular: go→went"}]),
            ("verb_tenses", "Future with will",
             "Predictions and spontaneous decisions. Will + base form.",
             [{"sentence": "It will rain tomorrow.", "translation": "", "note": "prediction"}]),
            ("verb_tenses", "Future with going to",
             "Planned intentions. Am/is/are + going to + base form.",
             [{"sentence": "I am going to study tonight.", "translation": "", "note": "intention"}]),
            ("comparatives", "Comparative adjectives",
             "Short adjectives add -er; long adjectives use more. Than links the two items.",
             [{"sentence": "This bag is heavier than that one.", "translation": "", "note": "short adj"},
              {"sentence": "She is more intelligent than him.", "translation": "", "note": "long adj"}]),
            ("questions", "Yes/No and Wh- questions",
             "Invert subject and auxiliary verb; use do/does/did when no auxiliary present.",
             [{"sentence": "Do you like tea?", "translation": "", "note": "present simple"},
              {"sentence": "Where did you go?", "translation": "", "note": "Wh- question"}]),
        ],
        "B1": [
            ("verb_tenses", "Present Perfect",
             "Connects past to present. Have/has + past participle. Often with ever, never, already, yet.",
             [{"sentence": "I have never been to Japan.", "translation": "", "note": "life experience"},
              {"sentence": "She has just finished her work.", "translation": "", "note": "recent past"}]),
            ("verb_tenses", "Past Continuous",
             "Ongoing action interrupted by a Past Simple event. Was/were + -ing.",
             [{"sentence": "I was cooking when the phone rang.", "translation": "", "note": ""}]),
            ("modal_verbs", "Modals of obligation and deduction",
             "Must (strong obligation), should (advice), can/could (ability/possibility).",
             [{"sentence": "You must wear a seatbelt.", "translation": "", "note": "obligation"},
              {"sentence": "She should see a doctor.", "translation": "", "note": "advice"}]),
            ("passives", "Passive voice (present and past)",
             "Focus on the object or when agent is unknown. Am/is/are/was/were + past participle.",
             [{"sentence": "The window was broken.", "translation": "", "note": "past passive"},
              {"sentence": "Mistakes are made.", "translation": "", "note": "present passive"}]),
            ("conditionals", "Zero and First Conditional",
             "Zero: always true (if + present, present). First: likely future (if + present, will).",
             [{"sentence": "If you heat ice, it melts.", "translation": "", "note": "zero conditional"},
              {"sentence": "If it rains, I will stay in.", "translation": "", "note": "first conditional"}]),
        ],
        "B2": [
            ("verb_tenses", "Past Perfect",
             "Action completed before another past action. Had + past participle.",
             [{"sentence": "She had left before I arrived.", "translation": "", "note": ""}]),
            ("conditionals", "Second and Third Conditional",
             "Second: unreal present/future. Third: unreal past. Would (have) + past participle.",
             [{"sentence": "If I were rich, I would travel.", "translation": "", "note": "second conditional"},
              {"sentence": "If she had studied, she would have passed.", "translation": "", "note": "third conditional"}]),
            ("reported_speech", "Reported speech",
             "Verb tense usually backshifts. Say/tell + that clause.",
             [{"sentence": "He said that he was tired.", "translation": "", "note": "backshift present→past"}]),
            ("relative_clauses", "Defining and non-defining relative clauses",
             "Defining: who/which/that (no commas). Non-defining: who/which (commas, adds info).",
             [{"sentence": "The man who called is my uncle.", "translation": "", "note": "defining"},
              {"sentence": "My sister, who lives in Rome, is a chef.", "translation": "", "note": "non-defining"}]),
        ],
        "C1": [
            ("inversion", "Fronting and inversion",
             "Fronting a negative adverb inverts subject and auxiliary for emphasis.",
             [{"sentence": "Never have I seen such courage.", "translation": "", "note": "negative inversion"},
              {"sentence": "Not only did she win, she broke the record.", "translation": "", "note": ""}]),
            ("discourse", "Discourse markers and cohesion",
             "Connectors that organise academic/formal writing: nevertheless, moreover, albeit, hitherto.",
             [{"sentence": "The results are inconclusive; nevertheless, the trend is clear.", "translation": "", "note": ""}]),
            ("aspect", "Perfect aspect nuances",
             "Present perfect continuous vs perfect: duration vs completion.",
             [{"sentence": "I have been writing this report all day.", "translation": "", "note": "continuous: duration"},
              {"sentence": "I have written the report.", "translation": "", "note": "perfect: completion"}]),
        ],
        "C2": [
            ("style", "Register and stylistic variation",
             "Distinguishing formal, neutral, and informal register; archaisms and elevated diction.",
             [{"sentence": "It is incumbent upon us to address this forthwith.", "translation": "", "note": "formal/archaic"}]),
            ("aspect", "Lexical aspect (telicity)",
             "Distinguishing telic (goal-bounded) from atelic (unbounded) verbs and their aspectual implications.",
             [{"sentence": "She was running. / She ran a mile.", "translation": "", "note": "atelic vs telic"}]),
        ],
    },

    # ── Spanish (es) ───────────────────────────────────────────────────────────
    "es": {
        "A1": [
            ("ser_estar", "Ser vs Estar (basics)",
             "Ser: permanent identity (nationality, profession). Estar: temporary state, location.",
             [{"sentence": "Soy español.", "translation": "I am Spanish.", "note": "ser for nationality"},
              {"sentence": "Estoy cansado.", "translation": "I am tired.", "note": "estar for state"}]),
            ("verb_tenses", "Present tense (-ar/-er/-ir)",
             "Regular present: -ar: hablo/hablas/habla/hablamos/habláis/hablan.",
             [{"sentence": "Ella come ensalada.", "translation": "She eats salad.", "note": "-er verb"},
              {"sentence": "Nosotros vivimos aquí.", "translation": "We live here.", "note": "-ir verb"}]),
            ("gender", "Noun gender and agreement",
             "Nouns are masculine (el) or feminine (la). Adjectives agree in gender and number.",
             [{"sentence": "El chico alto.", "translation": "The tall boy.", "note": "masculine"},
              {"sentence": "La chica alta.", "translation": "The tall girl.", "note": "feminine"}]),
            ("articles", "Definite and indefinite articles",
             "Definite: el/la/los/las. Indefinite: un/una/unos/unas.",
             [{"sentence": "Un libro / El libro.", "translation": "A book / The book.", "note": ""}]),
            ("questions", "Question words",
             "Qué (what), quién (who), dónde (where), cuándo (when), cómo (how), por qué (why).",
             [{"sentence": "¿Cómo te llamas?", "translation": "What is your name?", "note": ""}]),
        ],
        "A2": [
            ("verb_tenses", "Preterite (indefinido)",
             "Completed past actions. Regular: -ar → -é/-aste/-ó; -er/-ir → -í/-iste/-ió.",
             [{"sentence": "Ayer fui al mercado.", "translation": "Yesterday I went to the market.", "note": "irregular: ir"},
              {"sentence": "Ella habló con el médico.", "translation": "She spoke with the doctor.", "note": "regular -ar"}]),
            ("verb_tenses", "Imperfect (imperfecto)",
             "Habitual/ongoing past actions or background descriptions.",
             [{"sentence": "Cuando era niño, jugaba mucho.", "translation": "When I was a child, I used to play a lot.", "note": "habitual"}]),
            ("reflexive", "Reflexive verbs",
             "Verb performs action on subject itself. Reflexive pronouns: me/te/se/nos/os/se.",
             [{"sentence": "Me llamo Ana.", "translation": "My name is Ana (I call myself Ana).", "note": ""},
              {"sentence": "Él se levanta a las ocho.", "translation": "He gets up at eight.", "note": ""}]),
            ("comparatives", "Comparatives and superlatives",
             "Más/menos + adj + que. Superlative: el/la más + adj.",
             [{"sentence": "Madrid es más grande que Sevilla.", "translation": "Madrid is bigger than Seville.", "note": ""}]),
        ],
        "B1": [
            ("verb_tenses", "Subjunctive present",
             "Expresses wishes, doubts, emotions after verbs like querer, esperar, dudar. -ar: -e; -er/-ir: -a.",
             [{"sentence": "Espero que vengas.", "translation": "I hope you come.", "note": "wish clause"},
              {"sentence": "Es importante que estudies.", "translation": "It is important that you study.", "note": "impersonal expression"}]),
            ("verb_tenses", "Future tense",
             "Formed by adding -é/-ás/-á/-emos/-éis/-án to infinitive.",
             [{"sentence": "Mañana hablaré con el jefe.", "translation": "Tomorrow I will speak with the boss.", "note": ""}]),
            ("passives", "Passive with se (se pasiva)",
             "Se + third-person verb. More common than ser + past participle in everyday speech.",
             [{"sentence": "Se habla español aquí.", "translation": "Spanish is spoken here.", "note": ""}]),
            ("por_para", "Por vs Para",
             "Por: cause, duration, exchange. Para: purpose, recipient, deadline.",
             [{"sentence": "Te llamo por teléfono.", "translation": "I'll call you by phone.", "note": "por: means"},
              {"sentence": "Este regalo es para ti.", "translation": "This gift is for you.", "note": "para: recipient"}]),
        ],
        "B2": [
            ("verb_tenses", "Subjunctive imperfect",
             "Past subjunctive for hypothetical/impossible conditions. -ra or -se endings.",
             [{"sentence": "Si tuviera dinero, viajaría.", "translation": "If I had money, I would travel.", "note": "conditional clause"}]),
            ("verb_tenses", "Conditional tense",
             "Hypothetical results. Same stem as future + -ía/-ías/-ía/-íamos/-íais/-ían.",
             [{"sentence": "¿Podrías ayudarme?", "translation": "Could you help me?", "note": "polite request"}]),
            ("verb_tenses", "Perfect tenses",
             "Pluperfect (había + pp) for past-before-past; Future perfect (habré + pp) for future completion.",
             [{"sentence": "Cuando llegué, ella ya había salido.", "translation": "When I arrived, she had already left.", "note": "pluperfect"}]),
        ],
        "C1": [
            ("verb_tenses", "Subjunctive perfect",
             "Espero que hayas llegado bien. Past event viewed from present with uncertainty/wish.",
             [{"sentence": "Es posible que haya cometido un error.", "translation": "It is possible that he has made an error.", "note": ""}]),
            ("discourse", "Discourse connectors",
             "Sin embargo, no obstante, por consiguiente, a pesar de que, con el fin de.",
             [{"sentence": "No obstante, los resultados fueron positivos.", "translation": "However, the results were positive.", "note": ""}]),
        ],
        "C2": [
            ("register", "Register and style",
             "Distinguishing coloquial, estándar, culto and argot registers; ellipsis in speech.",
             [{"sentence": "¡Qué guay!", "translation": "How cool! (colloquial Spain)", "note": "informal register"}]),
            ("inversion", "Lexical and syntactic inversion",
             "Fronting for emphasis: 'De esto no se habla.' Topic-comment constructions.",
             [{"sentence": "De política, mejor no hablar.", "translation": "Politics, better not to discuss.", "note": "fronted topic"}]),
        ],
    },

    # ── French (fr) ────────────────────────────────────────────────────────────
    "fr": {
        "A1": [
            ("articles", "Definite and indefinite articles",
             "Definite: le/la/l'/les. Indefinite: un/une/des. Contract after de and à.",
             [{"sentence": "Je veux du pain.", "translation": "I want some bread.", "note": "de + le → du"}]),
            ("verb_tenses", "Présent de l'indicatif",
             "Regular -er (parler), -ir (finir), -re (vendre). Many common irregular verbs: être, avoir, faire, aller.",
             [{"sentence": "Je parle français.", "translation": "I speak French.", "note": "regular -er"},
              {"sentence": "Il fait beau.", "translation": "The weather is nice.", "note": "faire: irregular"}]),
            ("gender", "Noun gender",
             "All nouns are masculine or feminine. No neuter. Adjectives agree in gender and number.",
             [{"sentence": "un grand livre / une grande maison", "translation": "a big book / a big house", "note": ""}]),
            ("negation", "Basic negation: ne ... pas",
             "Wrap the conjugated verb with ne ... pas. Ne may elide before vowels.",
             [{"sentence": "Je ne parle pas anglais.", "translation": "I don't speak English.", "note": ""},
              {"sentence": "Il n'est pas là.", "translation": "He is not here.", "note": "elision"}]),
        ],
        "A2": [
            ("verb_tenses", "Passé composé",
             "Past tense formed with avoir or être + past participle. Être verbs: DR MRS VAN DER TRAMP + reflexives.",
             [{"sentence": "J'ai mangé une pizza.", "translation": "I ate a pizza.", "note": "avoir"},
              {"sentence": "Elle est allée au marché.", "translation": "She went to the market.", "note": "être: aller"}]),
            ("verb_tenses", "Imparfait",
             "Ongoing or habitual past. Stem from nous-form present + -ais/-ais/-ait/-ions/-iez/-aient.",
             [{"sentence": "Quand j'étais enfant, je jouais dehors.", "translation": "When I was a child, I played outside.", "note": "habitual"}]),
            ("pronouns", "Direct and indirect object pronouns",
             "Direct: me/te/le/la/nous/vous/les. Indirect: me/te/lui/nous/vous/leur. Placed before verb.",
             [{"sentence": "Je le vois.", "translation": "I see him/it.", "note": "direct"},
              {"sentence": "Je lui parle.", "translation": "I speak to him/her.", "note": "indirect"}]),
            ("partitive", "Partitive article du/de la/de l'/des",
             "Expresses an unspecified quantity. After negation, becomes de/d'.",
             [{"sentence": "Je bois du café.", "translation": "I drink (some) coffee.", "note": ""},
              {"sentence": "Je ne bois pas de café.", "translation": "I don't drink coffee.", "note": "negation → de"}]),
        ],
        "B1": [
            ("verb_tenses", "Futur simple",
             "Infinitive + -ai/-as/-a/-ons/-ez/-ont. Irregular stems: être→ser-, avoir→aur-, aller→ir-.",
             [{"sentence": "Demain il fera beau.", "translation": "Tomorrow the weather will be nice.", "note": "faire→fer-"}]),
            ("verb_tenses", "Conditionnel présent",
             "Hypothetical events. Futur stem + imparfait endings.",
             [{"sentence": "Je voudrais un café.", "translation": "I would like a coffee.", "note": "polite request"}]),
            ("verb_tenses", "Subjonctif présent",
             "After verbs of wishing/fearing/doubt and certain conjunctions (bien que, pour que).",
             [{"sentence": "Je veux qu'il vienne.", "translation": "I want him to come.", "note": ""},
              {"sentence": "Bien qu'il soit tard, je travaille.", "translation": "Although it is late, I am working.", "note": ""}]),
            ("pronouns", "Relative pronouns qui/que/dont/où",
             "Qui: subject. Que: object. Dont: de + antecedent. Où: place/time.",
             [{"sentence": "La femme qui chante est ma mère.", "translation": "The woman who sings is my mother.", "note": "subject"},
              {"sentence": "Le livre dont je parle est fantastique.", "translation": "The book I'm talking about is fantastic.", "note": "dont"}]),
        ],
        "B2": [
            ("verb_tenses", "Plus-que-parfait",
             "Past-before-past. Avoir/être in imparfait + past participle.",
             [{"sentence": "Quand je suis arrivé, il était déjà parti.", "translation": "When I arrived, he had already left.", "note": ""}]),
            ("passives", "Passive voice",
             "Être + past participle (agrees with subject) + par for agent.",
             [{"sentence": "Le livre a été écrit par Camus.", "translation": "The book was written by Camus.", "note": ""}]),
            ("verb_tenses", "Subjonctif passé",
             "Past action seen with subjectivity from present: avoir/être in subjonctif + past participle.",
             [{"sentence": "Je suis content qu'il soit venu.", "translation": "I am glad he came.", "note": ""}]),
        ],
        "C1": [
            ("style", "Nominalisation",
             "Converting verbs/adjectives to nouns for formal/written style.",
             [{"sentence": "La mise en œuvre de la réforme a commencé.", "translation": "The implementation of the reform has begun.", "note": ""}]),
            ("verb_tenses", "Subjonctif imparfait",
             "Literary/formal past subjunctive. Rare in speech; encountered in literature.",
             [{"sentence": "Il fallait qu'il fût là.", "translation": "He had to be there.", "note": "literary register"}]),
        ],
        "C2": [
            ("register", "Soutenu vs argot register",
             "Distinguishing soutenu (formal, literary) from familiar and argot registers.",
             [{"sentence": "Ce bouquin est vachement bien.", "translation": "This book is really good. (familiar)", "note": "bouquin=book, vachement=very (familiar)"}]),
        ],
    },

    # ── German (de) ────────────────────────────────────────────────────────────
    "de": {
        "A1": [
            ("articles", "Definite article (der/die/das) and gender",
             "Every noun has a grammatical gender. Der (m), die (f), das (n). Plural always die.",
             [{"sentence": "Der Mann, die Frau, das Kind.", "translation": "The man, the woman, the child.", "note": "three genders"},
              {"sentence": "Die Männer, die Frauen, die Kinder.", "translation": "The men, the women, the children.", "note": "plural: always die"}]),
            ("verb_tenses", "Präsens (present tense)",
             "Regular conjugation: stem + -e/-st/-t/-en/-t/-en. Stem-vowel change for some verbs (fahren, lesen).",
             [{"sentence": "Ich lerne Deutsch.", "translation": "I am learning German.", "note": "regular"},
              {"sentence": "Du fährst nach Berlin.", "translation": "You are driving to Berlin.", "note": "vowel change: a→ä"}]),
            ("word_order", "V2 word order",
             "The conjugated verb is always second in a declarative main clause.",
             [{"sentence": "Heute gehe ich ins Kino.", "translation": "Today I am going to the cinema.", "note": "adverb first → V2: verb before subject"}]),
            ("cases", "Nominative and Accusative cases",
             "Nominative: subject. Accusative: direct object. Der→den (m, accusative).",
             [{"sentence": "Der Mann sieht den Hund.", "translation": "The man sees the dog.", "note": "der→den for masculine accusative"}]),
        ],
        "A2": [
            ("cases", "Dative case",
             "Indirect object and after dative prepositions (mit, bei, nach, seit, von, zu, aus, gegenüber). Dem (m/n), der (f).",
             [{"sentence": "Ich gebe dem Mann das Buch.", "translation": "I give the man the book.", "note": "dem: dative masculine"},
              {"sentence": "Er wohnt bei der Familie.", "translation": "He lives with the family.", "note": "bei + dative"}]),
            ("modal_verbs", "Modal verbs",
             "können, müssen, wollen, sollen, dürfen, mögen. Second position; infinitive goes to end.",
             [{"sentence": "Ich kann Deutsch sprechen.", "translation": "I can speak German.", "note": "infinitive at end"},
              {"sentence": "Du musst das lernen.", "translation": "You must learn that.", "note": ""}]),
            ("word_order", "Subordinate clause word order",
             "In subordinate clauses (dass, weil, wenn, obwohl) the conjugated verb moves to the end.",
             [{"sentence": "Ich weiß, dass er kommt.", "translation": "I know that he is coming.", "note": "verb final in dass-clause"},
              {"sentence": "Er bleibt zu Hause, weil er krank ist.", "translation": "He stays at home because he is sick.", "note": ""}]),
            ("perfect", "Perfekt (conversational past)",
             "Haben/sein + past participle (Partizip II). Used in speech for completed actions.",
             [{"sentence": "Ich habe gegessen.", "translation": "I have eaten / I ate.", "note": "haben + ge-...-en"},
              {"sentence": "Sie ist gefahren.", "translation": "She has driven / She drove.", "note": "sein for motion verbs"}]),
        ],
        "B1": [
            ("cases", "Genitive case",
             "Possession and after genitive prepositions (wegen, trotz, während, statt). -(e)s added to m/n nouns.",
             [{"sentence": "Das ist das Buch des Mannes.", "translation": "That is the man's book.", "note": "des: genitive masculine"},
              {"sentence": "Wegen des Regens blieb ich zu Hause.", "translation": "Because of the rain I stayed home.", "note": "wegen + genitive"}]),
            ("adjectives", "Adjective declension",
             "Adjectives take different endings depending on case, gender, and article type (strong/weak/mixed).",
             [{"sentence": "Ein großer Mann / der große Mann.", "translation": "A tall man / the tall man.", "note": "strong vs weak declension"}]),
            ("verb_tenses", "Präteritum (written past)",
             "Simple past used in writing and for haben/sein/modals in speech. Regular: stem + -te endings.",
             [{"sentence": "Er war müde.", "translation": "He was tired.", "note": "sein→war"},
              {"sentence": "Sie hatte keine Zeit.", "translation": "She had no time.", "note": "haben→hatte"}]),
            ("conjunctions", "Two-part conjunctions",
             "Entweder...oder (either...or), sowohl...als auch (both...and), nicht nur...sondern auch (not only...but also).",
             [{"sentence": "Er spricht sowohl Englisch als auch Französisch.", "translation": "He speaks both English and French.", "note": ""}]),
        ],
        "B2": [
            ("passives", "Passive voice (Vorgangs- and Zustandspassiv)",
             "Vorgangpassiv: werden + pp (action). Zustandspassiv: sein + pp (resulting state).",
             [{"sentence": "Die Tür wird geöffnet.", "translation": "The door is being opened.", "note": "Vorgangpassiv"},
              {"sentence": "Die Tür ist geöffnet.", "translation": "The door is open.", "note": "Zustandspassiv"}]),
            ("konjunktiv", "Konjunktiv II (hypothetical/polite)",
             "Expresses wishes, hypotheticals, polite requests. Würde + infinitive or special forms (wäre, hätte, könnte).",
             [{"sentence": "Wenn ich Zeit hätte, würde ich reisen.", "translation": "If I had time, I would travel.", "note": "conditional"},
              {"sentence": "Könnten Sie mir helfen?", "translation": "Could you help me?", "note": "polite request"}]),
            ("separable_verbs", "Separable and inseparable prefix verbs",
             "Separable prefixes (an-, auf-, aus-, mit-) detach in main clauses. Inseparable prefixes (be-, er-, ver-) never detach.",
             [{"sentence": "Er ruft seine Mutter an.", "translation": "He calls his mother.", "note": "anrufen: separable"},
              {"sentence": "Er versteht das nicht.", "translation": "He doesn't understand that.", "note": "verstehen: inseparable"}]),
        ],
        "C1": [
            ("konjunktiv", "Konjunktiv I (reported speech)",
             "Expresses indirect speech in formal/journalistic writing. Er sagt, er sei krank.",
             [{"sentence": "Der Minister erklärte, die Lage sei stabil.", "translation": "The minister stated that the situation was stable.", "note": "indirect speech"}]),
            ("extended_attributes", "Erweitertes Partizipialattribut",
             "A complex participial phrase placed before a noun, functioning as a relative clause (formal/written).",
             [{"sentence": "Das von der Regierung beschlossene Gesetz trat in Kraft.", "translation": "The law passed by the government came into force.", "note": "equiv: das Gesetz, das die Regierung beschlossen hat"}]),
        ],
        "C2": [
            ("style", "Nominalstil vs Verbalstil",
             "Nominalization (Nominalstil) is characteristic of academic/bureaucratic German. Converting to Verbalstil improves clarity.",
             [{"sentence": "nach Abschluss der Untersuchung vs nachdem die Untersuchung abgeschlossen wurde", "translation": "after conclusion of the investigation vs after the investigation was concluded", "note": ""}]),
        ],
    },

    # ── Italian (it) ───────────────────────────────────────────────────────────
    "it": {
        "A1": [
            ("articles", "Definite and indefinite articles",
             "Definite: il/lo/la/l'/i/gli/le. Indefinite: un/uno/una/un'. Choice depends on initial sound.",
             [{"sentence": "il libro / lo zaino / la casa", "translation": "the book / the backpack / the house", "note": ""},
              {"sentence": "uno studente / una studentessa", "translation": "a (male) student / a (female) student", "note": ""}]),
            ("verb_tenses", "Presente indicativo",
             "Regular -are (parlare), -ere (leggere), -ire (dormire/finire). Many common irregular verbs.",
             [{"sentence": "Io parlo italiano.", "translation": "I speak Italian.", "note": "regular -are"},
              {"sentence": "Lei legge un libro.", "translation": "She reads a book.", "note": "regular -ere"}]),
            ("gender", "Noun gender",
             "Typically -o (m) and -a (f); -e can be either. Adjectives agree.",
             [{"sentence": "Il ragazzo simpatico / La ragazza simpatica.", "translation": "The nice boy / The nice girl.", "note": ""}]),
        ],
        "A2": [
            ("verb_tenses", "Passato prossimo",
             "Conversational past: avere/essere + past participle. Essere verbs (motion, change of state) require agreement.",
             [{"sentence": "Ho mangiato la pizza.", "translation": "I ate the pizza.", "note": "avere"},
              {"sentence": "Sono andato al mercato.", "translation": "I went to the market.", "note": "essere: agreement m.sg."}]),
            ("verb_tenses", "Imperfetto",
             "Habitual/ongoing past: -avo/-avi/-ava/-avamo/-avate/-avano (-are). Describes background actions.",
             [{"sentence": "Da bambino, giocavo ogni giorno.", "translation": "As a child, I played every day.", "note": "habitual"}]),
            ("reflexive", "Reflexive verbs",
             "Mi/ti/si/ci/vi/si before verb. Common in daily routines.",
             [{"sentence": "Mi chiamo Lucia.", "translation": "My name is Lucia.", "note": ""},
              {"sentence": "Si alza alle sette.", "translation": "He/She gets up at seven.", "note": ""}]),
        ],
        "B1": [
            ("verb_tenses", "Futuro semplice",
             "Infinitive minus final -e + personal endings. Irregular: essere→sar-, avere→avr-, andare→andr-.",
             [{"sentence": "Domani parlerò con il capo.", "translation": "Tomorrow I will speak with the boss.", "note": ""}]),
            ("congiuntivo", "Congiuntivo presente",
             "After verbs of wishing/fearing/believing and certain conjunctions (benché, affinché, sebbene).",
             [{"sentence": "Voglio che tu venga.", "translation": "I want you to come.", "note": "wish"},
              {"sentence": "Benché piova, esco.", "translation": "Although it is raining, I am going out.", "note": "benché + congiuntivo"}]),
            ("pronouns", "Combined object pronouns",
             "When direct and indirect pronouns combine, indirect precedes: mi/ti/gli/ci/vi → me/te/glie/ce/ve + lo/la/li/le/ne.",
             [{"sentence": "Me lo dai?", "translation": "Will you give it to me?", "note": "mi + lo → me lo"}]),
        ],
        "B2": [
            ("verb_tenses", "Congiuntivo passato",
             "Past subjunctive for completed actions viewed with subjectivity from present.",
             [{"sentence": "Sono contento che tu sia venuto.", "translation": "I am glad you came.", "note": ""}]),
            ("conditional", "Condizionale presente e passato",
             "Polite requests, hypotheticals, reported speech. Past conditional for unrealised past events.",
             [{"sentence": "Se potessi, viaggerei di più.", "translation": "If I could, I would travel more.", "note": ""},
              {"sentence": "Se avessi studiato, avrei passato l'esame.", "translation": "If I had studied, I would have passed the exam.", "note": "past conditional"}]),
        ],
        "C1": [
            ("verb_tenses", "Congiuntivo imperfetto e trapassato",
             "Imperfect subjunctive for hypothetical/unrealised past. Trapassato for earlier past.",
             [{"sentence": "Vorrei che studiasse di più.", "translation": "I wish he studied more.", "note": "imperfect subjunctive"},
              {"sentence": "Se avesse studiato... (trapassato)", "translation": "If he had studied...", "note": ""}]),
        ],
        "C2": [
            ("register", "Register variants",
             "Literary Italian retains subjunctive in indirect speech, archaic forms (desso, or sono) and elevated lexis.",
             [{"sentence": "Aveva detto che venisse presto.", "translation": "He had said to come early.", "note": "literary indirect speech"}]),
        ],
    },

    # ── Portuguese (pt) ─────────────────────────────────────────────────────────
    "pt": {
        "A1": [
            ("verb_tenses", "Presente do indicativo",
             "Regular -ar (falar), -er (comer), -ir (partir). Ser vs estar distinction similar to Spanish.",
             [{"sentence": "Eu falo português.", "translation": "I speak Portuguese.", "note": "regular -ar"},
              {"sentence": "Ela é professora.", "translation": "She is a teacher.", "note": "ser for profession"}]),
            ("gender", "Noun gender and agreement",
             "Nouns typically end in -o (m) or -a (f); adjectives agree.",
             [{"sentence": "um livro pequeno / uma casa pequena", "translation": "a small book / a small house", "note": ""}]),
            ("ser_estar", "Ser vs Estar",
             "Ser: permanent/identity. Estar: temporary state/location.",
             [{"sentence": "Estou cansado.", "translation": "I am tired.", "note": "estar: state"},
              {"sentence": "Sou brasileiro.", "translation": "I am Brazilian.", "note": "ser: nationality"}]),
        ],
        "A2": [
            ("verb_tenses", "Pretérito perfeito simples",
             "Completed past actions: -ar: -ei/-aste/-ou/-ámos/-astes/-aram.",
             [{"sentence": "Ontem eu fui ao mercado.", "translation": "Yesterday I went to the market.", "note": "irregular: ir"},
              {"sentence": "Ela falou com o médico.", "translation": "She spoke with the doctor.", "note": "regular"}]),
            ("verb_tenses", "Pretérito imperfeito",
             "Background past / habitual: -ar: -ava/-avas/-ava/-ávamos/-áveis/-avam.",
             [{"sentence": "Quando era criança, brincava muito.", "translation": "When I was a child, I played a lot.", "note": ""}]),
            ("personal_infinitive", "Personal infinitive (European Portuguese)",
             "Inflected infinitive with personal endings: falar/falares/falar/falarmos/falardes/falarem.",
             [{"sentence": "É importante fazermos isso.", "translation": "It is important for us to do that.", "note": "EP feature"}]),
        ],
        "B1": [
            ("verb_tenses", "Futuro do indicativo",
             "Infinitive + -ei/-ás/-á/-emos/-eis/-ão. Regular in form; irregular: fazer→far-, dizer→dir-.",
             [{"sentence": "Amanhã farei a tarefa.", "translation": "Tomorrow I will do the task.", "note": ""}]),
            ("subjunctive", "Presente do conjuntivo",
             "After querer que, esperar que, para que, embora, antes que.",
             [{"sentence": "Espero que venhas.", "translation": "I hope you come.", "note": "BP: venha / EP: venhas"}]),
        ],
        "B2": [
            ("conditional", "Futuro do pretérito (condicional)",
             "Hypotheticals: -ia/-ias/-ia/-íamos/-íeis/-iam.",
             [{"sentence": "Se eu tivesse tempo, viajaria.", "translation": "If I had time, I would travel.", "note": ""}]),
        ],
        "C1": [
            ("subjunctive", "Conjuntivo imperfeito",
             "Hypothetical/polite/indirect speech: -asse/-asses/-asse/-ássemos/-ásseis/-assem.",
             [{"sentence": "Ele pediu que eu fizesse o relatório.", "translation": "He asked me to write the report.", "note": ""}]),
        ],
        "C2": [
            ("register", "BP vs EP register",
             "Brazilian Portuguese (BP) and European Portuguese (EP) differ in clitic placement, pronoun use, and lexis.",
             [{"sentence": "Me diz isso. (BP) / Diz-me isso. (EP)", "translation": "Tell me that.", "note": "clitic placement"}]),
        ],
    },

    # ── Russian (ru) ───────────────────────────────────────────────────────────
    "ru": {
        "A1": [
            ("cases", "Nominative case",
             "Subject of a sentence. Base form of the noun. Adjectives agree in gender, number, case.",
             [{"sentence": "Это большой город.", "translation": "This is a big city.", "note": "nominative: subject"},
              {"sentence": "Она красивая женщина.", "translation": "She is a beautiful woman.", "note": "adj agreement: fem."}]),
            ("verb_tenses", "Present tense (non-past)",
             "Russian has no present-tense distinction from simple/continuous. Imperfective aspect used for present.",
             [{"sentence": "Я читаю книгу.", "translation": "I am reading / I read a book.", "note": "imperfective = present"},
              {"sentence": "Он говорит по-русски.", "translation": "He speaks Russian.", "note": ""}]),
            ("gender", "Noun gender",
             "-а/-я: usually feminine. Consonant ending: usually masculine. -о/-е: neuter. Memorise exceptions.",
             [{"sentence": "стол (m) / книга (f) / окно (n)", "translation": "table / book / window", "note": "typical endings"}]),
            ("pronouns", "Personal pronouns",
             "Я, ты, он/она/оно, мы, вы, они. No articles in Russian.",
             [{"sentence": "Мы студенты.", "translation": "We are students.", "note": "no verb 'to be' in present"}]),
        ],
        "A2": [
            ("cases", "Accusative case",
             "Direct object. Inanimate: same as nominative (neuter/feminine differ). Animate nouns: same as genitive.",
             [{"sentence": "Я вижу стол / собаку.", "translation": "I see the table / the dog.", "note": "inanimate / animate"}]),
            ("cases", "Genitive case",
             "Possession, absence (нет), after numerals 2–4 (gen.sg.), 5+ (gen.pl.), after много, мало.",
             [{"sentence": "Это книга студента.", "translation": "This is the student's book.", "note": "possession"},
              {"sentence": "У меня нет времени.", "translation": "I have no time.", "note": "нет + genitive"}]),
            ("cases", "Dative case",
             "Indirect object; after certain prepositions (к, по); used in age expressions.",
             [{"sentence": "Я дал другу книгу.", "translation": "I gave my friend the book.", "note": "indirect object"},
              {"sentence": "Мне двадцать лет.", "translation": "I am twenty years old.", "note": "age with dative"}]),
            ("aspect", "Verbal aspect basics",
             "Imperfective (process/habitual) vs perfective (completed action/result). Aspect pairs must be memorised.",
             [{"sentence": "Я читал (impf) / прочитал (pf) книгу.", "translation": "I was reading / I read (finished) the book.", "note": "aspect contrast"}]),
        ],
        "B1": [
            ("cases", "Instrumental case",
             "Instrument, accompaniment (with), predicate after быть in past/future.",
             [{"sentence": "Я пишу ручкой.", "translation": "I write with a pen.", "note": "instrument"},
              {"sentence": "Он был учителем.", "translation": "He was a teacher.", "note": "predicative"}]),
            ("cases", "Prepositional case",
             "Used exclusively with prepositions о (about), в/на (location), при.",
             [{"sentence": "Я думаю о работе.", "translation": "I think about work.", "note": "о + prepositional"},
              {"sentence": "Она живёт в Москве.", "translation": "She lives in Moscow.", "note": "в + prepositional"}]),
            ("verb_tenses", "Past tense",
             "Agrees in gender/number with subject: читал (m.sg.) / читала (f.sg.) / читали (pl.). No person distinction.",
             [{"sentence": "Она читала. / Он читал.", "translation": "She was reading. / He was reading.", "note": "gender agreement"}]),
            ("motion_verbs", "Verbs of motion",
             "Unprefixed: идти (on foot, one direction) vs ходить (repeated/general). Same distinction for ехать/ездить.",
             [{"sentence": "Я иду в школу.", "translation": "I am going to school (now).", "note": "directional"},
              {"sentence": "Я хожу в школу каждый день.", "translation": "I go to school every day.", "note": "habitual"}]),
        ],
        "B2": [
            ("aspect", "Perfective/imperfective in imperatives and after phase verbs",
             "начать (begin), кончить (stop), продолжать (continue) take imperfective infinitive.",
             [{"sentence": "Начни читать! / Начни прочитать! ✗", "translation": "Start reading!", "note": "начать + impf only"}]),
            ("short_adj", "Short-form adjectives",
             "Predicative short forms: рад/рада/рады, готов/готова/готово, должен/должна.",
             [{"sentence": "Я рад тебя видеть.", "translation": "I am glad to see you.", "note": "short adj predicative"}]),
            ("participles", "Participles and gerunds (деепричастия)",
             "Present active participle (-ущий/-ящий). Gerund (-я/-а): simultaneous action.",
             [{"sentence": "Читая книгу, он думал.", "translation": "While reading the book, he was thinking.", "note": "gerund: simultaneous"}]),
        ],
        "C1": [
            ("conditionals", "Conditionals with бы",
             "Subjunctive/conditional: past tense + бы. Concessive: хотя бы, если бы.",
             [{"sentence": "Если бы я знал, я бы сказал.", "translation": "If I had known, I would have said.", "note": ""}]),
            ("register", "Book vs colloquial register",
             "Bookish: причастные/деепричастные обороты, отглагольные существительные. Colloquial: reduced forms.",
             [{"sentence": "Прибывший поезд / Поезд, который прибыл", "translation": "The arrived train / The train that arrived", "note": "formal participial vs relative clause"}]),
        ],
        "C2": [
            ("style", "Stylistic layers of Russian",
             "Distinguishing высокий стиль (elevated), нейтральный (neutral), разговорный (colloquial) and жаргон.",
             [{"sentence": "очи (poetic) / глаза (neutral) / гляделки (colloquial)", "translation": "eyes", "note": "register contrast"}]),
        ],
    },

    # ── Japanese (ja) ──────────────────────────────────────────────────────────
    "ja": {
        "A1": [
            ("particles", "Topic particle は (wa)",
             "Marks the topic of the sentence. Often a contrast with が.",
             [{"sentence": "私は学生です。", "translation": "I am a student.", "note": "topic marker"}]),
            ("particles", "Subject particle が (ga)",
             "Marks the grammatical subject, especially in existence, ability, desire sentences.",
             [{"sentence": "猫がいます。", "translation": "There is a cat.", "note": "existence: います"}]),
            ("particles", "Object particle を (wo)",
             "Marks the direct object of a transitive verb.",
             [{"sentence": "本を読みます。", "translation": "I read a book.", "note": "direct object"}]),
            ("verb_forms", "Polite present/future -ます (-masu)",
             "Formal/polite non-past. Stem + ます. Negative: ません.",
             [{"sentence": "食べます / 食べません", "translation": "I eat / I don't eat", "note": "affirmative / negative"},
              {"sentence": "行きます。", "translation": "I go / I will go.", "note": "no tense distinction"}]),
            ("copula", "Copula です (desu)",
             "Links subject to predicate noun/adjective. Polite register. Plain form: だ.",
             [{"sentence": "これは本です。", "translation": "This is a book.", "note": ""},
              {"sentence": "彼は親切です。", "translation": "He is kind.", "note": "i-adj: 親切な→親切です (na-adj)"}]),
        ],
        "A2": [
            ("adjectives", "い-adjectives and な-adjectives",
             "い-adj conjugate directly (大きい→大きくない). な-adj use な before nouns, に before verbs.",
             [{"sentence": "大きい部屋 / 大きくない", "translation": "big room / not big", "note": "i-adj"},
              {"sentence": "静かな部屋 / 静かではない", "translation": "quiet room / not quiet", "note": "na-adj"}]),
            ("verb_forms", "て-form (te-form) uses",
             "Connects actions (then), makes requests (ください), forms progressive (~ている).",
             [{"sentence": "食べてください。", "translation": "Please eat.", "note": "request"},
              {"sentence": "今、食べています。", "translation": "I am eating now.", "note": "progressive"}]),
            ("particles", "Location particles に and で",
             "に: destination and location of existence. で: location of action.",
             [{"sentence": "学校に行きます。", "translation": "I go to school.", "note": "に: destination"},
              {"sentence": "図書館で読みます。", "translation": "I read at the library.", "note": "で: action location"}]),
            ("verb_forms", "Past tense -ました (-mashita)",
             "Polite past: stem + ました. Negative past: ませんでした.",
             [{"sentence": "昨日、映画を見ました。", "translation": "Yesterday I watched a film.", "note": ""}]),
        ],
        "B1": [
            ("verb_forms", "Plain form (dictionary form) and た-form",
             "Plain form used in informal speech, embedded clauses, and nominalisations.",
             [{"sentence": "映画を見た。", "translation": "I watched a film. (casual)", "note": "plain past"},
              {"sentence": "映画を見たことがある。", "translation": "I have seen a film before.", "note": "experience expression"}]),
            ("conditionals", "Conditionals: と, たら, ば, なら",
             "と: natural result. たら: past completion condition. ば: hypothetical. なら: contextual assumption.",
             [{"sentence": "春になると、花が咲く。", "translation": "When spring comes, flowers bloom.", "note": "と: natural result"},
              {"sentence": "雨が降ったら、中止します。", "translation": "If it rains, we will cancel.", "note": "たら: condition"}]),
            ("potential", "Potential form",
             "Ability: Gr.2 -られる, Gr.1 -える conjugation. Shortened colloquial forms common.",
             [{"sentence": "日本語が話せます。", "translation": "I can speak Japanese.", "note": "話す→話せる (gr.1)"},
              {"sentence": "泳げません。", "translation": "I cannot swim.", "note": "泳ぐ→泳げない"}]),
            ("giving_receiving", "Giving/receiving verbs あげる・もらう・くれる",
             "あげる: give (to others). もらう: receive. くれる: give (to me/in-group). Encode social direction.",
             [{"sentence": "友達に本をあげました。", "translation": "I gave a book to my friend.", "note": "あげる: outward"},
              {"sentence": "先生に本をもらいました。", "translation": "I received a book from the teacher.", "note": "もらう: inward"}]),
        ],
        "B2": [
            ("causative_passive", "Causative (-させる) and passive (-られる) forms",
             "Causative: make/let s.o. do. Passive: action done to subject. Causative-passive: be made to do.",
             [{"sentence": "先生は生徒に宿題をさせた。", "translation": "The teacher made the students do homework.", "note": "causative"},
              {"sentence": "私は怒られた。", "translation": "I was scolded.", "note": "passive"}]),
            ("formal_expressions", "Formal/humble/honorific speech (敬語)",
             "Sonkeigo (respectful for others), kenjōgo (humble for oneself), teineigo (polite).",
             [{"sentence": "先生はいらっしゃいますか？", "translation": "Is the teacher here?", "note": "sonkeigo: いる→いらっしゃる"},
              {"sentence": "私は参ります。", "translation": "I will go. (humble)", "note": "kenjōgo: 行く→参る"}]),
        ],
        "C1": [
            ("classical", "Classical grammar residues in modern Japanese",
             "Literary/formal written Japanese retains classical forms: である, にすぎない, をもって.",
             [{"sentence": "それは努力の賜物にほかならない。", "translation": "It is nothing other than the fruit of effort.", "note": "formal written"}]),
            ("connectors", "Advanced discourse connectors",
             "したがって (therefore), ところが (however), それどころか (on the contrary), とはいえ (that said).",
             [{"sentence": "準備は十分だ。とはいえ、不安は残る。", "translation": "The preparation is sufficient. That said, anxiety remains.", "note": ""}]),
        ],
        "C2": [
            ("style", "Register mastery and code-switching",
             "Seamless switching between plain, polite, keigo, and colloquial registers in context.",
             [{"sentence": "（上司に）ご確認いただけますでしょうか。", "translation": "Could you please check this? (to superior)", "note": "double-polite layering"}]),
        ],
    },

    # ── Chinese (zh) ───────────────────────────────────────────────────────────
    "zh": {
        "A1": [
            ("sentence_structure", "SVO word order",
             "Chinese is strictly Subject-Verb-Object. Time and place typically precede the verb.",
             [{"sentence": "我吃饭。", "translation": "I eat (a meal).", "note": "basic SVO"},
              {"sentence": "我明天去学校。", "translation": "I go to school tomorrow.", "note": "time before verb"}]),
            ("particles", "Aspect particle 了 (le)",
             "Marks completion of an action (verbal 了) or a change of state (sentence-final 了).",
             [{"sentence": "我吃了。", "translation": "I have eaten.", "note": "verbal 了: completion"},
              {"sentence": "他来了。", "translation": "He has come (now).", "note": "sentence-final 了: change of state"}]),
            ("questions", "Yes/No questions with 吗 (ma)",
             "Add 吗 to end of a statement to form a yes/no question. No inversion.",
             [{"sentence": "你是学生吗？", "translation": "Are you a student?", "note": ""}]),
            ("negation", "Negation with 不 and 没",
             "不: negate present/future states and habitual actions. 没: negate past actions (with 了).",
             [{"sentence": "我不喝咖啡。", "translation": "I don't drink coffee.", "note": "不: habitual"},
              {"sentence": "我没去。", "translation": "I didn't go.", "note": "没: past negation"}]),
        ],
        "A2": [
            ("measure_words", "Measure words (量词)",
             "Every noun requires a specific measure word when counted. 个 is generic; others are noun-specific.",
             [{"sentence": "一本书 / 一杯水 / 一张纸", "translation": "one book / one cup of water / one sheet of paper", "note": "本/杯/张 are noun-specific"},
              {"sentence": "三个苹果", "translation": "three apples", "note": "个: generic measure word"}]),
            ("particles", "Aspect particle 过 (guo)",
             "Marks previous life experience. Often with 没 for negation.",
             [{"sentence": "我去过北京。", "translation": "I have been to Beijing (before).", "note": "experience"},
              {"sentence": "我没去过日本。", "translation": "I have never been to Japan.", "note": ""}]),
            ("particles", "Progressive aspect 在/正在 ... 着",
             "正在 or 在 before verb marks ongoing action; 着 after verb marks continuing state.",
             [{"sentence": "他正在吃饭。", "translation": "He is eating.", "note": "正在: ongoing"},
              {"sentence": "门开着。", "translation": "The door is open.", "note": "着: continuing state"}]),
            ("resultative_complements", "Resultative verb complements",
             "Verb + result complement: 吃完 (finish eating), 看懂 (understand after reading), 写好 (finish writing well).",
             [{"sentence": "我吃完了。", "translation": "I have finished eating.", "note": "完: completion"},
              {"sentence": "你听懂了吗？", "translation": "Did you understand (after listening)?", "note": "懂: comprehension"}]),
        ],
        "B1": [
            ("ba_construction", "把 (bǎ) construction",
             "Moves the object before the verb to emphasise disposition/handling of object: 把 + O + V + complement.",
             [{"sentence": "我把书放在桌子上。", "translation": "I put the book on the table.", "note": "把: object handled"},
              {"sentence": "把门关上。", "translation": "Close the door.", "note": "imperative"}]),
            ("bei_passive", "被 (bèi) passive",
             "被 + agent + verb (+ complement). Used for adverse or undesirable events.",
             [{"sentence": "我的自行车被人偷了。", "translation": "My bicycle was stolen.", "note": "adverse passive"},
              {"sentence": "他被老师批评了。", "translation": "He was criticized by the teacher.", "note": ""}]),
            ("complements", "Directional complements",
             "来/去 after verbs of motion indicate direction toward/away from speaker.",
             [{"sentence": "他走进来了。", "translation": "He walked in (toward here).", "note": "进来: enter → speaker"},
              {"sentence": "她跑出去了。", "translation": "She ran out (away).", "note": "出去: exit → away"}]),
            ("degree", "Degree complements with 得",
             "V + 得 + degree complement describes manner/degree of action.",
             [{"sentence": "她唱得很好。", "translation": "She sings very well.", "note": "degree: manner"},
              {"sentence": "他跑得太快了。", "translation": "He ran too fast.", "note": ""}]),
        ],
        "B2": [
            ("topic_comment", "Topic-comment structure",
             "Chinese frequently fronts a topic before the main SVO comment. Topic = what is talked about.",
             [{"sentence": "这本书，我已经看完了。", "translation": "This book, I have already finished reading.", "note": "topic fronted"},
              {"sentence": "中文，我觉得不太难。", "translation": "Chinese, I find not too difficult.", "note": ""}]),
            ("correlatives", "Correlative conjunctions",
             "虽然…但是 (although…but), 因为…所以 (because…therefore), 不但…而且 (not only…but also).",
             [{"sentence": "虽然很忙，但是我很开心。", "translation": "Although very busy, I am happy.", "note": ""},
              {"sentence": "因为下雨，所以我没去。", "translation": "Because it rained, I didn't go.", "note": ""}]),
        ],
        "C1": [
            ("classical_elements", "Classical Chinese elements in modern writing",
             "Four-character idioms (成语), classical conjunctions (然而, 故, 既…又), and abbreviations from wenyan.",
             [{"sentence": "半途而废是不可取的。", "translation": "Giving up halfway is unacceptable. (成语: 半途而废)", "note": "idiom in formal writing"}]),
            ("discourse", "Advanced discourse structure",
             "Academic Chinese uses 首先…其次…最后, 综上所述, 由此可见 to structure arguments.",
             [{"sentence": "综上所述，该方法具有重要意义。", "translation": "In summary, this method is of great significance.", "note": "formal academic"}]),
        ],
        "C2": [
            ("register", "Written vs spoken register",
             "Literary Chinese (书面语) vs colloquial (口语). Written uses longer nominal phrases, classical vocabulary.",
             [{"sentence": "目前 (written) / 现在 (spoken)", "translation": "currently / now", "note": "register contrast"}]),
        ],
    },

    # ── Arabic (ar) ────────────────────────────────────────────────────────────
    "ar": {
        "A1": [
            ("articles", "Definite article ال (al-)",
             "Prefixed to nouns. Assimilates to sun letters (الشمس aš-šams). No indefinite article; indefiniteness is unmarked.",
             [{"sentence": "الكتاب / كتاب", "translation": "the book / a book", "note": "definite / indefinite (unmarked)"},
              {"sentence": "الشمس / القمر", "translation": "the sun (aš-šams) / the moon", "note": "sun letter assimilation"}]),
            ("gender", "Grammatical gender",
             "Nouns are masculine or feminine. Feminine typically ends in ة (tā' marbūṭa) or is a naturally feminine concept.",
             [{"sentence": "مُعلِّم / مُعلِّمة", "translation": "male teacher / female teacher", "note": "ة marks feminine"}]),
            ("pronouns", "Personal pronouns",
             "أنا (I), أنتَ/أنتِ (you m/f), هو/هي (he/she), نحن (we), أنتم (you pl.), هم (they).",
             [{"sentence": "أنا طالب.", "translation": "I am a student. (m)", "note": "no copula in present"}]),
            ("sentence_structure", "Nominal sentence (جملة اسمية)",
             "Equational sentences: no verb. Subject + predicate. Verb optional in present.",
             [{"sentence": "البيتُ كبيرٌ.", "translation": "The house is big.", "note": "no verb"}]),
        ],
        "A2": [
            ("verb_tenses", "Perfect tense (الماضي)",
             "Marks completed actions. Conjugated by suffix: كتبَ (he wrote), كتبَتْ (she wrote), كتبتُ (I wrote).",
             [{"sentence": "ذهبَ إلى المدرسة.", "translation": "He went to school.", "note": "3rd m.sg. suffix: -a"},
              {"sentence": "أكلتُ التفاحة.", "translation": "I ate the apple.", "note": "1st sg. suffix: -tu"}]),
            ("verb_tenses", "Imperfect tense (المضارع)",
             "Non-past (present/future). Prefix + stem + suffix: يَكتُبُ (he writes), تَكتُبُ (she writes).",
             [{"sentence": "يَذهبُ إلى المدرسة.", "translation": "He goes to school.", "note": "prefix يَ- for 3rd m.sg."}]),
            ("dual", "Dual form (المثنى)",
             "Nouns and verbs have a dual form. Suffix ان- (nom.) / ين- (acc./gen.) for dual.",
             [{"sentence": "كتابان / كتابَين", "translation": "two books (nominative / accusative)", "note": "dual suffix"}]),
        ],
        "B1": [
            ("cases", "Case endings (الإعراب)",
             "Nominative ـُ (ḍamma), Accusative ـَ (fatḥa), Genitive ـِ (kasra). Tanwīn on indefinite: ـٌ/ـً/ـٍ.",
             [{"sentence": "جاء الطالبُ.", "translation": "The student came.", "note": "nominative: -u"},
              {"sentence": "رأيتُ الطالبَ.", "translation": "I saw the student.", "note": "accusative: -a"}]),
            ("broken_plurals", "Broken plurals (جمع التكسير)",
             "Arabic forms most plurals by changing the internal vowel pattern rather than adding a suffix.",
             [{"sentence": "كتاب → كتب / رجل → رجال / بيت → بيوت", "translation": "book→books / man→men / house→houses", "note": "each noun has its own pattern"}]),
            ("verb_forms", "Verb forms I-X (الأوزان)",
             "Arabic verbs are built on trilateral roots; 10 standard verb forms (وزن) with predictable meanings.",
             [{"sentence": "كَتَبَ (I: write) → كاتَبَ (III: correspond) → كَتَّبَ (II: cause to write)", "translation": "", "note": "root ك-ت-ب"}]),
        ],
        "B2": [
            ("relative_clauses", "Relative clauses (الجملة الوصفية)",
             "Definite antecedent: الذي/التي/الذين/اللواتي (who/which). Indefinite: no relative pronoun.",
             [{"sentence": "رأيتُ الرجلَ الذي يعملُ هنا.", "translation": "I saw the man who works here.", "note": "الذي: def. m.sg."},
              {"sentence": "رأيتُ رجلاً يعملُ هنا.", "translation": "I saw a man working here.", "note": "indef: no pronoun"}]),
            ("verb_forms", "Verbal noun (المصدر)",
             "Each verb form has a canonical verbal noun (gerund) used for abstract actions.",
             [{"sentence": "كِتابة (writing) / ذِهاب (going) / دِراسة (studying)", "translation": "", "note": "form I verbal nouns are unpredictable; higher forms follow patterns"}]),
        ],
        "C1": [
            ("msa_fusha", "Modern Standard Arabic vs dialects",
             "MSA (الفصحى) is the formal written/broadcast register; dialects vary greatly by region.",
             [{"sentence": "لا أعلم (MSA) / ما بعرف (Levantine) / ما نعرف (Moroccan)", "translation": "I don't know", "note": "register variation"}]),
        ],
        "C2": [
            ("classical_arabic", "Classical Arabic features",
             "Dual verb agreement, full إعراب, subjunctive (منصوب) and jussive (مجزوم) moods in formal writing.",
             [{"sentence": "لم يذهبْ.", "translation": "He did not go.", "note": "لم + jussive (مجزوم)"}]),
        ],
    },

    # ── Hebrew (he) ────────────────────────────────────────────────────────────
    "he": {
        "A1": [
            ("articles", "Definite article ה (ha-)",
             "Prefixed to noun with dagesh and usually a vowel change. Adjectives also take ה when noun is definite.",
             [{"sentence": "ספר / הספר", "translation": "a book / the book", "note": ""},
              {"sentence": "הבית הגדול", "translation": "the big house", "note": "adj also takes ה"}]),
            ("gender", "Noun gender",
             "Masculine unmarked; feminine typically ends in ה- or ת-. Adjectives agree in gender and number.",
             [{"sentence": "ילד גדול / ילדה גדולה", "translation": "a big boy / a big girl", "note": ""}]),
            ("pronouns", "Personal pronouns",
             "אני (I), אתה/את (you m/f), הוא/היא (he/she), אנחנו (we), אתם/אתן (you m.pl/f.pl), הם/הן (they m/f).",
             [{"sentence": "אני סטודנט.", "translation": "I am a student. (m)", "note": "no copula in present"}]),
            ("sentence_structure", "Nominal sentence",
             "Present-tense equational sentences use no copula: X + Y.",
             [{"sentence": "הבית גדול.", "translation": "The house is big.", "note": "no verb"}]),
        ],
        "A2": [
            ("verb_tenses", "Past tense (עבר) — binyan Pa'al",
             "Most basic binyan. Past: root vowel pattern + person suffixes: כתבתי / כתבת / כתב / כתבה...",
             [{"sentence": "כתבתי מכתב.", "translation": "I wrote a letter.", "note": "1sg past: -תי"},
              {"sentence": "היא הלכה הביתה.", "translation": "She went home.", "note": "3sg.f: -ה"}]),
            ("verb_tenses", "Present tense (הווה) — Pa'al",
             "Four forms: ms/fs/mp/fp: כותב / כותבת / כותבים / כותבות. Functions as present or participial adjective.",
             [{"sentence": "אני כותב מכתב.", "translation": "I am writing / I write a letter.", "note": "no aspect distinction in present"}]),
            ("construct_state", "Construct state (סמיכות)",
             "Noun + noun genitive compound: first noun (nomen regens) takes construct form. No ה on first noun.",
             [{"sentence": "בית הספר", "translation": "the school (lit: house of the book)", "note": "no ה on בית"},
              {"sentence": "ספר ילדים", "translation": "a children's book", "note": "indefinite construct"}]),
        ],
        "B1": [
            ("binyanim", "The binyan system — Pa'al, Nif'al, Pi'el",
             "Hebrew roots appear in seven binyanim with predictable meaning patterns. Pa'al: basic. Nif'al: passive/reflexive. Pi'el: intensive/causative.",
             [{"sentence": "כתב (Pa'al: wrote) / נכתב (Nif'al: was written) / כיתב (Pi'el: inscribed/wrote repeatedly)", "translation": "", "note": "root כ-ת-ב"},
              {"sentence": "שבר (Pa'al: broke) / נשבר (Nif'al: broke/was broken) / שיבר (Pi'el: smashed)", "translation": "", "note": "root ש-ב-ר"}]),
            ("verb_tenses", "Future tense (עתיד) — Pa'al",
             "Prefix pattern: אכתוב/תכתוב/יכתוב/תכתוב/נכתוב/תכתבו/יכתבו.",
             [{"sentence": "אני אכתוב מחר.", "translation": "I will write tomorrow.", "note": ""}]),
            ("prepositions", "Inseparable prepositions ב/ל/מ/כ",
             "Attached directly to noun, replacing ה: בבית = in the house; למדרגות = to the stairs.",
             [{"sentence": "אני גר בירושלים.", "translation": "I live in Jerusalem.", "note": "ב + ירושלים"},
              {"sentence": "הלכתי לשוק.", "translation": "I went to the market.", "note": "ל + שוק"}]),
        ],
        "B2": [
            ("binyanim", "Hif'il, Hitpa'el, Pu'al, Huf'al binyanim",
             "Hif'il: causative. Hitpa'el: reflexive/reciprocal. Pu'al/Huf'al: passive counterparts of Pi'el/Hif'il.",
             [{"sentence": "הכניס (Hif'il: caused to enter/introduced)", "translation": "", "note": "root כ-נ-ס"},
              {"sentence": "התלבש (Hitpa'el: dressed himself)", "translation": "", "note": "root ל-ב-ש"}]),
            ("relative_clauses", "Relative clauses with ש/אשר",
             "ש- (colloquial/modern) or אשר (formal) introduces relative clauses. Resumptive pronouns when needed.",
             [{"sentence": "האיש שדיברתי איתו", "translation": "the man I spoke with (lit: the man that I-spoke with-him)", "note": "resumptive pronoun: איתו"}]),
        ],
        "C1": [
            ("discourse", "Discourse connectors",
             "Formal: לפיכך, אולם, עם זאת, לעומת זאת, כלומר, דהיינו.",
             [{"sentence": "לפיכך, ניתן להסיק כי...", "translation": "Therefore, one can conclude that...", "note": "academic register"}]),
            ("register", "Biblical vs Modern Hebrew register",
             "Biblical roots and forms appear in formal/literary Modern Hebrew. ו-consecutive, construct chains.",
             [{"sentence": "בראשית ברא אלוהים", "translation": "In the beginning God created", "note": "literary/religious register"}]),
        ],
        "C2": [
            ("style", "Register mastery",
             "Distinguishing מליצי (flowery/biblical), ספרותי (literary), עיתונאי (journalistic), and שפת-רחוב (street language).",
             [{"sentence": "הלך לעולמו (euphemism) / מת (neutral) / נפטר (formal)", "translation": "passed away / died / passed away (formal)", "note": "register contrast"}]),
        ],
    },

    # ── Hindi (hi) ─────────────────────────────────────────────────────────────
    "hi": {
        "A1": [
            ("script", "Devanagari script basics",
             "Hindi is written in Devanagari script. Each character represents a syllable (consonant + inherent 'a'). Vowel signs (matras) modify the inherent vowel.",
             [{"sentence": "मैं घर जाता हूँ।", "translation": "I go home.", "note": "basic SVO sentence in Devanagari"}]),
            ("pronouns", "Personal pronouns",
             "मैं (I), तुम/आप (you informal/formal), वह (he/she/it), हम (we), वे (they). आप is the formal second-person form.",
             [{"sentence": "आप कहाँ हैं?", "translation": "Where are you?", "note": "formal second person"}]),
            ("verb_copula", "Copula है / हैं / था / थे",
             "है = is (3sg/2sg-formal present), हैं = are (plural/formal), था = was (masc sg), थे = were (masc pl/formal).",
             [{"sentence": "यह किताब है।", "translation": "This is a book.", "note": "present copula"},
              {"sentence": "वे घर पर थे।", "translation": "They were at home.", "note": "past copula"}]),
            ("nouns", "Gender: masculine and feminine",
             "Hindi nouns are grammatically masculine or feminine. Masculine sg often ends in -ā (आ), feminine sg often in -ī (ई). Agreement affects adjectives and verbs.",
             [{"sentence": "लड़का (masc) / लड़की (fem)", "translation": "boy / girl", "note": "gender contrast"}]),
        ],
        "A2": [
            ("postpositions", "Postpositions as case markers",
             "Hindi uses postpositions (not prepositions): ने (ergative), को (dative/accusative), से (from/by), में (in), पर (on/at), के लिए (for).",
             [{"sentence": "राम ने खाना खाया।", "translation": "Ram ate food.", "note": "ergative ने with past transitive"},
              {"sentence": "मुझे पानी चाहिए।", "translation": "I need water.", "note": "को/dative with psychological predicates"}]),
            ("verbs_habitual", "Habitual present: stem + -ता/-ती/-ते + है/हैं",
             "Expresses regular/habitual actions. Stem + -tā (masc sg) / -tī (fem) / -te (masc pl) + copula.",
             [{"sentence": "वह रोज़ आता है।", "translation": "He comes every day.", "note": "habitual masc sg"},
              {"sentence": "वे स्कूल जाते हैं।", "translation": "They go to school.", "note": "habitual masc pl"}]),
            ("verbs_past", "Past perfective: stem + -ā/-ī/-e",
             "Perfective past agrees with gender/number of the object (with transitive verbs + ने) or subject (intransitive).",
             [{"sentence": "सीता ने खाना खाया।", "translation": "Sita ate food.", "note": "transitive + ergative"},
              {"sentence": "वह घर गई।", "translation": "She went home.", "note": "intransitive fem"}]),
        ],
        "B1": [
            ("verbs_future", "Future tense: stem + -egā/-egī/-eṃge",
             "Four-way agreement by gender and number: -egā (masc sg), -egī (fem sg), -eṃge (masc pl), -eṃgī (fem pl).",
             [{"sentence": "वह आएगा।", "translation": "He will come.", "note": "masc sg future"},
              {"sentence": "वे आएंगी।", "translation": "They (fem) will come.", "note": "fem pl future"}]),
            ("compound_verbs", "Conjunct/compound verbs",
             "Light verbs (जाना, लेना, देना, आना, पड़ना) attach to verb stems to express aspect/modality. Very common in spoken Hindi.",
             [{"sentence": "वह खा गया।", "translation": "He ate (and went/completely).", "note": "completive aspect with जाना"},
              {"sentence": "मुझे बोलने दो।", "translation": "Let me speak.", "note": "permissive with देना"}]),
            ("honorifics", "Three-way honorific system",
             "तू (intimate/rude), तुम (informal), आप (formal/respectful). Verb and pronoun forms differ for each level.",
             [{"sentence": "आप क्या काम करते हैं?", "translation": "What work do you do? (formal)", "note": "आप = formal"}]),
        ],
        "B2": [
            ("subjunctive", "Subjunctive mood: stem + -e/-ẽ",
             "Expresses possibility, wish, polite request. Also used in subordinate clauses with कि.",
             [{"sentence": "शायद वह आए।", "translation": "Perhaps he may come.", "note": "possibility"},
              {"sentence": "मैं चाहता हूँ कि वह जाए।", "translation": "I want that he go.", "note": "subordinate subjunctive"}]),
            ("passive", "Passive constructions",
             "Formed with the past participle (verb stem + -ā) + जाना. Agent marked with के द्वारा or से.",
             [{"sentence": "खाना खाया जाता है।", "translation": "Food is eaten.", "note": "habitual passive"}]),
        ],
        "C1": [
            ("aspect", "Aspectual distinctions",
             "Hindi has rich aspectual marking: habitual (-tā), progressive (-rahā), perfective (-ā), inceptive (lagnā).",
             [{"sentence": "वह खा रहा था।", "translation": "He was eating.", "note": "past progressive"},
              {"sentence": "वह खाने लगा।", "translation": "He began eating.", "note": "inceptive"}]),
        ],
        "C2": [
            ("register", "Formal/written Hindi (shuddh Hindi)",
             "Formal Hindi uses tatsama (Sanskrit-derived) vocabulary and avoids Urdu/Persian loanwords. Contrast: पानी (informal/Urdu) vs. जल (formal/Sanskrit).",
             [{"sentence": "जल ही जीवन है।", "translation": "Water is life. (formal)", "note": "tatsama vocabulary"}]),
        ],
    },

    # ── Turkish (tr) ───────────────────────────────────────────────────────────
    "tr": {
        "A1": [
            ("script_alphabet", "Turkish Latin alphabet",
             "Turkish uses a modified Latin alphabet with ç, ğ, ı (dotless i), i (dotted), ö, ş, ü. The letter 'ğ' lengthens the preceding vowel and is nearly silent.",
             [{"sentence": "Ğ sesi uzatır: dağ, sağ.", "translation": "The ğ sound lengthens: mountain, healthy.", "note": "silent/lengthening ğ"}]),
            ("vowel_harmony", "Vowel harmony",
             "Suffixes change their vowels to match the last vowel of the stem. Back vowels (a/ı/o/u) require back-vowel suffixes; front vowels (e/i/ö/ü) require front-vowel suffixes.",
             [{"sentence": "ev + de = evde (in the house); araba + da = arabada (in the car)", "translation": "in the house; in the car", "note": "locative vowel harmony"}]),
            ("word_order", "SOV word order",
             "Turkish is Subject–Object–Verb. The verb comes last. Modifiers precede what they modify.",
             [{"sentence": "Ben kitabı okudum.", "translation": "I the-book read (I read the book).", "note": "SOV order"}]),
            ("copula", "Present copula: -dir/-dır/-dür/-dur or ∅",
             "Turkish does not require an overt copula in present tense. Third-person present is zero-marked or uses -(y)dı for past.",
             [{"sentence": "O öğrenci(dir).", "translation": "She is a student.", "note": "optional -dir in 3rd person"},
              {"sentence": "Ben öğrenciyim.", "translation": "I am a student.", "note": "1sg copula -yim"}]),
        ],
        "A2": [
            ("cases", "Six nominal cases",
             "Turkish nouns take case suffixes: nominative (∅), accusative (-ı/-i/-u/-ü), dative (-a/-e), locative (-da/-de/-ta/-te), ablative (-dan/-den/-tan/-ten), genitive (-ın/-in/-un/-ün).",
             [{"sentence": "ev (nom) / evi (acc) / eve (dat) / evde (loc) / evden (abl) / evin (gen)", "translation": "house in its six cases", "note": "case paradigm for 'ev' (house)"}]),
            ("plural", "Plural suffix -lar/-ler",
             "Plural is formed with -lar (after back vowels) or -ler (after front vowels). Plural is not used with numerals.",
             [{"sentence": "kitap → kitaplar; ev → evler", "translation": "book → books; house → houses", "note": "vowel harmony in plural"}]),
            ("verbs_present", "Progressive present: verb stem + -iyor + personal suffix",
             "-iyor expresses actions happening now. Four-way vowel harmony: -ıyor/-iyor/-uyor/-üyor.",
             [{"sentence": "Gidiyorum.", "translation": "I am going.", "note": "1sg progressive"},
              {"sentence": "Ne yapıyorsun?", "translation": "What are you doing?", "note": "2sg progressive"}]),
        ],
        "B1": [
            ("verbs_past", "Definite past: -dı/-di/-du/-dü (+ person endings)",
             "Expresses directly witnessed past events. Alternates by vowel harmony and voicing of final consonant.",
             [{"sentence": "Gitti.", "translation": "He/she went.", "note": "3sg past definite"},
              {"sentence": "Yedim.", "translation": "I ate.", "note": "1sg past definite"}]),
            ("verbs_evidential", "Evidential/reported past: -mış/-miş/-muş/-müş",
             "Expresses hearsay, inference, or past events not directly witnessed. Key distinction from -dı.",
             [{"sentence": "Gitmiş.", "translation": "He apparently went / I heard he went.", "note": "3sg evidential past"},
              {"sentence": "Uyumuşum.", "translation": "Apparently I fell asleep (I didn't notice).", "note": "1sg evidential — surprise/inference"}]),
            ("infinitive", "Verb infinitive: stem + -mak/-mek",
             "The citation form of Turkish verbs. -mak after back vowels, -mek after front vowels.",
             [{"sentence": "gitmek (to go), yemek (to eat), yapmak (to do)", "translation": "to go, to eat, to do", "note": "vowel harmony in infinitive"}]),
            ("negation", "Verbal negation: stem + -me/-ma",
             "Negation suffix precedes tense/person suffixes. Vowel harmony applies.",
             [{"sentence": "Gitme! / Gitmiyor.", "translation": "Don't go! / (He) is not going.", "note": "imperative negation / progressive negation"}]),
        ],
        "B2": [
            ("agglutination", "Agglutinative suffix stacking",
             "Multiple suffixes stack onto one stem. Order: stem + voice + negation + tense + person + question. E.g.: yap-abil-me-miş-ler-di-k.",
             [{"sentence": "yapamıyorum", "translation": "I am not able to do (it)", "note": "yap+abil+me+iyor+um — ability + negation + progressive + 1sg"},
              {"sentence": "evlerimizden", "translation": "from our houses", "note": "ev+ler+imiz+den — pl + 1pl.poss + ablative"}]),
            ("aorist", "Aorist / general present: -ar/-er/-ır/-ir",
             "Expresses habitual, general truths, and potential. Less frequent in spoken language than progressive.",
             [{"sentence": "Her sabah kahve içer.", "translation": "He drinks coffee every morning.", "note": "habitual aorist"}]),
        ],
        "C1": [
            ("subjunctive_cond", "Conditional mood: -sa/-se",
             "Verb stem + -sa/-se + person suffix. Expresses conditional/hypothetical. Often paired with -(y)dı for counterfactuals.",
             [{"sentence": "Gelseydin, görürdün.", "translation": "If you had come, you would have seen.", "note": "counterfactual conditional"}]),
        ],
        "C2": [
            ("register", "Ottoman loanwords and formal register",
             "Formal Turkish uses more Arabic/Persian loanwords (Ottoman heritage). Informal spoken Turkish prefers simpler Turkic roots. Contrast: istihdam (formal) vs. iş (casual) for employment.",
             [{"sentence": "müteşekkirim vs. teşekkür ederim", "translation": "I am grateful (formal) vs. thank you (standard)", "note": "formal Ottoman-derived form"}]),
        ],
    },

    # ── Finnish (fi) ───────────────────────────────────────────────────────────
    "fi": {
        "A1": [
            ("phonology", "Finnish vowel harmony",
             "Finnish has vowel harmony: back vowels (a, o, u) and front vowels (ä, ö, y) don't mix in native words. Suffixes use back vowels after back-vowel stems and front vowels after front-vowel stems.",
             [{"sentence": "talo+ssa = talossa (in the house); tyttö+ssä = tytössä (in the girl)", "translation": "in the house; in the girl", "note": "inessive vowel harmony"}]),
            ("word_order", "Flexible word order; SVO as default",
             "Finnish word order is relatively free because case suffixes mark grammatical roles. SVO is most neutral; SOV and VSO occur for emphasis.",
             [{"sentence": "Minä syön omenaa.", "translation": "I eat an apple.", "note": "basic SVO"}]),
            ("nouns_cases_intro", "Finnish cases overview",
             "Finnish has 15 grammatical cases marked by suffixes. The most common for beginners: nominative (subject), genitive (-n), partitive (-a/-ä/-ta/-tä), accusative (-n/-t), inessive (-ssa/-ssä), elative (-sta/-stä), allative (-lle), adessive (-lla/-llä), ablative (-lta/-ltä).",
             [{"sentence": "talo / talon / talossa / talosta / talolle", "translation": "house (nom/gen/inessive/elative/allative)", "note": "five common cases of 'talo'"}]),
        ],
        "A2": [
            ("partitive", "Partitive case: -a/-ä/-ta/-tä",
             "The partitive marks partial/indefinite quantity (vs. genitive/accusative for complete/definite). Also used after negation and with numbers > 1.",
             [{"sentence": "Juon kahvia. (partitive = some coffee) / Juo kahvi. (nom/acc = the coffee, all of it)", "translation": "I am drinking (some) coffee / Drink the coffee.", "note": "partitive vs. nominative contrast"},
              {"sentence": "Ei ole aikaa.", "translation": "There is no time.", "note": "partitive after negation"}]),
            ("verbs_present", "Present tense: personal endings",
             "Finnish verbs conjugate for person/number. Endings: -n (1sg), -t (2sg), -V (3sg = vowel lengthening), -mme (1pl), -tte (2pl), -vat/-vät (3pl).",
             [{"sentence": "menen / menet / menee / menemme / menette / menevät", "translation": "I go / you go / he goes / we go / you-pl go / they go", "note": "full paradigm of mennä (to go)"}]),
            ("negation", "Negation with ei/en/et/emme/ette/eivät",
             "Finnish negation uses a negative auxiliary that conjugates for person, followed by the bare (connective) form of the main verb.",
             [{"sentence": "En mene. / Hän ei mene.", "translation": "I don't go. / He/she doesn't go.", "note": "negative auxiliary + connective"}]),
        ],
        "B1": [
            ("past_tense", "Past tense: stem + -i- + personal endings",
             "Most Finnish verbs form the past by inserting -i- before personal endings. Consonant gradation and stem vowel changes frequently occur.",
             [{"sentence": "menen → menin (I went)", "translation": "I go → I went", "note": "past 1sg"},
              {"sentence": "lukea → luin (I read)", "translation": "read (inf) → I read (past)", "note": "stem change in past"}]),
            ("passive", "Passive voice: -taan/-tään/-daan/-dään",
             "Finnish passive is impersonal (no agent). Present passive: -taan/-tään. Past passive: -ttiin/-tiin. Very common in colloquial speech for first-person plural.",
             [{"sentence": "Syödään! (Passive)", "translation": "Let's eat! / We eat!", "note": "passive as inclusive 1pl in colloquial"},
              {"sentence": "Kirja luetaan.", "translation": "The book is read.", "note": "impersonal passive"}]),
            ("cases_local", "Local cases: six spatial cases",
             "Finnish has an inner and outer set of local cases. Inner: inessive (-ssa), elative (-sta), illative (-Vn/-hVn). Outer: adessive (-lla), ablative (-lta), allative (-lle).",
             [{"sentence": "talossa (in) / talosta (from inside) / taloon (into)", "translation": "in the house / from the house / into the house", "note": "inner local cases"},
              {"sentence": "pöydällä (on) / pöydältä (from) / pöydälle (onto)", "translation": "on the table / from the table / onto the table", "note": "outer local cases"}]),
        ],
        "B2": [
            ("conditional", "Conditional mood: -isi-",
             "Formed with -isi- between the verb stem and personal ending. Expresses hypothetical and polite requests.",
             [{"sentence": "Menisin, jos voisin.", "translation": "I would go if I could.", "note": "conditional + conditional"},
              {"sentence": "Voisitko auttaa?", "translation": "Could you help?", "note": "polite request with conditional"}]),
            ("consonant_gradation", "Consonant gradation (k→∅, p→v, t→d)",
             "A systematic alternation of consonants between strong and weak grades, triggered by syllable structure. E.g.: tyttö (sg nom) / tytön (sg gen) — tt→t. Makes Finnish morphology complex.",
             [{"sentence": "tyttö / tytön; pöytä / pöydän; kauppa / kaupan", "translation": "girl / of the girl; table / of the table; shop / of the shop", "note": "strong→weak gradation in genitive"}]),
        ],
        "C1": [
            ("verbal_nouns", "Verbal nouns and infinitives",
             "Finnish has multiple infinitives. The first infinitive (-a/-ä) is the citation form. The second infinitive (inessive -essa/-essä) expresses simultaneous action. Third infinitive cases (-massa/-mässä, -masta/-mästä, -maan/-mään) have specific meanings.",
             [{"sentence": "Lähtiessäni satoi. (2nd inf inessive)", "translation": "When I was leaving, it rained.", "note": "simultaneous action"},
              {"sentence": "Olen lukemassa.", "translation": "I am (in the process of) reading.", "note": "3rd inf inessive = progressive sense"}]),
        ],
        "C2": [
            ("register", "Spoken vs written Finnish",
             "Spoken (puhekieli) and written (kirjakieli/yleiskieli) Finnish differ significantly. Spoken: mä/sä/se (I/you/it), mennään (we go), ei oo (isn't). Written: minä/sinä/se, menemme, ei ole.",
             [{"sentence": "Mä en oo kotona. (spoken) / Minä en ole kotona. (written)", "translation": "I am not home.", "note": "spoken vs written contrast"}]),
        ],
    },

    # ── Latin (la) ─────────────────────────────────────────────────────────────
    "la": {
        "A1": [
            ("script", "Latin alphabet and macrons",
             "Latin uses the Roman alphabet (23 letters; no W, Y, Z in classical). Long vowels are marked with a macron (ā, ē, ī, ō, ū) in teaching texts; macrons affect pronunciation and meaning (e.g. mālum = apple vs. malum = evil).",
             [{"sentence": "amō, amāre, amāvī, amātum", "translation": "love, to love, I loved, loved", "note": "macrons on long vowels in principal parts"},
              {"sentence": "mālum vs. malum", "translation": "apple vs. evil", "note": "macron changes meaning"}]),
            ("word_order", "Default SOV word order",
             "Latin is typically Subject–Object–Verb, but word order is flexible because case endings carry grammatical roles. Verbs usually appear last; adjectives agree in case, number, and gender with the noun they modify.",
             [{"sentence": "Puella aquam amat.", "translation": "The girl loves water.", "note": "SOV: subject nominative, object accusative, verb final"},
              {"sentence": "Aquam puella amat.", "translation": "The girl loves water (emphasis on water).", "note": "word order shift for emphasis"}]),
            ("esse", "Esse — to be: present indicative",
             "Sum, es, est, sumus, estis, sunt. Highly irregular; memorise as a unit. Esse is used as a copula and as an auxiliary for perfect passive.",
             [{"sentence": "Homo sum.", "translation": "I am a human.", "note": "1sg present"},
              {"sentence": "Discipuli sumus.", "translation": "We are students.", "note": "1pl present"},
              {"sentence": "Deus est.", "translation": "God exists.", "note": "3sg predicate use"}]),
            ("1st_declension", "First declension feminine nouns",
             "Nouns ending in -a (nom. sg.) belong to the 1st declension, mostly feminine. Key endings: nom. -a, gen. -ae, dat. -ae, acc. -am, abl. -ā, nom. pl. -ae, gen. pl. -ārum, acc. pl. -ās.",
             [{"sentence": "puella, puellae, puellae, puellam, puellā", "translation": "girl (nom/gen/dat/acc/abl sg)", "note": "1st declension singular paradigm"},
              {"sentence": "aqua, terra, via, vita, luna", "translation": "water, earth, road, life, moon", "note": "common 1st declension nouns"}]),
        ],
        "A2": [
            ("2nd_declension", "Second declension masculine and neuter",
             "Masculine nouns end in -us (nom. sg.); neuter in -um. Key masculine endings: nom. -us, gen. -ī, dat. -ō, acc. -um, abl. -ō. Neuter nom./acc. are identical: nom. -um, gen. -ī.",
             [{"sentence": "amicus, amicī, amicō, amicum, amicō", "translation": "friend (nom/gen/dat/acc/abl)", "note": "2nd decl. masc."},
              {"sentence": "bellum, bellī, bellō, bellum, bellō", "translation": "war (nom/gen/dat/acc/abl)", "note": "2nd decl. neut. nom=acc"}]),
            ("cases", "The six-case system",
             "Nominative (subject), Genitive (possession), Dative (indirect object), Accusative (direct object, motion-toward), Ablative (separation, means, manner), Vocative (address). No article; case endings replace it.",
             [{"sentence": "Rex (nom.) videt reginam (acc.).", "translation": "The king sees the queen.", "note": "subject nom, object acc"},
              {"sentence": "Amor patriae (gen.).", "translation": "Love of the fatherland.", "note": "genitive of possession"},
              {"sentence": "In viā (abl.) ambulat.", "translation": "He walks in the road.", "note": "ablative of place where"}]),
            ("1st_2nd_conj_present", "First and second conjugation: present active indicative",
             "1st conj. (amō): amō, amās, amat, amāmus, amātis, amant. 2nd conj. (moneō): moneō, monēs, monet, monēmus, monētis, monent. Personal endings: -ō/-m, -s, -t, -mus, -tis, -nt.",
             [{"sentence": "Amō, amās, amat, amāmus, amātis, amant.", "translation": "I love, you love, he loves, we love, you (pl.) love, they love.", "note": "1st conj. present"},
              {"sentence": "Videō patriam.", "translation": "I see the fatherland.", "note": "2nd conj. 1sg present"}]),
        ],
        "B1": [
            ("perfect_active", "Perfect active indicative: -ī ending",
             "The perfect tense uses a separate stem (3rd principal part). Endings: -ī, -istī, -it, -imus, -istis, -ērunt/-ēre. Expresses completed action; equivalent to English simple past or present perfect.",
             [{"sentence": "Amāvī patriam.", "translation": "I loved / I have loved the fatherland.", "note": "perfect: love, simple past"},
              {"sentence": "Vēnī, vīdī, vīcī.", "translation": "I came, I saw, I conquered.", "note": "Caesar's perfect forms — suppletive stems"}]),
            ("imperfect", "Imperfect active: -bam/-bās/-bat suffix",
             "The imperfect expresses ongoing or habitual action in the past. Formed by adding -bam (1sg), -bās (2sg), -bat (3sg), -bāmus (1pl), -bātis (2pl), -bant (3pl) to the present stem.",
             [{"sentence": "Amābam puellam.", "translation": "I was loving / used to love the girl.", "note": "imperfect ongoing action"},
              {"sentence": "Pueri in viā ambulābant.", "translation": "The boys were walking in the road.", "note": "imperfect 3pl"}]),
            ("3rd_declension", "Third declension consonant-stem nouns",
             "The largest declension; nominative forms vary greatly. Key: gen. sg. always -is. Includes rex/rēgis, homo/hominis, pax/pācis, corpus/corporis.",
             [{"sentence": "rex, rēgis, rēgī, rēgem, rēge", "translation": "king (nom/gen/dat/acc/abl)", "note": "3rd decl. cons. stem"},
              {"sentence": "corpus, corporis, corporī, corpus, corpore", "translation": "body (5 cases)", "note": "s-stem neuter: nom=acc"}]),
            ("3rd_4th_conj", "Third and fourth conjugation verbs",
             "3rd conj. (legō): legō, legis, legit, legimus, legitis, legunt. Short -e- in stem often weakens. 4th conj. (audiō): audiō, audīs, audit, audīmus, audītis, audiunt.",
             [{"sentence": "Legimus librum.", "translation": "We read the book.", "note": "3rd conj. 1pl"},
              {"sentence": "Audio vocem.", "translation": "I hear the voice.", "note": "4th conj. 1sg"}]),
        ],
        "B2": [
            ("subjunctive", "Present and imperfect subjunctive",
             "Present subjunctive 1st conj.: amē, amēs, amet… (drop -āre, add -ē-). 2nd/3rd/4th: add -ā-. Imperfect subjunctive: present infinitive + personal endings (amārem, amārēs…). Used in purpose/result/indirect question clauses.",
             [{"sentence": "Veniō ut videam.", "translation": "I come in order to see.", "note": "purpose clause: ut + present subjunctive"},
              {"sentence": "Rogō quid ageret.", "translation": "I ask what he was doing.", "note": "indirect question: imperfect subj."}]),
            ("passive_voice", "Present and imperfect passive",
             "Passive personal endings replace active: -r (1sg), -ris/-re (2sg), -tur (3sg), -mur (1pl), -minī (2pl), -ntur (3pl). Imperfect passive: -bātur, -bantur etc.",
             [{"sentence": "Laudātur a magistrō.", "translation": "He is praised by the teacher.", "note": "present passive 3sg; agent in ablative"},
              {"sentence": "Bellum gerēbātur.", "translation": "War was being waged.", "note": "imperfect passive 3sg"}]),
            ("gerund_gerundive", "Gerund and gerundive",
             "Gerund: verbal noun in oblique cases (gen. amandī, dat. amandō, acc. amandum, abl. amandō). Gerundive (verbal adjective): -ndus/-nda/-ndum, agrees with noun; expresses obligation or purpose.",
             [{"sentence": "Discendī causā.", "translation": "For the sake of learning.", "note": "gerund: gen. sg."},
              {"sentence": "Carthāgō dēlenda est.", "translation": "Carthage must be destroyed.", "note": "gerundive + esse = obligation"}]),
        ],
        "C1": [
            ("indirect_statement", "Indirect statement: accusative + infinitive",
             "After verbs of saying, thinking, knowing: the subject of the subordinate verb takes the accusative, and its predicate is an infinitive (present, perfect, or future). Tense is relative to the main verb.",
             [{"sentence": "Dīcō Rōmam esse magnam.", "translation": "I say that Rome is great.", "note": "acc. + present inf.: subject acc. Rōmam"},
              {"sentence": "Crēdō eum vēnisse.", "translation": "I believe that he came.", "note": "perfect inf.: action before main verb"}]),
            ("ablative_absolute", "Ablative absolute construction",
             "A noun/pronoun + participle (or second noun) in the ablative, with no grammatical connection to the main clause. Expresses time, cause, or circumstance.",
             [{"sentence": "Caesare duce, Rōmānī vīcērunt.", "translation": "With Caesar as leader, the Romans conquered.", "note": "ablative absolute: noun + noun"},
              {"sentence": "Hostibus victīs, exercitus rediit.", "translation": "The enemy having been defeated, the army returned.", "note": "ablative absolute: noun + participle"}]),
            ("conditionals", "Conditional sentences",
             "Three main types: (1) simple/open: sī + indicative; (2) less vivid future: sī + present subj., future perf. + present subj.; (3) contrary-to-fact: sī + imperfect subj. (present) or pluperfect subj. (past).",
             [{"sentence": "Sī hoc facis, errās.", "translation": "If you do this, you are wrong.", "note": "open condition: indicative"},
              {"sentence": "Sī hoc facerēs, errārēs.", "translation": "If you were doing this, you would be wrong.", "note": "contrary-to-fact present: imperfect subj."}]),
        ],
        "C2": [
            ("deponent", "Deponent verbs — passive form, active meaning",
             "Deponents have only passive forms but active meaning. Principal parts: pres. 1sg (-or), inf. (-ī), perf. 1sg (-us sum). Common: loquor (speak), sequor (follow), patior (suffer), morior (die).",
             [{"sentence": "Loquitur Latīnē.", "translation": "He speaks Latin.", "note": "deponent 3sg — passive form, active meaning"},
              {"sentence": "Secūtus est ducem.", "translation": "He followed the leader.", "note": "deponent perfect: participle + esse"}]),
            ("register", "Classical vs. ecclesiastical and medieval Latin",
             "Classical Latin (Cicero, Virgil) prizes periodic structure, periodic sentences, avoidance of hiatus. Ecclesiastical Latin (Vulgate, liturgy) uses simpler syntax, Greek loanwords, and quia/quoniam for indirect statement. Medieval Latin introduces new vocabulary for feudal institutions.",
             [{"sentence": "In principio erat Verbum (Vulgate John 1:1)", "translation": "In the beginning was the Word.", "note": "Ecclesiastical Latin: erat + nom. predicate"},
              {"sentence": "Gallia est omnis dīvīsa in partēs trēs. (Caesar)", "translation": "All of Gaul is divided into three parts.", "note": "Classical Latin periodic opening"}]),
        ],
    },

    # ── Koine Greek (grc) ──────────────────────────────────────────────────────
    "grc": {
        "A1": [
            ("alphabet", "Greek alphabet and pronunciation",
             "24 letters; key letters that differ from Latin: α β γ δ ε ζ η θ ι κ λ μ ν ξ ο π ρ σ/ς τ υ φ χ ψ ω. η = long e (ē), ω = long o (ō), θ = th, φ = ph, χ = ch (k-sound). Final sigma ς appears at word-end.",
             [{"sentence": "ἐν ἀρχῇ ἦν ὁ λόγος", "translation": "In the beginning was the Word (John 1:1)", "note": "all five accents (acute, grave, circumflex) and rough breathing visible"},
              {"sentence": "θεός, φωνή, χάρις", "translation": "god, voice, grace", "note": "θ=th, φ=ph, χ=ch"}]),
            ("article", "Definite article ὁ/ἡ/τό",
             "Greek has a definite article that inflects for gender (M/F/N), number (sg/pl), and case (nom/gen/dat/acc — no vocative). No indefinite article. Article can turn any word into a noun (substantivization) and mark attributive position.",
             [{"sentence": "ὁ θεός, ἡ ζωή, τὸ πνεῦμα", "translation": "the god, the life, the spirit", "note": "three genders of the article"},
              {"sentence": "ὁ ἀγαθός / ἀγαθός", "translation": "the good man / a good man (or: good man attributive)", "note": "article marks attributive vs. predicative"}]),
            ("eimi", "Εἰμί — to be: present indicative",
             "εἰμί (I am), εἶ (you are), ἐστίν (he/she/it is), ἐσμέν (we are), ἐστέ (you pl. are), εἰσίν (they are). Highly irregular; memorise as a paradigm. Often omitted (verbless clause).",
             [{"sentence": "ὁ θεὸς ἀγάπη ἐστίν.", "translation": "God is love.", "note": "3sg copula with predicate nominative"},
              {"sentence": "ἐγώ εἰμι ἡ ὁδός.", "translation": "I am the way.", "note": "1sg copula — emphatic ἐγώ"}]),
            ("word_order", "Flexible word order; emphasis and the article",
             "Greek word order is flexible; the article and case endings (not position) signal grammatical function. First and last positions are emphatic. Attributive adjective: article–adj–noun. Predicative: adj without article.",
             [{"sentence": "ὁ ἀγαθὸς ἄνθρωπος", "translation": "the good man (attributive)", "note": "article before adjective = attributive"},
              {"sentence": "ἀγαθὸς ὁ ἄνθρωπος", "translation": "the man is good (predicative)", "note": "no article before adjective = predicative"}]),
        ],
        "A2": [
            ("declensions", "Three declension system",
             "1st decl. (mostly fem., ἡ ζωή): nom. -η/-α, gen. -ης/-ας, dat. -ῃ/-ᾳ, acc. -ην/-αν. 2nd decl. (mostly masc., ὁ λόγος; neut. τὸ ἔργον): nom. -ος, gen. -ου, dat. -ῳ, acc. -ον. 3rd decl. (mixed): identify from gen. sg.",
             [{"sentence": "ζωή, ζωῆς, ζωῇ, ζωήν", "translation": "life (nom/gen/dat/acc sg)", "note": "1st decl. fem."},
              {"sentence": "λόγος, λόγου, λόγῳ, λόγον", "translation": "word (nom/gen/dat/acc sg)", "note": "2nd decl. masc."}]),
            ("present_active", "Present active indicative of -ω verbs",
             "λύω paradigm: λύω, λύεις, λύει, λύομεν, λύετε, λύουσιν. Primary active endings: -ω/-ω, -εις, -ει, -ομεν, -ετε, -ουσιν. The present expresses ongoing or repeated action (imperfective aspect).",
             [{"sentence": "πιστεύω εἰς τὸν θεόν.", "translation": "I believe in God.", "note": "1sg present active"},
              {"sentence": "ἀκούεις τὴν φωνήν;", "translation": "Do you hear the voice?", "note": "2sg present active"}]),
            ("cases", "Five cases and their uses",
             "Nominative (subject), Genitive (possession, separation, agent in passive), Dative (indirect object, means, sphere), Accusative (direct object, extent, motion-toward), Vocative (address). Greek lost the ablative (absorbed into genitive) that Latin has.",
             [{"sentence": "ὁ θεὸς ἀγαπᾷ τὸν κόσμον.", "translation": "God loves the world.", "note": "nom. subject, acc. direct object"},
              {"sentence": "ἡ ἀγάπη τοῦ θεοῦ", "translation": "the love of God", "note": "genitive of possession/source"}]),
            ("contract_verbs", "Contract verbs: -έω, -άω, -όω",
             "Vowel stems contract when followed by another vowel in the ending. ἀγαπάω: ἀγαπῶ, ἀγαπᾷς, ἀγαπᾷ, ἀγαπῶμεν… ποιέω: ποιῶ, ποιεῖς, ποιεῖ, ποιοῦμεν… Very common in NT.",
             [{"sentence": "ἀγαπῶ τὸν κύριον.", "translation": "I love the Lord.", "note": "ἀγαπάω contracted 1sg"},
              {"sentence": "ποιεῖτε ταῦτα.", "translation": "Do these things.", "note": "ποιέω contracted 2pl"}]),
        ],
        "B1": [
            ("aorist", "First and second aorist — simple past aspect",
             "First (sigmatic) aorist: ἔ- (augment) + stem + -σα (1sg) e.g. ἔλυσα. Second aorist: irregular stem change, same endings as imperfect: ἔλαβον (λαμβάνω), ἦλθον (ἔρχομαι), εἶπον (λέγω). Aorist expresses a simple punctiliar past action.",
             [{"sentence": "ἔλυσα τὸν δοῦλον.", "translation": "I freed the slave.", "note": "1st aorist 1sg"},
              {"sentence": "ἦλθεν εἰς τὴν οἰκίαν.", "translation": "He came into the house.", "note": "2nd aorist of ἔρχομαι"}]),
            ("middle_voice", "Middle voice — action affecting the subject",
             "Middle voice: subject acts on itself or for its own benefit. In NT, many verbs are deponent (middle/passive form, active meaning): ἔρχομαι (come), γίνομαι (become), ἀποκρίνομαι (answer).",
             [{"sentence": "λούομαι τὸ σῶμα.", "translation": "I wash my body.", "note": "middle: action benefits subject"},
              {"sentence": "ἀπεκρίνατο αὐτοῖς.", "translation": "He answered them.", "note": "deponent: middle form, active meaning"}]),
            ("participles", "Participles: attributive and circumstantial",
             "Participles are verbal adjectives; they agree in gender, number, case with their referent. Attributive (with article): ὁ πιστεύων = the one who believes. Circumstantial (no article): modifies the main verb.",
             [{"sentence": "ὁ πιστεύων εἰς ἐμὲ ἔχει ζωὴν αἰώνιον.", "translation": "The one who believes in me has eternal life.", "note": "attributive participle as subject"},
              {"sentence": "ταῦτα εἰπὼν ἀπῆλθεν.", "translation": "Having said these things, he departed.", "note": "circumstantial aorist participle"}]),
        ],
        "B2": [
            ("perfect_tense", "Perfect tense — stative aspect",
             "Greek perfect expresses a present state resulting from a past action. Formed with reduplication (first consonant + ε) + perfect stem + -κα endings. λέλυκα = I have loosed (and it is loosed). Pluperfect: past state.",
             [{"sentence": "γέγραπται: 'Οὐκ ἐπ᾿ ἄρτῳ μόνῳ ζήσεται ἄνθρωπος.'", "translation": "It is written: 'Man shall not live by bread alone.'", "note": "perfect passive of γράφω — scripture as permanent state"},
              {"sentence": "πεπίστευκα εἰς τὸν κύριον.", "translation": "I have believed (and now stand in faith) in the Lord.", "note": "perfect: present stative result"}]),
            ("optative", "Optative mood — wish and potential",
             "The optative expresses wish (μὴ γένοιτο = may it not be!), indirect discourse in secondary sequence, and conditions (less vivid). Less common in NT than in Classical; most NT optatives are in wish formulas.",
             [{"sentence": "μὴ γένοιτο!", "translation": "May it not be! / God forbid!", "note": "common NT optative of wish (Paul's letters)"},
              {"sentence": "Τί οὖν ἐροῦμεν; μὴ ἀδικία παρὰ τῷ θεῷ; μὴ γένοιτο.", "translation": "What then shall we say? Is there injustice with God? By no means!", "note": "rhetorical use"}]),
            ("genitive_absolute", "Genitive absolute",
             "A noun/pronoun + participle in the genitive, grammatically independent from the main clause. Expresses attendant circumstance, time, or cause — like the Latin ablative absolute.",
             [{"sentence": "ἐλθόντος αὐτοῦ εἰς Καφαρναούμ, προσῆλθον αὐτῷ.", "translation": "When he had come to Capernaum, they approached him.", "note": "genitive absolute: time clause"},
              {"sentence": "ταῦτα δὲ αὐτοῦ λαλοῦντος, πολλοὶ ἐπίστευσαν.", "translation": "While he was saying these things, many believed.", "note": "genitive absolute: circumstance"}]),
        ],
        "C1": [
            ("conditional", "Four types of Greek conditionals",
             "1. Simple/real (εἰ + indicative, indicative): 'If this is true, it is.' 2. Future more vivid (ἐάν/ἄν + subj., future): 'If he comes, we will see.' 3. Present contrary-to-fact (εἰ + imperfect indic., imperfect + ἄν): 'If he were here, I would see him.' 4. Past contrary-to-fact (εἰ + pluperfect/aorist indic., aorist + ἄν).",
             [{"sentence": "ἐὰν ὁμολογῶμεν τὰς ἁμαρτίας ἡμῶν, πιστός ἐστιν.", "translation": "If we confess our sins, he is faithful (1 John 1:9)", "note": "future more vivid: ἐάν + subj., present indicative"},
              {"sentence": "εἰ ἦτε ἐκ τοῦ κόσμου, ὁ κόσμος ἂν τὸ ἴδιον ἐφίλει.", "translation": "If you were of the world, the world would love its own (John 15:19)", "note": "contrary-to-fact: εἰ + imperfect, imperfect + ἄν"}]),
            ("infinitive_articular", "Articular infinitive with τοῦ/τό",
             "The infinitive preceded by the article functions as a verbal noun in various cases. τοῦ + inf. = genitive (purpose, result, description). τό + inf. = accusative (subject or object of verb). Very common in Paul.",
             [{"sentence": "ἐμοὶ τὸ ζῆν Χριστός. (Phil 1:21)", "translation": "For me, to live is Christ.", "note": "articular inf. τό + ζῆν as subject"},
              {"sentence": "ἦλθεν τοῦ σῴζειν.", "translation": "He came to save.", "note": "genitive articular inf. of purpose"}]),
            ("indirect_discourse", "Indirect discourse constructions",
             "After verbs of saying/thinking: (a) ὅτι/ὡς + indicative (most common in Koine); (b) accusative + infinitive (Classical; occasional in NT); (c) participle (with ὁράω, οἶδα etc.).",
             [{"sentence": "λέγει ὅτι ὁ θεὸς ἀγαπᾷ τὸν κόσμον.", "translation": "He says that God loves the world.", "note": "ὅτι + indicative — most common NT construction"},
              {"sentence": "οἶδα ὅτι ἀναστήσεται.", "translation": "I know that he will rise again.", "note": "ὅτι + indicative with future"}]),
        ],
        "C2": [
            ("koine_vs_classical", "Koine features vs. Classical Attic",
             "NT Koine differs from Attic: (1) ἵνα + subjunctive replaces infinitive for purpose and indirect command; (2) increased use of ὅτι for indirect statement; (3) optative is rare; (4) εἰς + accusative often replaces dative; (5) Semitic influence (Hebraisms) in Gospels and Revelation.",
             [{"sentence": "ἐντέλλομαί σοι ἵνα ἀγαπᾶτε ἀλλήλους. (John 15:17)", "translation": "I command you to love one another.", "note": "Koine: ἵνα + subj. instead of Classical infinitive"},
              {"sentence": "καὶ ἐγένετο… (narrative ἐγένετο)", "translation": "And it came to pass…", "note": "Hebraism: ויהי → ἐγένετο as narrative opener in Luke-Acts"}]),
            ("aspect", "Verbal aspect — imperfective vs. perfective vs. stative",
             "Greek verbs encode aspect: imperfective (present/imperfect: ongoing or repeated action), perfective/aoristic (aorist: simple whole action), stative (perfect: resulting state). Tense-form choice conveys the writer's perspective on how an action unfolds.",
             [{"sentence": "ἔλεγεν (impf) vs. εἶπεν (aor)", "translation": "he was saying (ongoing) vs. he said (simple)", "note": "same verb, different aspect: process vs. event"},
              {"sentence": "γέγραπται (pf. pass.): it stands written", "translation": "permanent authority: the text stands as written", "note": "perfect stative: ongoing relevance of completed writing"}]),
        ],
    },
}

# ── Database helpers ───────────────────────────────────────────────────────────

UPSERT_VOCAB = """
INSERT INTO vocabulary_entries (language, lemma, pos, cefr_level, definition, frequency_rank, source)
VALUES (:language, :lemma, :pos, :cefr_level, :definition, :frequency_rank, :source)
ON CONFLICT (language, lemma, pos)
DO UPDATE SET
    cefr_level     = EXCLUDED.cefr_level,
    definition     = COALESCE(EXCLUDED.definition, vocabulary_entries.definition),
    frequency_rank = COALESCE(EXCLUDED.frequency_rank, vocabulary_entries.frequency_rank),
    source         = EXCLUDED.source
"""

UPSERT_GRAMMAR = """
INSERT INTO grammar_rules (language, cefr_level, category, name, description, examples, source)
VALUES (:language, :cefr_level, :category, :name, :description, CAST(:examples AS jsonb), :source)
ON CONFLICT (language, cefr_level, name)
DO UPDATE SET
    category    = EXCLUDED.category,
    description = EXCLUDED.description,
    examples    = EXCLUDED.examples,
    source      = EXCLUDED.source
"""

# ── Core routines ─────────────────────────────────────────────────────────────

async def load_grammar_rules(
    session: AsyncSession,
    languages: list[str],
    levels: list[str],
    dry_run: bool,
) -> None:
    total = 0
    for lang in languages:
        rules_by_level = _GRAMMAR.get(lang)
        if not rules_by_level:
            log.warning("  no grammar rules defined for '%s', skipping", lang)
            continue
        for level, rules in rules_by_level.items():
            if level not in levels:
                continue
            for category, name, description, examples in rules:
                total += 1
                if not dry_run:
                    import json
                    await session.execute(
                        text(UPSERT_GRAMMAR),
                        {
                            "language": lang,
                            "cefr_level": level,
                            "category": category,
                            "name": name,
                            "description": description,
                            "examples": json.dumps(examples, ensure_ascii=False),
                            "source": SOURCE_GRAMMAR,
                        },
                    )
        if not dry_run:
            await session.commit()
        log.info("  %s grammar rules for '%s' (%s)", "would insert" if dry_run else "upserted", lang, "levels: " + ",".join(levels))
    log.info("Grammar: %d rules total", total)


async def load_japanese_vocab(
    session: AsyncSession,
    levels: list[str],
    fetch_defs: bool,
    dry_run: bool,
    client: httpx.AsyncClient,
) -> None:
    log.info("Japanese (ja): loading JLPT vocabulary")
    count = 0
    for level, words in _JLPT.items():
        if level not in levels:
            continue
        for word in words:
            definition: str | None = None
            if fetch_defs:
                definition = await fetch_definition(client, word, "ja")
            count += 1
            if not dry_run:
                await session.execute(
                    text(UPSERT_VOCAB),
                    {
                        "language": "ja",
                        "lemma": word,
                        "pos": None,
                        "cefr_level": level,
                        "definition": definition,
                        "frequency_rank": None,
                        "source": SOURCE_JLPT,
                    },
                )
    if not dry_run:
        await session.commit()
    log.info("  ja: %d words (%s)", count, "dry-run" if dry_run else "upserted")


async def load_chinese_vocab(
    session: AsyncSession,
    levels: list[str],
    fetch_defs: bool,
    dry_run: bool,
    client: httpx.AsyncClient,
) -> None:
    log.info("Chinese (zh): loading HSK vocabulary")
    count = 0
    for level, words in _HSK.items():
        if level not in levels:
            continue
        for word in words:
            definition: str | None = None
            if fetch_defs:
                definition = await fetch_definition(client, word, "zh")
            count += 1
            if not dry_run:
                await session.execute(
                    text(UPSERT_VOCAB),
                    {
                        "language": "zh",
                        "lemma": word,
                        "pos": None,
                        "cefr_level": level,
                        "definition": definition,
                        "frequency_rank": None,
                        "source": SOURCE_HSK,
                    },
                )
    if not dry_run:
        await session.commit()
    log.info("  zh: %d words (%s)", count, "dry-run" if dry_run else "upserted")


async def load_inline_vocab(
    lang: str,
    vocab: dict[str, list[tuple[str, str, str]]],
    session: AsyncSession,
    levels: list[str],
    fetch_defs: bool,
    dry_run: bool,
    client: httpx.AsyncClient,
) -> None:
    """Load a curated inline vocabulary dict (lemma, pos, gloss per entry)."""
    log.info("%s: loading curated inline vocabulary", lang)
    count = 0
    for level, entries in vocab.items():
        if level not in levels:
            continue
        for lemma, pos, gloss in entries:
            definition: str | None = gloss
            if fetch_defs:
                fetched = await fetch_definition(client, lemma, lang)
                if fetched:
                    definition = fetched
            count += 1
            if not dry_run:
                await session.execute(
                    text(UPSERT_VOCAB),
                    {
                        "language": lang,
                        "lemma": lemma,
                        "pos": pos,
                        "cefr_level": level,
                        "definition": definition,
                        "frequency_rank": None,
                        "source": SOURCE_CURATED,
                    },
                )
    if not dry_run:
        await session.commit()
    log.info("  %s: %d words (%s)", lang, count, "dry-run" if dry_run else "upserted")


async def load_freq_vocab(
    lang: str,
    fw_lang: str,
    session: AsyncSession,
    levels: list[str],
    fetch_defs: bool,
    dry_run: bool,
    client: httpx.AsyncClient,
) -> None:
    log.info("%s (%s): fetching frequency list", lang, fw_lang)
    words = await fetch_freq_list(client, fw_lang)
    if not words:
        log.warning("  %s: empty frequency list, skipping", lang)
        return

    # Determine which ranks to harvest given requested levels
    max_rank_needed = 0
    for limit, level in _CEFR_THRESHOLDS:
        if level in levels:
            max_rank_needed = limit

    batch: list[dict] = []
    for rank, word in words:
        if rank > max_rank_needed:
            break
        level = cefr_for_rank(rank)
        if level is None or level not in levels:
            continue
        definition: str | None = None
        if fetch_defs and rank <= 1500:  # only fetch defs for A1/A2 to limit API calls
            definition = await fetch_definition(client, word, lang)
        batch.append({
            "language": lang,
            "lemma": word,
            "pos": None,
            "cefr_level": level,
            "definition": definition,
            "frequency_rank": rank,
            "source": SOURCE_VOCAB,
        })
        if len(batch) >= 500 and not dry_run:
            for row in batch:
                await session.execute(text(UPSERT_VOCAB), row)
            await session.commit()
            batch.clear()

    if batch and not dry_run:
        for row in batch:
            await session.execute(text(UPSERT_VOCAB), row)
        await session.commit()

    harvested = sum(1 for r, _ in words if cefr_for_rank(r) in levels and r <= max_rank_needed)
    log.info("  %s: %d words (%s)", lang, harvested, "dry-run" if dry_run else "upserted")


# ── Main entry point ─────────────────────────────────────────────────────────

ALL_LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ar", "he",
                 "hi", "tr", "fi", "la", "grc"]
ALL_LEVELS    = ["A1", "A2", "B1", "B2", "C1", "C2"]


async def run(
    languages: list[str],
    levels: list[str],
    skip_vocab: bool,
    skip_grammar: bool,
    skip_definitions: bool,
    dry_run: bool,
) -> None:
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        log.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # type: ignore[call-overload]

    fetch_defs = not skip_definitions

    async with async_session() as session:
        async with httpx.AsyncClient(
            headers={"User-Agent": "Mnemosyne-Harvester/1.0 (language learning app; contact: paul_schleifer@hotmail.com)"},
        ) as client:

            if not skip_grammar:
                log.info("=== Grammar rules ===")
                await load_grammar_rules(session, languages, levels, dry_run)

            if not skip_vocab:
                log.info("=== Vocabulary ===")
                for lang in languages:
                    if lang == "ja":
                        await load_japanese_vocab(session, levels, fetch_defs, dry_run, client)
                    elif lang == "zh":
                        await load_chinese_vocab(session, levels, fetch_defs, dry_run, client)
                    elif lang == "la":
                        await load_inline_vocab("la", _LATIN_VOCAB, session, levels, fetch_defs, dry_run, client)
                    elif lang == "grc":
                        await load_inline_vocab("grc", _GRC_VOCAB, session, levels, fetch_defs, dry_run, client)
                    elif lang in _FW_LANG_MAP:
                        fw_lang = _FW_LANG_MAP[lang]
                        await load_freq_vocab(lang, fw_lang, session, levels, fetch_defs, dry_run, client)
                    else:
                        log.warning("No vocabulary source configured for '%s', skipping", lang)

    await engine.dispose()
    log.info("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Harvest CEFR vocabulary and grammar rules into the Mnemosyne database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--languages", nargs="+", default=ALL_LANGUAGES,
                        metavar="LANG", help=f"BCP-47 codes to harvest (default: all {len(ALL_LANGUAGES)})")
    parser.add_argument("--levels", nargs="+", default=ALL_LEVELS,
                        metavar="LEVEL", help="CEFR levels to harvest (default: A1 A2 B1 B2 C1 C2)")
    parser.add_argument("--skip-vocab",       action="store_true", help="Skip vocabulary harvesting")
    parser.add_argument("--skip-grammar",     action="store_true", help="Skip grammar rule loading")
    parser.add_argument("--skip-definitions", action="store_true", help="Skip Wiktionary definition fetching")
    parser.add_argument("--dry-run",          action="store_true", help="Count and print without writing to DB")

    args = parser.parse_args()

    bad_langs   = [l for l in args.languages if l not in ALL_LANGUAGES]
    bad_levels  = [l for l in args.levels    if l not in ALL_LEVELS]
    if bad_langs:
        parser.error(f"Unknown languages: {bad_langs}. Supported: {ALL_LANGUAGES}")
    if bad_levels:
        parser.error(f"Unknown levels: {bad_levels}. Supported: {ALL_LEVELS}")

    log.info("Languages: %s", args.languages)
    log.info("Levels:    %s", args.levels)
    log.info("Dry-run:   %s", args.dry_run)

    asyncio.run(run(
        languages=args.languages,
        levels=args.levels,
        skip_vocab=args.skip_vocab,
        skip_grammar=args.skip_grammar,
        skip_definitions=args.skip_definitions,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()

"""Matching algorithm: cm/360 (unified via Yaw) -> ideal friction -> ranked mousepads.

5 sensitivity tiers -> 4 surface types, with rough as independent tier.
Tier-anchored ideal friction ensures each sensitivity band maps to the
correct friction zone (speed ~1.5, balanced ~3-4, control ~5, rough ~6-7).

Dynamic thrust nudges within +/-3 pts (lightweight), preserving friction distance as primary ranker.
game_bias reserved at 0, interface intact.
"""

import math
from data import MOUSEPADS, GAMES


# ---- Sensitivity tiers (cm/360, anchored to Valorant eDPI) ----
# eDPI = DPI x Sens_val; cm/360 = 360 x 2.54 / (eDPI x 0.07)
# 450 -> 29.0 | 370 -> 35.3 | 320 -> 40.8 | 240 -> 54.4
TIER_HIGH     = 29.0
TIER_MID_HIGH = 35.3
TIER_MID      = 40.8
TIER_MID_LOW  = 54.4

# Tier -> (cm_center, ideal_static, ideal_dynamic, ideal_stopping)
# Centers align with real pad friction clusters in data.py
# Rough zone: static 6.0-6.5, dynamic 4.5-5.0, stopping 6.5-7.5
# Control zone: static 5.0-5.5, dynamic 3.8-4.2, stopping 5.5-6.0
# Clear gap between control max (6.0) and rough min (6.5) on stopping power
TIER_ANCHOR = {
    "high":     {"cm": 22.0, "static": 6.5, "dynamic": 4.8, "stopping": 7.0},
    "mid_high": {"cm": 32.0, "static": 5.3, "dynamic": 4.0, "stopping": 5.8},
    "mid":      {"cm": 38.0, "static": 3.8, "dynamic": 3.0, "stopping": 4.2},
    "mid_low":  {"cm": 47.0, "static": 3.0, "dynamic": 2.3, "stopping": 3.3},
    "low":      {"cm": 65.0, "static": 1.5, "dynamic": 1.0, "stopping": 1.5},
}

# Tier -> surface recommendation
# rough is an independent tier, NOT a subset of control
TIER_SURFACE = {
    "high":     "rough",
    "mid_high": "control",
    "mid":      "balanced",
    "mid_low":  "balanced",
    "low":      "speed",
}

# Surface-specific friction weights for Euclidean scoring
# rough: stopping-heavy (涩垫制动为王); control: balanced stopping/static
SURFACE_WEIGHTS = {
    "rough":    {"static": 0.20, "dynamic": 0.15, "stopping": 0.65},
    "control":  {"static": 0.35, "dynamic": 0.25, "stopping": 0.40},
    "balanced": {"static": 0.35, "dynamic": 0.30, "stopping": 0.35},
    "speed":    {"static": 0.30, "dynamic": 0.45, "stopping": 0.25},
}

# Dynamic thrust: (player_pref, pad_surface) -> bonus. Max +/-3 pts (lightweight).
SURFACE_MATCH_BONUS = {
    ("rough", "rough"):      3.0,
    ("rough", "control"):    1.0,
    ("control", "control"):  2.5,
    ("control", "balanced"): 1.0,
    ("control", "rough"):    2.0,
    ("balanced", "balanced"): 2.0,
    ("balanced", "control"):  1.0,
    ("balanced", "speed"):    1.0,
    ("speed", "speed"):      2.5,
    ("speed", "balanced"):   1.0,
}

# Cross-type penalty: strongly mismatched surface types
CROSS_PENALTY = {
    ("rough", "balanced"): -6.0,
    ("rough", "speed"):    -8.0,
    ("speed", "rough"):    -8.0,
    ("speed", "control"):  -4.0,
    ("control", "speed"):  -4.0,
    ("balanced", "rough"): -5.0,
    ("balanced", "speed"): 0.0,
}


def compute_cm360(mouse_dpi: float, game_sens: float, yaw: float) -> float:
    """cm/360 = 360 / (DPI x Sens x Yaw) x 2.54  (universal metric)."""
    if mouse_dpi <= 0 or game_sens <= 0 or yaw <= 0:
        return 35.0
    return (360.0 / (mouse_dpi * game_sens * yaw)) * 2.54


def classify_sensitivity(cm360: float) -> str:
    """5-tier classification from cm/360."""
    if cm360 < TIER_HIGH:       return "high"
    elif cm360 < TIER_MID_HIGH: return "mid_high"
    elif cm360 < TIER_MID:      return "mid"
    elif cm360 < TIER_MID_LOW:  return "mid_low"
    else:                       return "low"


def ideal_friction(cm360: float, game_bias: float = 0.0) -> dict:
    """Tier-anchored ideal friction: each sensitivity band maps to its
    correct friction zone, with mild intra-tier interpolation via log-scale
    offset from the tier center.

    game_bias is reserved at 0; preserved for future per-genre calibration.
    """
    if cm360 <= 0:
        cm360 = 35.0

    tier = classify_sensitivity(cm360)
    anchor = TIER_ANCHOR[tier]

    # Intra-tier interpolation: mild log-scale offset from tier center
    log_val   = math.log10(cm360)
    log_center = math.log10(anchor["cm"])
    offset    = (log_val - log_center) * 4.0   # mild, keeps friction within tier zone

    ideal_static  = anchor["static"]  + offset * 0.25
    ideal_dynamic = anchor["dynamic"] + offset * 0.20
    ideal_stopping = anchor["stopping"] + offset * 0.30

    # Clamp to physically meaningful ranges
    ideal_static  = max(0.5, min(7.5, ideal_static))
    ideal_dynamic = max(0.3, min(5.5, ideal_dynamic))
    ideal_stopping = max(0.5, min(8.0, ideal_stopping))

    # Raw score for display compatibility
    log_35 = math.log10(35.0)
    raw_score = (log_val - log_35) * 7.0 + game_bias
    raw_score = max(-10.0, min(10.0, raw_score))

    return {
        "cm360":              round(cm360, 1),
        "raw_score":          round(raw_score, 2),
        "sensitivity_tier":   tier,
        "surface_preference": TIER_SURFACE[tier],
        "ideal_static":       round(ideal_static, 2),
        "ideal_dynamic":      round(ideal_dynamic, 2),
        "ideal_stopping":     round(ideal_stopping, 2),
    }


def match_score(pad: dict, ideal: dict) -> float:
    """Score pad vs ideal: surface-weighted Euclidean distance + dynamic thrust."""
    surface = pad.get("surface", "balanced")
    w = SURFACE_WEIGHTS.get(surface, SURFACE_WEIGHTS["balanced"])

    dist = math.sqrt(
        w["static"]   * (pad["static_friction"] - ideal["ideal_static"]) ** 2
        + w["dynamic"] * (pad["dynamic_friction"] - ideal["ideal_dynamic"]) ** 2
        + w["stopping"] * (pad["stopping_power"] - ideal["ideal_stopping"]) ** 2
    )

    base = max(0.0, 100.0 - dist * 16.67)

    player_pref = ideal["surface_preference"]
    bonus = SURFACE_MATCH_BONUS.get((player_pref, surface), 0.0)

    penalty_key = (surface, player_pref)
    if penalty_key in CROSS_PENALTY:
        bonus += CROSS_PENALTY[penalty_key]

    return round(max(0.0, min(100.0, base + bonus)), 1)


def rank_mousepads(mouse_dpi: float, game_sens: float, game_id: str = "general", surface_filter: str = None) -> dict:
    """Full pipeline: cm/360 -> ideal friction -> ranked pads.

    surface_filter: optional surface type to filter results (speed/balanced/control/rough).
    When set, only pads of that surface type are scored and returned.
    """
    game = GAMES.get(game_id, GAMES["general"])
    cm360 = compute_cm360(mouse_dpi, game_sens, game["yaw"])
    ideal = ideal_friction(cm360, game.get("bias", 0.0))

    pads = MOUSEPADS
    if surface_filter and surface_filter in ("speed", "balanced", "control", "rough"):
        pads = [p for p in MOUSEPADS if p["surface"] == surface_filter]

    results = []
    for pad in pads:
        score = match_score(pad, ideal)
        results.append({"pad": pad, "score": score})

    results.sort(key=lambda r: r["score"], reverse=True)

    return {
        "cm360": ideal["cm360"],
        "sensitivity_tier": ideal["sensitivity_tier"],
        "surface_preference": ideal["surface_preference"],
        "game_name": game["name"],
        "game_category": game["category"],
        "recommendations": [
            {
                "rank": i + 1,
                "score": r["score"],
                "id": r["pad"]["id"],
                "name": r["pad"]["name"],
                "brand": r["pad"]["brand"],
                "surface": r["pad"]["surface"],
                "material": r["pad"]["material"],
                "static_friction": r["pad"]["static_friction"],
                "dynamic_friction": r["pad"]["dynamic_friction"],
                "stopping_power": r["pad"]["stopping_power"],
                "speed_rating": r["pad"]["speed_rating"],
                "sizes": r["pad"]["sizes"],
                "thickness": r["pad"]["thickness"],
                "price_cny": r["pad"]["price_cny"],
                "image": r["pad"]["image"],
                "desc": r["pad"]["desc"],
                "detail_desc": r["pad"].get("detail_desc", r["pad"]["desc"]),
                "desc_source": r["pad"].get("desc_source", ""),
                "dimensions": r["pad"].get("dimensions"),
                "purchase_links": r["pad"].get("purchase_links"),
            }
            for i, r in enumerate(results)
        ],
    }

DIMENSION_LABELS = {
    "glide": "顺滑度",
    "control": "操控性",
    "durability": "耐用性",
    "comfort": "舒适度",
    "compatibility": "兼容性",
    "value": "性价比",
}

def compute_pad_comparison(pad_id: str) -> dict | None:
    """Compute per-dimension ranking for a given pad across all 17 pads.

    Returns None if pad not found or has no dimensions data.
    """
    target = None
    all_pads_with_dims = []

    for pad in MOUSEPADS:
        dims = pad.get("dimensions")
        if dims and all(k in dims for k in DIMENSION_LABELS):
            all_pads_with_dims.append(pad)
            if pad["id"] == pad_id:
                target = pad

    if not target or "dimensions" not in target:
        return None

    total = len(all_pads_with_dims)
    comparison = {}

    for dim_key, dim_label in DIMENSION_LABELS.items():
        # Build sorted list of (pad_id, name, score) for this dimension
        ranked = sorted(
            [(p["id"], p["name"], p["dimensions"][dim_key]) for p in all_pads_with_dims],
            key=lambda x: x[2],
            reverse=True,
        )

        # Find target pad's rank (1-indexed)
        target_score = target["dimensions"][dim_key]
        rank = next(i + 1 for i, r in enumerate(ranked) if r[0] == pad_id)
        percentile = round((1 - (rank - 1) / total) * 100, 1)

        top3 = [
            {"id": r[0], "name": r[1], "score": r[2]}
            for r in ranked[:3]
        ]

        comparison[dim_key] = {
            "label": dim_label,
            "score": target_score,
            "rank": rank,
            "total": total,
            "percentile": percentile,
            "top3": top3,
        }

    return comparison

def _match_personas(pad_name: str, dim_scores: dict, scenes: list, sensitivity_tier: str) -> list:
    """根据口碑数据推断适合的用户画像。

    返回：["画像描述", ...]
    """
    personas = []
    glide = dim_scores.get("glide", {}).get("score", 5)
    control = dim_scores.get("control", {}).get("score", 5)
    comfort = dim_scores.get("comfort", {}).get("score", 5)
    durability = dim_scores.get("durability", {}).get("score", 5)

    # 高滑度 → 手腕流
    if glide >= 7 and control >= 6:
        personas.append("高速跟枪手腕流（滑中带控，微调跟枪两不误）")
    elif glide >= 7:
        personas.append("高速手腕流玩家（极低启动阻力，适合快速微调）")

    # 高控制 → 手臂流
    if control >= 8:
        personas.append("低DPI手臂流 / 战术FPS玩家（急停精准，制动可靠）")
    elif control >= 7 and glide <= 6:
        personas.append("稳健型FPS玩家（偏重控制，适合CS/Valorant定位）")

    # 办公友好
    if comfort >= 7 and "办公" in scenes:
        personas.append("长时间办公用户（触感舒适，久用不疲劳）")

    # 汗手场景
    if "潮湿" in scenes:
        personas.append("汗手玩家友好（防潮/耐磨表现获认可）")

    # MOBA场景
    if "MOBA" in scenes and glide >= 6:
        personas.append("MOBA/高频点击玩家（顺滑度满足快速移动需求）")

    # 玻璃垫特殊
    if "玻璃垫" in scenes or "玻璃" in scenes:
        personas.append("硬垫爱好者（玻璃/树脂垫的绝对操控感）")

    # 耐久
    if durability >= 7:
        personas.append("长期持有型玩家（耐用口碑好，懒得换垫子）")

    # 性价比
    if dim_scores.get("value", {}).get("score", 5) >= 7:
        personas.append("预算敏感型玩家（追求高性价比）")

    if not personas:
        personas.append("通用型用户（评价数据不足，暂无明确画像）")

    return personas


def build_enhanced_report(
    selected: list,
    dim_analyses: list,
    detail_summaries: list,
    surface_text: str,
    overall_text: str,
    top_overall: dict,
    sensitivity_tier: str,
    cm360: float,
    game: dict,
    mouse_dpi: float,
    game_sens: float,
    crawl_summary: dict = None,
) -> dict:
    """构建终极决策报告（Markdown 格式）。

    # 鼠标垫终极决策报告
    ## 1. 综合推荐结论
    ## 2. 全网声量与口碑
    ## 3. 核心性能雷达图
    ## 4. 详细对比分析
    ## 5. 最终购买建议
    """
    surface_labels = {"speed": "速度型", "balanced": "均衡型", "control": "控制型", "rough": "涩面"}
    tier_labels = {"high": "高敏", "mid_high": "中高敏", "mid": "中敏", "mid_low": "中低敏", "low": "低敏"}
    dim_labels = {
        "glide": "顺滑度", "control": "操控性", "durability": "耐用性",
        "comfort": "舒适度", "compatibility": "兼容性", "value": "性价比",
    }
    core4_map = {
        "顺滑度": "glide", "操控性": "control",
        "质感做工": "comfort", "性价比": "value",
    }
    selected_names = [p["name"] for p in selected]

    report = {"selected_pads": [], "report": {}}

    for p in selected:
        report["selected_pads"].append({
            "id": p["id"], "name": p["name"], "brand": p["brand"],
            "surface": p["surface"], "dimensions": p.get("dimensions"),
            "detail_desc": p.get("detail_desc", p["desc"]),
            "price_cny": p["price_cny"], "sizes": p.get("sizes", []),
            "static_friction": p["static_friction"],
            "dynamic_friction": p["dynamic_friction"],
            "stopping_power": p["stopping_power"],
            "speed_rating": p["speed_rating"],
            "material": p["material"], "thickness": p["thickness"],
        })

    # ---- 算法匹配 ----
    scored_pads = []
    if sensitivity_tier and cm360:
        ideal = ideal_friction(cm360, 0)
        for p in selected:
            s = match_score(p, ideal)
            scored_pads.append((p, s))
        scored_pads.sort(key=lambda x: x[1], reverse=True)

    # ---- 无爬虫数据：简化报告（用算法维度填补详情）----
    if not crawl_summary:
        algo_details = []
        for p in selected:
            dims = p.get("dimensions", {})
            # 用算法维度构建一个模拟 review，让详情不显示"数据不足"
            algo_review = {
                "mention_count": 0,
                "personas": [_match_personas(p["name"], {
                    "glide": {"score": dims.get("glide", 5)},
                    "control": {"score": dims.get("control", 5)},
                    "comfort": {"score": dims.get("comfort", 5)},
                    "durability": {"score": dims.get("durability", 5)},
                    "value": {"score": dims.get("value", 5)},
                }, [], sensitivity_tier or "")],
                "top_pos_keywords": [
                    dim_labels.get(k, k) for k, v in sorted(dims.items(), key=lambda x: x[1], reverse=True)[:3]
                    if v >= 7
                ],
                "top_neg_keywords": [
                    dim_labels.get(k, k) for k, v in sorted(dims.items(), key=lambda x: x[1])[:2]
                    if v <= 4
                ],
                "pros": ["算法评分：基于产品参数推算，非社区真实口碑。"],
                "cons": [],
                "approval_rate": 0,
            }
            algo_details.append(_build_pad_detail(p, algo_review, sensitivity_tier))

        rpt = {
            "title": "鼠标垫终极决策报告",
            "summary": "（未获取 B站 社区数据，报告基于算法参数对比。设置 COOKIE_B 可启用社区口碑分析。）",
            "conclusion": _build_conclusion(scored_pads, selected, top_overall, sensitivity_tier) if scored_pads else "",
            "radar": _build_radar_text(selected, {}),
            "details": algo_details,
            "buy_guide": _build_buy_guide(scored_pads, selected, {}, sensitivity_tier) if scored_pads else [],
        }
        report["report"] = rpt
        report["user_context"] = {
            "cm360": round(cm360, 1) if cm360 else None,
            "sensitivity_tier": sensitivity_tier,
            "tier_label": tier_labels.get(sensitivity_tier, "") if sensitivity_tier else "",
            "game_name": game.get("name", "") if game else "",
        } if cm360 else None
        return report

    # ---- 提取爬虫数据 ----
    pad_mentions = crawl_summary.get("pad_mentions", {})
    b_info = crawl_summary.get("bilibili", {})

    # 构建每个垫的口碑数据
    pad_reviews = {}
    for p in selected:
        name = p["name"]
        m = pad_mentions.get(name, {})
        dim_analysis = m.get("dimension_analysis", {})
        dim_scores = {}
        for dim_key, dim_label in dim_labels.items():
            da = dim_analysis.get(dim_key, {"pos_count": 0, "neg_count": 0, "net": 0})
            total = da["pos_count"] + da["neg_count"]
            normalized = 5 + (da["net"] / total) * 5 if total > 0 else 5.0
            dim_scores[dim_key] = {
                "label": dim_label, "pos_count": da["pos_count"], "neg_count": da["neg_count"],
                "net": da["net"], "score": round(max(1.0, min(10.0, normalized)), 1),
            }

        # 好评率
        pos_count = sum(d["pos_count"] for d in dim_scores.values())
        neg_count = sum(d["neg_count"] for d in dim_scores.values())
        total_count = pos_count + neg_count
        approval = round(pos_count / total_count * 100, 1) if total_count > 0 else 0

        personas = _match_personas(name, dim_scores, m.get("scenes", []), sensitivity_tier or "")

        pad_reviews[name] = {
            "mention_count": m.get("mention_count", 0),
            "sentiment_strength": m.get("sentiment_strength", 0),
            "approval_rate": approval,
            "dimension_scores": dim_scores,
            "top_pos_keywords": m.get("top_pos_keywords", []),
            "top_neg_keywords": m.get("top_neg_keywords", []),
            "pros": m.get("pros", [])[:3],
            "cons": m.get("cons", [])[:3],
            "scenes": m.get("scenes", []),
            "personas": personas,
        }

    # ---- 模块一：综合推荐结论 ----
    conclusion = _build_conclusion(scored_pads, selected, top_overall, sensitivity_tier)
    if pad_reviews:
        # 加入社区口碑的结论
        best_sentiment = max(pad_reviews.items(), key=lambda x: x[1]["sentiment_strength"])
        best_approval = max(pad_reviews.items(), key=lambda x: x[1]["approval_rate"])
        conclusion += (
            f"\n\n社区口碑方面：**{best_approval[0]}** 好评率最高（{best_approval[1]['approval_rate']}%），"
            f"**{best_sentiment[0]}** 情感强度最强（{best_sentiment[1]['sentiment_strength']}）。"
        )

    # ---- 模块二：全网声量与口碑 ----
    mentions_list = []
    for p in selected:
        pr = pad_reviews.get(p["name"], {})
        mc = pr.get("mention_count", 0)
        approval = pr.get("approval_rate", 0)
        emoji = "🔥" if approval >= 80 else ("✅" if approval >= 60 else ("⚠️" if approval >= 40 else "❄️"))
        mentions_list.append({
            "name": p["name"],
            "approval_rate": approval,
            "emoji": emoji,
            "mention_count": mc,
            "top_pos": pr.get("top_pos_keywords", [])[:3],
            "top_neg": pr.get("top_neg_keywords", [])[:2],
        })
    # 计算数据不足的型号
    insufficient = [p["name"] for p in selected if pad_reviews.get(p["name"], {}).get("mention_count", 0) == 0]

    # ---- 模块三：雷达图 ----
    radar = _build_radar_text(selected, pad_reviews)

    # ---- 模块四：详细对比分析 ----
    details = []
    for p in selected:
        details.append(_build_pad_detail(p, pad_reviews.get(p["name"], {}), sensitivity_tier))

    # ---- 模块五：最终购买建议 ----
    buy_guide = _build_buy_guide(scored_pads, selected, pad_reviews, sensitivity_tier)

    report["report"] = {
        "title": "鼠标垫终极决策报告",
        "data_source_note": (
            f"基于 B站 {b_info.get('video_count', 0)} 个相关视频、"
            f"{b_info.get('total_comments', 0)} 条用户评论的自动化分析。"
            f"搜索关键词：{' '.join(selected_names[:3])} 鼠标垫测评。"
        ),
        "conclusion": conclusion,
        "mentions": mentions_list,
        "insufficient": insufficient,
        "radar": radar,
        "details": details,
        "buy_guide": buy_guide,
    }
    report["user_context"] = {
        "cm360": round(cm360, 1) if cm360 else None,
        "sensitivity_tier": sensitivity_tier,
        "tier_label": tier_labels.get(sensitivity_tier, "") if sensitivity_tier else "",
        "game_name": game.get("name", "") if game else "",
    } if cm360 else None

    return report


# ---- 辅助函数 ----

def _build_conclusion(scored_pads: list, selected: list, top_overall: dict, sensitivity_tier: str) -> str:
    """构建综合推荐结论文字。"""
    surface_labels = {"speed": "速度型", "balanced": "均衡型", "control": "控制型", "rough": "涩面"}
    tier_labels = {"high": "高敏", "mid_high": "中高敏", "mid": "中敏", "mid_low": "中低敏", "low": "低敏"}

    if not scored_pads:
        # 无灵敏度参数
        top_name = top_overall["name"]
        avg = top_overall["average"]
        cheapest = min(selected, key=lambda p: p["price_cny"])
        return (
            f"综合六维表现，**{top_name}** 以 {avg}/10 的平均分领先。"
            f"追求性价比可以考虑 **{cheapest['name']}**（¥{cheapest['price_cny']}）。"
            f"\n\n（未提供 DPI 和灵敏度参数，推荐基于通用评分。输入灵敏度可获得个性化匹配。）"
        )

    best, best_score = scored_pads[0]
    # 性价比
    affordable = sorted(selected, key=lambda p: p["price_cny"])
    budget_pick = affordable[0]
    # 高口碑（如果有社区数据会覆盖）
    tier_cn = tier_labels.get(sensitivity_tier, "")

    parts = [
        f"如果预算不是问题，**闭眼入 {best['name']}**"
        f"（匹配度 {round(best_score, 1)}/100，{tier_cn}档位最优解）。",
    ]

    if len(scored_pads) >= 2:
        runner, runner_score = scored_pads[1]
        diff = best_score - runner_score
        if diff > 5:
            parts.append(f"{best['name']} 优势明显，与第二名 {runner['name']} 拉开 {round(diff, 1)} 分差距。")
        elif diff > 1:
            parts.append(f"与 {runner['name']}（{round(runner_score, 1)}分）差距不大，根据手感偏好微调可选。")
        else:
            parts.append(f"与 {runner['name']} 几乎持平，手感决定最终选择。")

    if budget_pick["name"] != best["name"]:
        parts.append(
            f"追求性价比选 **{budget_pick['name']}**（¥{budget_pick['price_cny']}），"
            f"花小钱也能获得不错体验。"
        )

    return "\n".join(parts)


def _build_radar_text(selected: list, pad_reviews: dict) -> dict:
    """构建核心性能雷达图的文字描述。

    四个维度：顺滑度 / 操控性 / 质感做工 / 性价比
    """
    dims_order = ["顺滑度", "操控性", "质感做工", "性价比"]
    key_map = {"顺滑度": "glide", "操控性": "control", "质感做工": "comfort", "性价比": "value"}
    dim_labels_cn = {
        "顺滑度": "表面滑动阻力越小分数越高，跟枪/拉枪越流畅",
        "操控性": "制动能力与微调精度，急停越稳分数越高",
        "质感做工": "表面触感、边缘处理、整体做工的舒适度",
        "性价比": "同等性能下的价格优势",
    }

    radar_lines = []
    for dim_cn in dims_order:
        dk = key_map[dim_cn]
        # 从 algorithm 评分 + 社区口碑 中取各垫分数
        items = []
        for p in selected:
            # 优先用社区口碑维度评分，其次用算法维度评分
            pr = pad_reviews.get(p["name"], {})
            ds = pr.get("dimension_scores", {}).get(dk, {})
            community_score = ds.get("score")
            algo_score = p.get("dimensions", {}).get(dk, 5)
            # 综合：社区评分权重 0.6，算法评分权重 0.4
            if community_score is not None:
                score = round(community_score * 0.6 + algo_score * 0.4, 1)
            else:
                score = algo_score
            items.append((p["name"], score))
        items.sort(key=lambda x: x[1], reverse=True)
        comparison = " > ".join(f"{n}（{s}）" for n, s in items)
        radar_lines.append({
            "dimension": dim_cn,
            "description": dim_labels_cn.get(dim_cn, ""),
            "comparison": comparison,
            "ranked": [{"name": n, "score": s} for n, s in items],
        })
    return {"dimensions": dims_order, "radar_lines": radar_lines}


def _build_pad_detail(pad: dict, review: dict, sensitivity_tier: str) -> dict:
    """构建单个鼠标垫的详细对比分析。"""
    surface_labels = {"speed": "速度型", "balanced": "均衡型", "control": "控制型", "rough": "涩面"}

    detail = {
        "name": pad["name"],
        "brand": pad["brand"],
        "surface": surface_labels.get(pad["surface"], pad["surface"]),
        "price": pad["price_cny"],
        "desc": pad.get("detail_desc", pad.get("desc", ""))[:200],
    }

    if not review or (review.get("mention_count", 0) == 0 and not review.get("top_pos_keywords")):
        detail["praised"] = ["算法评分维度数据，非社区口碑"]
        detail["criticized"] = ["未获取到 B站 社区评价，设置 COOKIE_B 环境变量可启用"]
        detail["personas"] = ["通用型用户（暂无社区数据画像）"]
        detail["insufficient_data"] = True
        return detail

    # 被夸最多
    praised = []
    if review.get("top_pos_keywords"):
        praised.append("、".join(review["top_pos_keywords"][:4]))
    if review.get("pros"):
        praised.append(f"「{review['pros'][0][:60]}」")

    # 被骂最多
    criticized = []
    if review.get("top_neg_keywords"):
        criticized.append("、".join(review["top_neg_keywords"][:3]))
    if review.get("cons"):
        criticized.append(f"「{review['cons'][0][:60]}」")
    if not criticized:
        criticized.append("暂无显著的集中负面反馈，口碑较为正面")

    detail["praised"] = praised
    detail["criticized"] = criticized
    detail["personas"] = review.get("personas", ["通用型用户"])
    detail["approval_rate"] = review.get("approval_rate", 0)
    detail["mention_count"] = review.get("mention_count", 0)
    detail["insufficient_data"] = False
    return detail


def _build_buy_guide(scored_pads: list, selected: list, pad_reviews: dict, sensitivity_tier: str) -> list:
    """构建最终购买建议表。"""
    guide = []
    surface_labels = {"speed": "速度型", "balanced": "均衡型", "control": "控制型", "rough": "涩面"}

    # 只打 FPS，追求定位准 → 制动最强的
    best_control = max(
        selected,
        key=lambda p: p.get("dimensions", {}).get("control", 5) + p.get("stopping_power", 0) * 2
    )
    guide.append({"need": "我只打瓦/CS，追求定位精准", "pick": best_control["name"], "reason": "控制力 + 制动能力领先"})

    # 日常办公+打游戏
    best_comfort = max(
        selected,
        key=lambda p: p.get("dimensions", {}).get("comfort", 5) + p.get("dimensions", {}).get("compatibility", 5)
    )
    guide.append({"need": "我日常办公+打游戏", "pick": best_comfort["name"], "reason": "舒适度与兼容性综合最优"})

    # 预算有限
    cheapest = min(selected, key=lambda p: p["price_cny"])
    guide.append({"need": "我预算有限", "pick": cheapest["name"], "reason": f"仅 ¥{cheapest['price_cny']}，性价比拉满"})

    # 汗手/潮湿环境
    for p in selected:
        pr = pad_reviews.get(p["name"], {})
        if "潮湿" in pr.get("scenes", []):
            guide.append({"need": "我是汗手/潮湿环境", "pick": p["name"], "reason": "社区反馈防潮表现好"})
            break

    return guide


def generate_comparison_analysis(pad_ids: list[str], mouse_dpi: float = None, game_sens: float = None, game_id: str = "general", crawl_summary: dict = None) -> dict:
    """Generate a deep, professional comparison report for the selected pads.

    Uses product descriptions, dimensional data, and user sensitivity params
    to produce an AI-quality analysis report — all algorithmically, no ML.

    If crawl_summary is provided (from crawler.crawl_safe), integrates community
    review (B站/抖音测评视频 + 评论口碑) into the final report.
    """
    selected = [p for p in MOUSEPADS if p["id"] in pad_ids]
    if len(selected) < 2:
        return {"error": "请至少选择 2 款鼠标垫进行对比"}

    # Compute user cm/360
    cm360 = None
    sensitivity_tier = None
    game = None
    if mouse_dpi and game_sens:
        game = GAMES.get(game_id, GAMES.get("general", {}))
        if game:
            cm360 = compute_cm360(mouse_dpi, game_sens, game.get("yaw", 0.022))
            sensitivity_tier = classify_sensitivity(cm360)

    dim_labels = {
        "glide": "顺滑度", "control": "操控性", "durability": "耐用性",
        "comfort": "舒适度", "compatibility": "兼容性", "value": "性价比",
    }
    dim_interpretation = {
        "glide":      ("越高代表鼠标滑动越流畅、阻力越小，适合高灵敏度玩家快速拉枪；越低则启动阻力大，更适合需要精细微调的场景。", "顺滑为王，适合跟枪流"),
        "control":    ("越高代表制动能力越强，甩枪后鼠标可迅速静止，是低灵敏度战术 FPS 玩家的核心需求；越低则急停时需要更多手部控制。", "精准制动，低敏玩家的刚需"),
        "durability": ("越高代表使用寿命越长、受环境（湿度、温度）影响越小；玻璃垫近乎永久，涂层垫寿命最短。", "耐用可靠，长期投资回报高"),
        "comfort":    ("越高代表表面触感越舒适、边缘不硌手、厚度适中；对长时间游戏/办公用户尤为重要。", "舒适至上，长时间使用不疲劳"),
        "compatibility": ("越高代表与各类鼠标传感器、脚贴的兼容性越好，潮湿环境下表现更稳定。", "百搭兼容，不挑设备"),
        "value":      ("越高代表在同等性能下价格越亲民、性价比越突出。", "物超所值，预算友好"),
    }
    surface_labels = {"speed": "速度型", "balanced": "均衡型", "control": "控制型", "rough": "涩面"}
    tier_labels = {"high": "高敏", "mid_high": "中高敏", "mid": "中敏", "mid_low": "中低敏", "low": "低敏"}

    # ---- Build analysis paragraphs ----
    parts = []
    selected_names = [p["name"] for p in selected]

    # 1. Opening summary
    brands = [p["brand"] for p in selected]
    surfaces = [surface_labels.get(p["surface"], p["surface"]) for p in selected]
    parts.append(f"本次对比涉及 {len(selected)} 款鼠标垫：{'、'.join(selected_names)}，分别来自 {'、'.join(brands)}，涵盖 {'、'.join(surfaces)} 等表面类型。")

    # 2. Per-dimension deep analysis
    dim_analyses = []
    for dk, dlabel in dim_labels.items():
        scores = [(p["name"], p["dimensions"].get(dk, 0), p) for p in selected if p.get("dimensions")]
        scores.sort(key=lambda x: x[1], reverse=True)
        best = scores[0]
        worst = scores[-1]
        gap = best[1] - worst[1]
        interp, tag = dim_interpretation[dk]

        # Build detailed verdict
        if gap >= 6:
            verdict = f"差距悬殊——{best[0]}（{best[1]}分）的{dlabel}远超 {worst[0]}（{worst[1]}分），两者在实际使用中将有完全不同的手感体验。"
        elif gap >= 3:
            verdict = f"差异明显——{best[0]}（{best[1]}分）在{dlabel}上领先 {worst[0]}（{worst[1]}分），对于追求极致性能的玩家来说这一差距值得重视。"
        elif gap >= 1:
            verdict = f"略有差异——{best[0]}（{best[1]}分）略优于 {worst[0]}（{worst[1]}分），日常使用中差异感知不明显。"
        else:
            verdict = f"旗鼓相当——各产品在{dlabel}上表现接近（差距≤1分），实际体验难分伯仲。"

        # Build ranking text
        rank_parts = []
        for i, (name, score, pad) in enumerate(scores):
            marker = "🥇" if i == 0 else ("🥈" if i == 1 else ("🥉" if i == 2 else f"{i+1}."))
            rank_parts.append(f"{marker} {name}（{score}分）")
        ranking_text = " ＞ ".join(rank_parts)

        dim_analyses.append({
            "dimension_key": dk,
            "dimension_label": dlabel,
            "ranking_text": ranking_text,
            "verdict": verdict,
            "interpretation": interp,
            "tag": tag,
            "best_name": best[0], "best_score": best[1],
            "worst_name": worst[0], "worst_score": worst[1],
            "gap": gap,
            "ranked": [{"name": n, "score": s} for n, s, _ in scores],
        })

    # 3. Product detail summaries
    detail_summaries = []
    for p in selected:
        desc = p.get("detail_desc", p.get("desc", ""))
        dims = p.get("dimensions", {})
        top2 = sorted(dims.items(), key=lambda x: x[1], reverse=True)[:2]
        weak2 = sorted(dims.items(), key=lambda x: x[1])[:2]
        detail_summaries.append({
            "name": p["name"],
            "brand": p["brand"],
            "surface": surface_labels.get(p["surface"], p["surface"]),
            "price": p["price_cny"],
            "sizes": p.get("sizes", []),
            "desc_excerpt": desc[:300] if desc else "",
            "strengths": [f"{dim_labels.get(d, d)}（{s}分）" for d, s in top2],
            "weaknesses": [f"{dim_labels.get(d, d)}（{s}分）" for d, s in weak2],
        })

    # 4. Overall assessment
    avg_scores = []
    for p in selected:
        dims = p.get("dimensions", {})
        if dims:
            avg = sum(dims.values()) / len(dims)
            avg_scores.append((p["name"], round(avg, 1), p["surface"], p["price_cny"]))
    avg_scores.sort(key=lambda x: x[1], reverse=True)
    top_overall = avg_scores[0]

    # Build comprehensive overall text
    overall_parts = []
    for name, avg, surface, price in avg_scores:
        overall_parts.append(f"{name}（{surface_labels.get(surface, surface)}型，¥{price}）综合平均 {avg} 分")
    overall_text = f"综合六维表现排名：{'；'.join(overall_parts)}。"

    # 5. Surface type comparison
    surface_types = list(set(p["surface"] for p in selected))
    if len(surface_types) > 1:
        st_labels = [surface_labels.get(s, s) for s in surface_types]
        surface_text = f"所选产品涵盖 {'、'.join(st_labels)} 等不同表面类型。速度型适合高灵敏度快速移动，控制型/涩面提供更强的制动力和微调精度，均衡型在速度与控制之间取得折中。"
    else:
        surface_text = f"所选产品均为 {surface_labels.get(surface_types[0], surface_types[0])} 表面，在此类别内进行深度对比。"

    # 6. Personalized recommendation
    recommendation = ""
    if sensitivity_tier and cm360:
        tier_cn = tier_labels.get(sensitivity_tier, sensitivity_tier)
        ideal = ideal_friction(cm360, 0)
        scored = []
        for p in selected:
            s = match_score(p, ideal)
            scored.append((p, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        best_match, best_score = scored[0]

        game_name = game.get("name", "通用") if game else "通用"

        # Build detailed recommendation
        rec_parts = []
        rec_parts.append(f"您的灵敏度设置：{mouse_dpi} DPI × {game_sens}（{game_name}），cm/360 ≈ {round(cm360, 1)}cm，属于「{tier_cn}」档位。")
        rec_parts.append(f"该档位最适配 {surface_labels.get(TIER_SURFACE.get(sensitivity_tier, 'balanced'), '均衡')} 型表面。")

        # Explain why the best match is recommended
        best_dims = best_match.get("dimensions", {})
        rec_parts.append(f"在您选择的 {len(selected)} 款产品中，**{best_match['name']}** 的摩擦特性与您的灵敏度设置最为匹配（匹配度 {round(best_score, 1)}/100）。")

        # Compare with runner-up
        if len(scored) >= 2:
            runner_up, runner_score = scored[1]
            score_diff = best_score - runner_score
            if score_diff > 5:
                rec_parts.append(f"相较于第二名 {runner_up['name']}（{round(runner_score, 1)}分），{best_match['name']} 的优势较为明显。")
            elif score_diff > 1:
                rec_parts.append(f"与 {runner_up['name']}（{round(runner_score, 1)}分）差距不大，两者均可考虑，但 {best_match['name']} 的综合匹配度略胜一筹。")
            else:
                rec_parts.append(f"与 {runner_up['name']}（{round(runner_score, 1)}分）几乎持平，建议根据个人手感偏好做最终决定。")

        # Usage scenario
        if sensitivity_tier in ("high", "mid_high"):
            rec_parts.append("作为低灵敏度玩家，建议重点关注操控性与制动能力，确保大范围甩枪后能精准锁定目标。")
        elif sensitivity_tier in ("mid",):
            rec_parts.append("作为中灵敏度玩家，建议选择均衡型表面，兼顾速度与控制的平衡。")
        else:
            rec_parts.append("作为高灵敏度玩家，顺滑度和速度表现是核心考量，低摩擦表面能让您的手腕微调更加流畅。")

        recommendation = "\n\n".join(rec_parts)
    else:
        recommendation = (
            f"综合考虑六维表现，**{top_overall[0]}** 以 {top_overall[1]}/10 的综合平均分领先。"
            f"如需基于您个人灵敏度参数的精准推荐，请在搜索栏输入 DPI 和灵敏度后再生成报告。"
        )

    report = build_enhanced_report(
        selected=selected,
        dim_analyses=dim_analyses,
        detail_summaries=detail_summaries,
        surface_text=surface_text,
        overall_text=overall_text,
        top_overall=top_overall,
        sensitivity_tier=sensitivity_tier,
        cm360=cm360,
        game=game,
        mouse_dpi=mouse_dpi,
        game_sens=game_sens,
        crawl_summary=crawl_summary,
    )

    return report

# -*- coding: utf-8 -*-
"""
=====================================================================
鼠标垫测评数据采集脚本（B站）
=====================================================================
仅供个人学习研究，严禁商业用途。
=====================================================================

功能：
1. B站（bilibili-api-python + HTTP 直连）：搜索关键词 → 抓取前 N 个视频 → 抓取每个视频前 M 条热门评论
2. 输出：mousepad_reviews.xlsx
3. 供后端调用：crawl_for_pads() 返回结构化数据，供 algorithm.py 整合到对比报告

依赖自动安装：openpyxl / bilibili-api-python
Cookie 不写死，优先读环境变量 COOKIE_B，缺失时交互提示

作者：Vibe Coding 助手
=====================================================================
"""

import os
import sys
import time
import random
import json
import logging
import asyncio
import re
from typing import Optional, List, Dict, Any
from urllib.request import Request, urlopen

# ----------------------------------------------------------------------
# 依赖自动检测与安装
# ----------------------------------------------------------------------
def _ensure_pkg(pkg_name: str, import_name: str = None) -> bool:
    import_name = import_name or pkg_name
    try:
        __import__(import_name)
        return True
    except ImportError:
        try:
            import subprocess
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            __import__(import_name)
            return True
        except Exception as e:
            logging.warning(f"安装依赖 {pkg_name} 失败: {e}")
            return False

_ensure_pkg("openpyxl", "openpyxl")
HAS_BILI_API = _ensure_pkg("bilibili-api-python", "bilibili_api")

logger = logging.getLogger("crawler")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


# ----------------------------------------------------------------------
# Cookie 管理
# ----------------------------------------------------------------------
def parse_cookie_str(cookie_str: str) -> Dict[str, str]:
    cookies = {}
    if not cookie_str:
        return cookies
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies


def get_cookie_b() -> str:
    """获取 B 站 Cookie。

    获取方法：
    1. 浏览器登录 https://www.bilibili.com
    2. F12 → Application → Cookies → 复制全部 Cookie
    """
    cookie = os.getenv("COOKIE_B", "").strip()
    if not cookie:
        print("\n[B站] 未检测到环境变量 COOKIE_B")
        print("获取方法：1. 浏览器登录 bilibili.com  2. F12 → Application → Cookies → 复制全部")
        cookie = input("请粘贴 B站 Cookie（直接回车跳过）: ").strip()
    return cookie


# ----------------------------------------------------------------------
# B站爬虫
# ----------------------------------------------------------------------
def _fetch_bilibili_comments(aid: int, max_count: int = 50) -> List[Dict[str, Any]]:
    """通过 B站 HTTP API 抓取评论（无需 SESSDATA 登录态）。
    mode=3 按热度排序，cursor 翻页。
    """
    comments: List[Dict[str, Any]] = []
    cursor = 0
    max_pages = 10

    for _ in range(max_pages):
        if len(comments) >= max_count:
            break
        url = f"https://api.bilibili.com/x/v2/reply/main?oid={aid}&type=1&mode=3&next={cursor}"
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com/",
        })
        try:
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"评论请求失败 aid={aid}: {e}")
            break
        if data.get("code") != 0:
            break
        d = data.get("data", {})
        replies = d.get("replies")
        if not replies:
            break
        for r in replies:
            if len(comments) >= max_count:
                break
            try:
                c_text = r.get("content", {}).get("message", "")
                c_like = r.get("like", 0) or 0
                c_uname = r.get("member", {}).get("uname", "")
                comments.append({"content": c_text, "like": c_like, "user": c_uname})
            except Exception:
                continue
        next_cursor = d.get("cursor", {}).get("next", 0)
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(random.uniform(2, 4))
    return comments


def crawl_bilibili(
    keyword: str,
    max_videos: int = 20,
    max_comments_per_video: int = 50,
    timeout: int = 40,
    cookie_str: Optional[str] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "platform": "bilibili",
        "keyword": keyword,
        "video_count": 0,
        "videos": [],
        "errors": [],
    }
    if not HAS_BILI_API:
        result["errors"].append("bilibili-api-python 未安装")
        return result
    if not cookie_str:
        cookie_str = os.getenv("COOKIE_B", "").strip()
    if not cookie_str:
        result["errors"].append("B站 Cookie 为空")
        return result

    try:
        from bilibili_api import video, Credential
        from bilibili_api.search import search_by_type, SearchObjectType, OrderVideo
    except Exception as e:
        result["errors"].append(f"导入 bilibili_api 失败: {e}")
        return result

    cookies_dict = parse_cookie_str(cookie_str)
    try:
        credential = Credential.from_cookies(cookies_dict)
    except Exception as e:
        result["errors"].append(f"Credential 构建失败: {e}")
        return result

    async def _run():
        try:
            search_res = await asyncio.wait_for(
                search_by_type(
                    keyword=keyword,
                    search_type=SearchObjectType.VIDEO,
                    order_type=OrderVideo.TOTALRANK,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            result["errors"].append(f"B站搜索超时: {keyword}")
            return
        except Exception as e:
            result["errors"].append(f"B站搜索失败: {e}")
            return

        items = []
        if isinstance(search_res, dict):
            items = search_res.get("result", []) or []
        items = items[:max_videos]

        for idx, item in enumerate(items):
            try:
                bvid = item.get("bvid", "")
                title = re.sub(r"<[^>]+>", "", item.get("title", "")).strip()
                play = item.get("play", 0) or 0
                author = item.get("author", "") or item.get("name", "")
                if not bvid:
                    continue

                video_url = f"https://www.bilibili.com/video/{bvid}"
                v = video.Video(bvid=bvid, credential=credential)
                try:
                    info = await asyncio.wait_for(v.get_info(), timeout=15)
                except Exception as e:
                    result["errors"].append(f"视频详情失败 {bvid}: {e}")
                    info = {}
                aid = info.get("aid") or item.get("aid")

                comments: List[Dict[str, Any]] = []
                if aid:
                    try:
                        comments = _fetch_bilibili_comments(aid, max_comments_per_video)
                    except Exception as e:
                        result["errors"].append(f"评论抓取失败 {bvid}: {e}")

                result["videos"].append({
                    "title": title, "bvid": bvid, "play": play,
                    "author": author, "url": video_url, "comments": comments,
                })
                time.sleep(random.uniform(2, 5))
            except Exception as e:
                result["errors"].append(f"视频处理异常: {e}")
                continue
        result["video_count"] = len(result["videos"])

    try:
        asyncio.run(asyncio.wait_for(_run(), timeout=timeout + max_videos * 20))
    except asyncio.TimeoutError:
        result["errors"].append(f"B站整体抓取超时")
    except Exception as e:
        result["errors"].append(f"B站抓取异常: {e}")
    return result


# ----------------------------------------------------------------------
# 批量抓取多款鼠标垫
# ----------------------------------------------------------------------
def crawl_for_pads(
    pad_names: List[str],
    max_videos: int = 20,
    max_comments: int = 50,
    timeout: int = 40,
    cookie_b: Optional[str] = None,
) -> Dict[str, Any]:
    """针对多款鼠标垫抓取 B站 测评视频和评论。

    合并关键词「A B 鼠标垫测评」抓横向对比视频 + 每款单独补充。
    """
    if not pad_names:
        return {"error": "pad_names 为空"}

    combined_keyword = " ".join(pad_names[:3]) + " 鼠标垫测评"

    b_data = crawl_bilibili(
        keyword=combined_keyword,
        max_videos=max_videos,
        max_comments_per_video=max_comments,
        timeout=timeout,
        cookie_str=cookie_b,
    )

    per_pad: Dict[str, Any] = {}
    for name in pad_names:
        per_pad[name] = crawl_bilibili(
            keyword=f"{name} 鼠标垫测评",
            max_videos=min(5, max_videos),
            max_comments_per_video=min(20, max_comments),
            timeout=timeout,
            cookie_str=cookie_b,
        )

    return {
        "pad_names": pad_names,
        "combined_keyword": combined_keyword,
        "bilibili": b_data,
        "per_pad": per_pad,
        "errors": b_data.get("errors", []),
    }


# ----------------------------------------------------------------------
# 数据落地：Excel / CSV
# ----------------------------------------------------------------------
def save_to_excel(data: Dict[str, Any], filepath: str = "mousepad_reviews.xlsx") -> str:
    try:
        from openpyxl import Workbook
    except ImportError:
        return _save_to_csv(data)

    wb = Workbook()
    ws = wb.active
    ws.title = "B站数据"
    ws.append(["视频标题", "BV号", "UP主", "播放量", "视频链接", "评论内容", "评论点赞", "评论者"])
    for v in data.get("bilibili", {}).get("videos", []):
        if not v.get("comments"):
            ws.append([v.get("title", ""), v.get("bvid", ""), v.get("author", ""),
                        v.get("play", 0), v.get("url", ""), "", "", ""])
        else:
            for c in v["comments"]:
                ws.append([v.get("title", ""), v.get("bvid", ""), v.get("author", ""),
                            v.get("play", 0), v.get("url", ""),
                            c.get("content", ""), c.get("like", 0), c.get("user", "")])
    wb.save(filepath)
    return filepath


def _save_to_csv(data: Dict[str, Any]) -> str:
    import csv
    path = "mousepad_reviews_bilibili.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["视频标题", "BV号", "UP主", "播放量", "视频链接", "评论内容", "评论点赞", "评论者"])
        for v in data.get("bilibili", {}).get("videos", []):
            if not v.get("comments"):
                w.writerow([v.get("title", ""), v.get("bvid", ""), v.get("author", ""),
                            v.get("play", 0), v.get("url", ""), "", "", ""])
            else:
                for c in v["comments"]:
                    w.writerow([v.get("title", ""), v.get("bvid", ""), v.get("author", ""),
                                v.get("play", 0), v.get("url", ""),
                                c.get("content", ""), c.get("like", 0), c.get("user", "")])
    return path


# ----------------------------------------------------------------------
# 报告摘要（增强版：维度化提取 + 使用场景识别 + 情感分析）
# ----------------------------------------------------------------------

# 六维关键词词典 — 鼠标垫评价按维度归类
DIMENSION_KEYWORDS = {
    "glide": {       # 顺滑度
        "pos": ["顺滑", "丝滑", "流畅", "滑", "飞", "跟枪", "拉枪", "启动快", "启动迅速", "速度", "快"],
        "neg": ["涩", "阻力大", "卡", "慢", "拖", "粘", "不滑", "启动慢", "启动费力"],
    },
    "control": {     # 操控性
        "pos": ["精准", "制动", "急停", "微调", "定位", "控枪", "压枪", "停止", "操控", "控制"],
        "neg": ["飘", "滑过头", "停不住", "不准", "失控", "刹不住", "不稳"],
    },
    "durability": {  # 耐用性
        "pos": ["耐用", "耐造", "寿命", "不变", "不掉", "牢固", "结实", "可靠"],
        "neg": ["磨损", "掉渣", "涂层掉", "起毛", "变形", "褪色", "不耐用", "坏了", "寿命短"],
    },
    "comfort": {     # 舒适度
        "pos": ["舒服", "舒适", "柔软", "细腻", "手感好", "亲肤", "不硌手", "不磨手", "回弹"],
        "neg": ["硌手", "磨手", "硬", "粗糙", "异味", "臭", "刺鼻", "不舒服", "冰凉"],
    },
    "compatibility": {  # 兼容性
        "pos": ["兼容", "通用", "适应", "贴脚", "传感器", "任何鼠标", "所有鼠标", "稳定", "不掉帧"],
        "neg": ["丢帧", "跳帧", "不兼容", "挑鼠标", "挑脚贴", "不识别", "断触"],
    },
    "value": {       # 性价比
        "pos": ["性价比", "值", "便宜", "实惠", "划算", "价格", "物超所值", "香", "推荐", "入门"],
        "neg": ["贵", "不值", "智商税", "溢价", "太贵", "坑", "后悔", "买亏"],
    },
}

# 使用场景关键词
SCENE_KEYWORDS = {
    "FPS":     ["CS", "Valorant", "瓦", "彩虹六号", "OW", "守望", "FPS", "射击", "甩枪", "大范围", "拉枪线", "低敏", "edpi"],
    "MOBA":    ["LOL", "英雄联盟", "Dota", "MOBA", "小范围", "高敏", "手腕流", "快速点击"],
    "办公":    ["办公", "日常", "工作", "长时间", "久坐", "文书", "码字", "写代码", "修图", "设计"],
    "潮湿":    ["潮湿", "湿度", "汗手", "出汗", "防水", "防汗", "夏天", "闷热", "手汗"],
    "玻璃垫":  ["玻璃", "glass", "硬垫", "硬质", "树脂", "金属"],
    "布垫":    ["布垫", "软垫", "布面", "织物", "纺织"],
}

# 材质关键词
MATERIAL_KEYWORDS = {
    "布面":    ["布面", "布垫", "织物", "纺织", "软垫", "编织"],
    "涂层":    ["涂层", "coating", "镀膜"],
    "玻璃":    ["玻璃", "glass", "钢化玻璃", "磨砂玻璃"],
    "树脂":    ["树脂", "塑料", "硬垫", "PC", "ABS"],
    "混合":    ["混合", "复合", "混纺"],
}

# 技术参数关键词
TECH_SPEC_KEYWORDS = {
    "厚度":     ["厚度", "mm", "薄", "厚", "毫米"],
    "尺寸":     ["尺寸", "大小", "号", "L", "M", "S", "XL", "XXL", "cm", "大号", "中号", "小号"],
    "底面":     ["底面", "底胶", "防滑", "背胶", "PU", "橡胶", "聚氨酯"],
    "边缘":     ["边缘", "包边", "封边", "切边", "锁边", "缝边"],
}

# 全局正负面词典（_classify_comment / _sentiment_strength 共用）
POSITIVE_KEYWORDS = [
    "顺滑", "丝滑", "好用", "舒服", "推荐", "值", "性价比", "耐用", "漂亮",
    "精准", "制动好", "跟枪", "质感", "细腻", "不硌手", "稳定",
    "神器", "真香", "优秀", "赞", "牛", "完美", "顶",
]
NEGATIVE_KEYWORDS = [
    "难用", "差", "垃圾", "硌手", "异味", "掉渣", "涂层掉", "磨损快",
    "打滑", "发涩", "太慢", "太快", "不跟手", "飘", "卡", "贵",
    "不值", "后悔", "失望", "翻车", "坑", "渣", "烂",
]


def _extract_mentions(text: str, pad_names: List[str]) -> List[str]:
    """检测文本中提到了哪些鼠标垫名称。"""
    text_lower = text.lower()
    return [n for n in pad_names if n.lower() in text_lower]


def _classify_comment(text: str) -> str:
    """简单情感分类：pos / neg / neutral。"""
    t = text.lower()
    pos_hit = sum(1 for k in POSITIVE_KEYWORDS if k in t)
    neg_hit = sum(1 for k in NEGATIVE_KEYWORDS if k in t)
    if pos_hit > neg_hit and pos_hit > 0:
        return "pos"
    if neg_hit > pos_hit and neg_hit > 0:
        return "neg"
    return "neutral"


def _dimension_sentiment(text: str) -> Dict[str, dict]:
    """对一条评论做六维情感分析，返回每个维度的 pos/neg 命中数。

    Returns: {"glide": {"pos": int, "neg": int}, ...}
    """
    result = {}
    t = text.lower()
    for dim, kw in DIMENSION_KEYWORDS.items():
        pos_hits = sum(1 for k in kw["pos"] if k in t)
        neg_hits = sum(1 for k in kw["neg"] if k in t)
        result[dim] = {"pos": pos_hits, "neg": neg_hits}
    return result


def _extract_scenes(text: str) -> List[str]:
    """提取评论中提及的使用场景。"""
    scenes = []
    t = text.lower()
    for scene, keywords in SCENE_KEYWORDS.items():
        if any(k.lower() in t for k in keywords):
            scenes.append(scene)
    return scenes


def _extract_materials(text: str) -> List[str]:
    """提取评论中提及的材质类型。"""
    mats = []
    t = text.lower()
    for mat, keywords in MATERIAL_KEYWORDS.items():
        if any(k.lower() in t for k in keywords):
            mats.append(mat)
    return mats


def _extract_tech_specs(text: str) -> Dict[str, int]:
    """从评论中提取技术参数讨论。"""
    specs = {}
    t = text.lower()
    for spec, keywords in TECH_SPEC_KEYWORDS.items():
        hits = sum(1 for k in keywords if k.lower() in t)
        if hits > 0:
            specs[spec] = hits
    return specs


def _sentiment_strength(text: str) -> float:
    """量化评论情感强度：-2（强烈负面）到 +2（强烈正面）。

    考虑：正面词数量、负面词数量、程度副词、感叹号数量。
    """
    t = text.lower()
    pos = sum(1 for k in POSITIVE_KEYWORDS if k in t)
    neg = sum(1 for k in NEGATIVE_KEYWORDS if k in t)

    # 程度词加权
    strong_pos = sum(1 for k in ["非常", "超级", "太", "最", "很", "极", "绝"] if k in t)
    strong_neg = sum(1 for k in ["太", "非常", "超级", "最", "很", "极"] if k in t)
    exclamation = t.count("!") + t.count("！")

    # 基准分
    base = (pos - neg) / max(pos + neg, 1)

    # 程度加权
    if pos > neg:
        base += (strong_pos + exclamation) * 0.15
    elif neg > pos:
        base -= (strong_neg + exclamation) * 0.15

    return max(-2.0, min(2.0, base * 2.0))


def summarize_for_report(pad_names: List[str], crawl_data: Dict[str, Any]) -> Dict[str, Any]:
    """增强版报告摘要：维度化提取 + 使用场景识别 + 情感强度量化。

    Returns:
        {
            "bilibili": {video_count, total_comments, top_videos, high_like_comments},
            "pad_mentions": {
                name: {
                    "mention_count": int,
                    "pros": [str],  "cons": [str],
                    "sentiment_strength": float,           # 综合情感强度 (-2~2)
                    "dimension_analysis": {                # 六维情感分析
                        "glide": {"pos_count": int, "neg_count": int, "net": int},
                        ...
                    },
                    "scenes": [str],                       # 提及的使用场景
                    "materials": [str],                    # 提及的材质
                    "tech_specs": {spec: count},           # 技术参数讨论
                }
            },
            "dimension_summary": {dim_key: {total_pos, total_neg, net}},  # 全局六维汇总
            "scene_summary": {scene: count},                              # 全局场景汇总
            "errors": [str],
        }
    """
    summary: Dict[str, Any] = {
        "bilibili": {"video_count": 0, "total_comments": 0,
                     "top_videos": [], "high_like_comments": []},
        "pad_mentions": {},
        "dimension_summary": {},
        "scene_summary": {},
        "errors": crawl_data.get("errors", []),
    }

    # 初始化每个垫的 mention 结构
    for name in pad_names:
        summary["pad_mentions"][name] = {
            "mention_count": 0,
            "pros": [], "cons": [],
            "sentiment_strength": 0.0,
            "dimension_analysis": {dim: {"pos_count": 0, "neg_count": 0, "net": 0}
                                   for dim in DIMENSION_KEYWORDS},
            "scenes": [],
            "materials": [],
            "tech_specs": {},
        }

    b_data = crawl_data.get("bilibili", {})
    b_videos = b_data.get("videos", [])
    b_all_comments = []

    for v in b_videos:
        for c in v.get("comments", []):
            b_all_comments.append({
                "content": c.get("content", ""),
                "like": c.get("like", 0),
                "video_title": v.get("title", ""),
                "video_url": v.get("url", ""),
            })
            full_text = (v.get("title", "") + " " + c.get("content", ""))
            content = c.get("content", "")

            for name in _extract_mentions(full_text, pad_names):
                entry = summary["pad_mentions"][name]
                entry["mention_count"] += 1

                # 维度情感分析
                dim_sent = _dimension_sentiment(content)
                for dim, scores in dim_sent.items():
                    entry["dimension_analysis"][dim]["pos_count"] += scores["pos"]
                    entry["dimension_analysis"][dim]["neg_count"] += scores["neg"]
                    entry["dimension_analysis"][dim]["net"] = (
                        entry["dimension_analysis"][dim]["pos_count"]
                        - entry["dimension_analysis"][dim]["neg_count"]
                    )

                # 累积情感强度
                entry["sentiment_strength"] += _sentiment_strength(content)

                # 使用场景
                for scene in _extract_scenes(content):
                    if scene not in entry["scenes"]:
                        entry["scenes"].append(scene)

                # 材质
                for mat in _extract_materials(content):
                    if mat not in entry["materials"]:
                        entry["materials"].append(mat)

                # 技术参数
                tech = _extract_tech_specs(content)
                for spec, count in tech.items():
                    entry["tech_specs"][spec] = entry["tech_specs"].get(spec, 0) + count

                # pros/cons
                sentiment = _classify_comment(content)
                if sentiment == "pos" and len(entry["pros"]) < 8:
                    entry["pros"].append(content[:150])
                elif sentiment == "neg" and len(entry["cons"]) < 8:
                    entry["cons"].append(content[:150])

    # 归一化情感强度
    for name in pad_names:
        mc = summary["pad_mentions"][name]["mention_count"]
        if mc > 0:
            summary["pad_mentions"][name]["sentiment_strength"] = round(
                summary["pad_mentions"][name]["sentiment_strength"] / mc, 2
            )

    # 全局六维汇总
    for dim in DIMENSION_KEYWORDS:
        total_pos = sum(summary["pad_mentions"][n]["dimension_analysis"][dim]["pos_count"]
                        for n in pad_names)
        total_neg = sum(summary["pad_mentions"][n]["dimension_analysis"][dim]["neg_count"]
                        for n in pad_names)
        summary["dimension_summary"][dim] = {
            "total_pos": total_pos, "total_neg": total_neg,
            "net": total_pos - total_neg,
        }

    # 全局场景汇总
    all_scenes: Dict[str, int] = {}
    for name in pad_names:
        for scene in summary["pad_mentions"][name]["scenes"]:
            all_scenes[scene] = all_scenes.get(scene, 0) + 1
    summary["scene_summary"] = dict(sorted(all_scenes.items(), key=lambda x: x[1], reverse=True))

    # B站视频统计
    b_top_videos = sorted(b_videos, key=lambda x: x.get("play", 0), reverse=True)[:5]
    summary["bilibili"]["video_count"] = len(b_videos)
    summary["bilibili"]["total_comments"] = len(b_all_comments)
    summary["bilibili"]["top_videos"] = [
        {"title": v.get("title", ""), "url": v.get("url", ""),
         "play": v.get("play", 0), "author": v.get("author", "")}
        for v in b_top_videos
    ]
    summary["bilibili"]["high_like_comments"] = [
        {"content": c["content"][:200], "like": c["like"], "video_title": c["video_title"]}
        for c in sorted(b_all_comments, key=lambda x: x["like"], reverse=True)[:10]
    ]

    # 合并单品搜索结果
    per_pad = crawl_data.get("per_pad", {})
    for name, pp_data in per_pad.items():
        entry = summary["pad_mentions"].setdefault(name, {
            "mention_count": 0, "pros": [], "cons": [],
            "sentiment_strength": 0.0,
            "dimension_analysis": {dim: {"pos_count": 0, "neg_count": 0, "net": 0}
                                   for dim in DIMENSION_KEYWORDS},
            "scenes": [], "materials": [], "tech_specs": {},
        })
        pp_videos = pp_data.get("videos", []) if isinstance(pp_data, dict) else []
        for v in pp_videos:
            for c in v.get("comments", []):
                content = c.get("content", "")
                dim_sent = _dimension_sentiment(content)
                for dim, scores in dim_sent.items():
                    entry["dimension_analysis"][dim]["pos_count"] += scores["pos"]
                    entry["dimension_analysis"][dim]["neg_count"] += scores["neg"]
                    entry["dimension_analysis"][dim]["net"] = (
                        entry["dimension_analysis"][dim]["pos_count"]
                        - entry["dimension_analysis"][dim]["neg_count"]
                    )
                for scene in _extract_scenes(content):
                    if scene not in entry["scenes"]:
                        entry["scenes"].append(scene)
                sentiment = _classify_comment(content)
                if sentiment == "pos" and len(entry["pros"]) < 10:
                    entry["pros"].append(content[:150])
                    entry["mention_count"] += 1
                elif sentiment == "neg" and len(entry["cons"]) < 10:
                    entry["cons"].append(content[:150])
                    entry["mention_count"] += 1

    # ---- 提取每款鼠标垫的 Top 关键词 ----
    for name in pad_names:
        entry = summary["pad_mentions"].get(name, {})
        all_pros_text = " ".join(entry.get("pros", []))
        all_cons_text = " ".join(entry.get("cons", []))
        all_text = all_pros_text + " " + all_cons_text

        # 正面关键词频率统计
        pos_freq: Dict[str, int] = {}
        for dim, kw in DIMENSION_KEYWORDS.items():
            for k in kw["pos"]:
                if len(k) >= 2:  # 过滤单字
                    count = all_text.count(k)
                    if count > 0:
                        pos_freq[k] = pos_freq.get(k, 0) + count
        entry["top_pos_keywords"] = [
            kw for kw, _ in sorted(pos_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        # 负面关键词频率统计
        neg_freq: Dict[str, int] = {}
        for dim, kw in DIMENSION_KEYWORDS.items():
            for k in kw["neg"]:
                if len(k) >= 2:
                    count = all_text.count(k)
                    if count > 0:
                        neg_freq[k] = neg_freq.get(k, 0) + count
        entry["top_neg_keywords"] = [
            kw for kw, _ in sorted(neg_freq.items(), key=lambda x: x[1], reverse=True)[:3]
        ]

    return summary


# ----------------------------------------------------------------------
# 安全包装
# ----------------------------------------------------------------------
def crawl_safe(
    pad_names: List[str],
    max_videos: int = 10,
    max_comments: int = 30,
    timeout: int = 30,
    cookie_b: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """供后端调用的安全包装：抓取失败/超时返回 None，绝不抛异常。"""
    try:
        raw = crawl_for_pads(
            pad_names=pad_names,
            max_videos=max_videos,
            max_comments=max_comments,
            timeout=timeout,
            cookie_b=cookie_b,
        )
        summary = summarize_for_report(pad_names, raw)
        summary["_raw"] = raw
        return summary
    except Exception as e:
        logger.error(f"crawl_safe 异常: {e}")
        return None


# ----------------------------------------------------------------------
# 主函数：独立运行
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("鼠标垫测评数据采集脚本（B站）")
    print("仅供个人学习研究，严禁商业用途")
    print("=" * 60)

    user_input = input("\n请输入要对比的鼠标垫名称（逗号分隔，例如: Artisan Zero,ZOWIE G-SR）:\n> ").strip()
    if not user_input:
        print("未输入鼠标垫名称，退出。")
        sys.exit(0)

    pad_names = [n.strip() for n in user_input.split(",") if n.strip()]
    if len(pad_names) < 2:
        print("至少需要 2 款鼠标垫进行对比。")
        sys.exit(0)

    max_v = int(input("最多抓取视频数（默认 20）: ").strip() or "20")

    print(f"\n开始抓取：{'、'.join(pad_names)}（B站 {max_v} 个视频）\n")

    raw_data = crawl_for_pads(
        pad_names=pad_names,
        max_videos=max_v,
        max_comments=50,
        timeout=60,
    )

    out_path = os.path.join(os.getcwd(), "mousepad_reviews.xlsx")
    saved = save_to_excel(raw_data, out_path)
    print(f"\n[完成] 数据已保存到: {saved}")

    summary = summarize_for_report(pad_names, raw_data)
    print("\n" + "=" * 60)
    print("抓取摘要")
    print("=" * 60)
    print(f"B站：{summary['bilibili']['video_count']} 个视频，{summary['bilibili']['total_comments']} 条评论")
    print("\n各鼠标垫口碑提及：")
    for name, m in summary["pad_mentions"].items():
        print(f"  - {name}: 提及 {m['mention_count']} 次，正面 {len(m['pros'])} 条，负面 {len(m['cons'])} 条")

    if summary["errors"]:
        print("\n[警告] 抓取过程中出现以下错误（已跳过）：")
        for e in summary["errors"][:10]:
            print(f"  - {e}")

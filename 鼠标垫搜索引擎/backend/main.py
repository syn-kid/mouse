from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from algorithm import rank_mousepads, compute_pad_comparison, generate_comparison_analysis
from data import GAMES, MOUSEPADS
import os
import logging

logger = logging.getLogger("main")

app = FastAPI(title="DPI2Pad", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
IMG_DIR = os.path.join(FRONTEND_DIR, "img")
PADS_IMG_DIR = os.path.join(FRONTEND_DIR, "images", "pads")

# Serve processed images
if os.path.isdir(IMG_DIR):
    app.mount("/img", StaticFiles(directory=IMG_DIR), name="images")

# Serve crawled product images
if os.path.isdir(PADS_IMG_DIR):
    app.mount("/images/pads", StaticFiles(directory=PADS_IMG_DIR), name="pads_images")


@app.get("/api/search")
def search(
    mouse_dpi: float = Query(..., ge=100, le=36000, description="Mouse DPI"),
    game_sens: float = Query(..., ge=0.01, le=100, description="In-game sensitivity"),
    game_id: str = Query("general", description="Game identifier"),
    surface_filter: str = Query(None, description="Optional surface type filter: speed/balanced/control/rough"),
):
    valid_games = list(GAMES.keys())
    if game_id not in valid_games:
        game_id = "general"
    return rank_mousepads(mouse_dpi, game_sens, game_id, surface_filter)


@app.get("/api/games")
def list_games():
    return [
        {"id": k, "name": v["name"], "category": v["category"], "note": v["note"]}
        for k, v in GAMES.items()
    ]


@app.get("/api/genres")
def genres():
    return list_games()


@app.get("/api/pads")
def pads():
    from data import MOUSEPADS
    return {"pads": MOUSEPADS}


@app.get("/api/pad/{pad_id}")
def pad_detail(pad_id: str):
    """Return full pad detail with dimensions, purchase links, and comparison data."""
    pad = next((p for p in MOUSEPADS if p["id"] == pad_id), None)
    if not pad:
        return JSONResponse(status_code=404, content={"error": "Mousepad not found"})

    comparison = compute_pad_comparison(pad_id)

    return {
        "pad": {
            "id": pad["id"],
            "name": pad["name"],
            "brand": pad["brand"],
            "surface": pad["surface"],
            "material": pad["material"],
            "static_friction": pad["static_friction"],
            "dynamic_friction": pad["dynamic_friction"],
            "stopping_power": pad["stopping_power"],
            "speed_rating": pad["speed_rating"],
            "sizes": pad["sizes"],
            "thickness": pad["thickness"],
            "price_cny": pad["price_cny"],
            "image": pad.get("image"),
            "desc": pad["desc"],
            "detail_desc": pad.get("detail_desc", pad["desc"]),
            "desc_source": pad.get("desc_source", ""),
            "dimensions": pad.get("dimensions"),
            "purchase_links": pad.get("purchase_links"),
        },
        "comparison": comparison,
    }


@app.post("/api/compare")
def compare_pads(
    pad_ids: str = Body(..., description="Comma-separated pad IDs"),
    mouse_dpi: float = Body(None, ge=100, le=36000),
    game_sens: float = Body(None, ge=0.01, le=100),
    game_id: str = Body("general"),
    enable_crawl: bool = Body(False, description="是否启用 B站 社区测评爬虫"),
    max_videos: int = Body(10, description="B站最多抓取视频数"),
    max_comments: int = Body(30, description="每个视频最多评论数"),
    crawl_timeout: int = Body(60, description="爬虫整体超时（秒）"),
):
    """Compare selected mousepads and generate analysis report.

    当 enable_crawl=True 时，会同步爬取 B站 的测评视频和评论，
    整合到最终对比报告中。爬虫失败会自动降级为纯算法报告（不中断请求）。
    Cookie 通过环境变量 COOKIE_B 传入。
    """
    ids = [pid.strip() for pid in pad_ids.split(",") if pid.strip()]
    if len(ids) < 2:
        return JSONResponse(status_code=400, content={"error": "请至少选择 2 款鼠标垫"})
    if len(ids) > 5:
        return JSONResponse(status_code=400, content={"error": "最多选择 5 款鼠标垫"})

    crawl_summary = None
    if enable_crawl:
        selected_pads = [p for p in MOUSEPADS if p["id"] in ids]
        pad_names = [p["name"] for p in selected_pads] or ids

        try:
            from crawler import crawl_safe
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    crawl_safe,
                    pad_names=pad_names,
                    max_videos=max_videos,
                    max_comments=max_comments,
                    timeout=max(30, crawl_timeout // 2),
                    cookie_b=os.getenv("COOKIE_B", "").strip() or None,
                )
                try:
                    crawl_summary = future.result(timeout=crawl_timeout)
                except concurrent.futures.TimeoutError:
                    logger.warning(f"爬虫超时（{crawl_timeout}s），降级为纯算法报告")
                    crawl_summary = None
        except Exception as e:
            logger.warning(f"爬虫调用失败，降级为纯算法报告: {e}")
            crawl_summary = None

    return generate_comparison_analysis(ids, mouse_dpi, game_sens, game_id, crawl_summary=crawl_summary)


@app.get("/")
def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

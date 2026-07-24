# AI 交接本

## 当前状态
- 项目版本：v1.0.0
- 当前分支：main
- 服务端口：http://127.0.0.1:8000

## 用户偏好（摘要）
- 中文沟通，语气直接，少废话多做事。
- 审美：白底玻璃质感、舞台光照、iOS 原生感、物理动画。
- 技术洁癖：前端零框架依赖，后端轻量，数据驱动。

## 工作区地图
- `backend/main.py` — FastAPI 入口，路由 / CORS / 静态文件
- `backend/algorithm.py` — 匹配算法核心（cm/360 → 分档 → 摩擦距离 → 排名）
- `backend/data.py` — 17 款鼠标垫数据库 + 12 款游戏 Yaw 校准
- `frontend/index.html` — 原生 HTML/CSS/JS 前端页面
- `docs/` — 文档和记忆

- 2026-07-24：项目整合 — 部署前清理
  - 删除根目录 9 个临时验证脚本（verify_*.py / find_imgs.py / test_urls.py / check_context.py / parse_amazon.py）
  - 删除 `frontend/img/` 旧占位图目录（17 张 PNG，已废弃）
  - 删除 `backend/extract_imgs.py`（一次性搜狐评测图提取脚本）
  - 删除 `backend/image_crawler.py` + `backend/manual_urls.json`（爬图工具，非运行时依赖）
  - 初始化 Git 仓库 + 创建 `.gitignore`（排除 .venv / __pycache__ / IDE 配置等）
  - 语法检查全部通过（main.py / algorithm.py / data.py / crawler.py）

## 已完成工作日志
- 2026-07-19：创建项目规则三件套（AGENTS.md / AI_HANDOFF.md / PROJECT_MEMORY.md）
- 2026-07-19：鼠标垫展示页面布局优化 — 搜索框紧凑化、网格最多4列、方形图片、完整摩擦系数标签+单位、描述颜色优化、低敏+速度→滑面改名、游戏社区风格重构
- 2026-07-19：展示模块全面 redesign — 卡片改为正方形 (aspect-ratio 1:1)、图片区域扩大至 60% (grid-template-rows: 3fr 2fr)、搜索栏移至顶部与 logo 同行内联、快捷预设改为 5 列网格大卡片 + 表面类型标注条、容器 max-width 扩至 1200px、hover 图片微缩放效果、新增 1100px/768px/480px 三档响应式断点
- 2026-07-19：卡片放大 30% + 匹配度亮蓝 — 桌面网格 4列→3列 (卡片增大约 33%)、容器扩至 1280px、卡片内文字等比放大 15-20%、匹配度分数改为亮蓝色 (#3b9eff) + glow 光晕 (22px/900 weight)、新增 900px 断点过渡到 2 列、移动端卡片 max-width 放宽至 420px
- 2026-07-19：表面类型筛选接入交互 + rough/control 重校准 — 筛选条改为可点击按钮（含「全部」选项，点击切换，再次点击取消）、API 新增 surface_filter 参数、后端算法 rough 锚点独立 (ideal: 6.5/4.8/7.0 vs control 5.3/4.0/5.8)、rough 评分权重调整为制动主导 (stopping 0.65)、推力权重整体减半 (max 5→3)、新增 cross-type 对称惩罚 (balanced→rough -5, control→speed -4)
- 2026-07-19：实时搜索 — DPI/灵敏度输入框添加 input 事件监听 + 200ms 防抖、游戏下拉框 change 事件即时触发、搜索按钮保留作为备用触发方式
- 2026-07-20：界面结构+交互修复大改版
  - 移除快捷预设模块和表面类型筛选模块（HTML/CSS/JS 全部清理）
  - 输入区域重构为独立 Hero Card（.input-hero），居中、更大更突出，舞台光顶部渐变效果
  - 为 17 款鼠标垫补全官方详细描述（detail_desc），含材质、尺寸、表面特性、适用场景，均注明来源（desc_source）
  - 卡片底部新增 pad-detail 区域展示全面概括文本 + 来源标注
  - 修复选择逻辑：移除首卡自动 top-pick，实现左键点击切换选中（单选模式：点击选中 → 点其他切换 → 点已选中的取消）
  - 选中态 CSS：亮蓝边框 (#3b9eff) + glow 双层阴影 + 微背景提亮
  - 卡片 grid 由 2 行 (3fr 2fr) 改为 3 行 (3fr 2fr auto)，移除 aspect-ratio 限制以容纳详细描述
  - algorithm.py API 响应新增 detail_desc / desc_source 字段透传
- 2026-07-20：产品详情弹窗 + 六维雷达图 + 对比系统
  - 新增双击已选中卡片 → 弹出产品详情 Modal（毛玻璃全屏遮罩 + 玻璃质感卡片）
  - Modal 双栏布局：左侧产品图 + SVG 六维雷达图（纯 DOM API 绘制，600ms 入场动画），右侧维度评分卡 + 详细描述 + 四平台购买链接按钮（京东/淘宝/Amazon/官网）
  - 六维评估体系：顺滑度、操控性、耐用性、舒适度、兼容性、性价比（每维度 1-10 分）
  - data.py 为 17 款鼠标垫全部新增 `dimensions` 和 `purchase_links` 字段
  - algorithm.py 新增 `compute_pad_comparison()` — 按维度全量排序，返回 rank/percentile/top3
  - main.py 新增 `GET /api/pad/{pad_id}` 端点（含 404 处理）
  - 对比表：六行维度排名表，绿色进度条 + 排名 #X/17 + 百分位 + 前三名标注，CSS transition 动画
  - 关闭方式：X 按钮 / 点击遮罩 / Esc 键
  - 雷达图悬停 tooltip 显示精确分值
  - 响应式：768px 以下 Modal 切换为单栏，480px 以下购买链接纵向排列
- 2026-07-20：修复双击 Modal 无法打开的 bug
  - 根因：click 和 dblclick 事件冲突 — 双击未选中卡片时，第一次 click 选中、第二次 click 取消选中，导致 dblclick 触发时卡片不在选中状态
  - 修复：用 300ms 定时器区分单击/双击；两次快速点击同一卡片 → 视为双击直接打开 Modal；定时器到期 → 视为单击执行选择切换
- 2026-07-20：对比空间功能 — 多垫六维雷达图重叠对比 + 自动分析报告
  - 右下角浮动按钮（⚔ 对比空间），亮绿圆形 glow 效果
  - 对比 Modal（max-width 1100px，三区布局：产品选择 + 雷达图 + 分析报告）
  - 产品选择区：17 垫网格 + 表面类型筛选条 + 已选 chips（最多 5 款）
  - 多垫雷达图（SVG innerHTML，400×400 viewBox），5 色重叠多边形 + 图例
  - 后端 POST /api/compare：接收 pad_ids + 用户 DPI/灵敏度参数，生成逐维度对比分析 + 综合评述 + 推荐方案
  - algorithm.py 新增 generate_comparison_analysis()：纯算法驱动，无 AI 依赖
  - 前端本地 fallback：API 不可用时自动降级为本地维度对比报告
  - 响应式：900px 以下单栏，600px 以下按钮缩小
- 2026-07-20：对比报告重构 — 终极决策报告格式 + 用户画像匹配
  - algorithm.py 重构 build_enhanced_report()
    - ## 1. 综合推荐结论（算法+社区双源）
    - ## 2. 全网声量与口碑（好评率 + Top关键词 + 提及次数 + emoji评级）
    - ## 3. 核心性能雷达图（4维：顺滑度/操控性/质感做工/性价比，算法60%+社区40%综合评分）
    - ## 4. 详细对比分析（每垫：被夸最多/被骂最多/适合人群，引用原评论关键词）
    - ## 5. 最终购买建议（场景化表格：FPS/办公/预算/汗手）
    - 新增 _match_personas() 用户画像匹配（手腕流/手臂流/FPS/汗手/办公/MOBA/硬垫/耐久/性价比等）
    - 新增 _build_radar_text() 4维雷达文字描述
    - 新增 _build_buy_guide() 场景化购买建议表
  - crawler.py 新增 Top关键词提取（正面Top5+负面Top3，按评论出现频率统计）
  - crawler.py summarize_for_report() 增强
    - 六维维度化关键词词典（每个维度独立 pos/neg 词库）
    - 使用场景识别（FPS/MOBA/办公/潮湿/玻璃垫/布垫）
    - 材质提取（布面/涂层/玻璃/树脂/混合）
    - 技术参数提取（厚度/尺寸/底面/边缘）
    - 情感强度量化（-2~+2，含程度副词+感叹号加权）
    - 新增 dimension_summary / scene_summary / pad_mentions.dimension_analysis
  - 语法检查通过 + 端到端测试通过（五模块完整输出）
- 2026-07-20：爬虫+报告全链路打通
  - 放弃抖音方向（需桌面环境非headless浏览器，sandbox不支持），只保留 B站
  - 删除 crawler.py 全部抖音代码、简化 algorithm.py / main.py 参数
  - 修复前端 buildCompareReport 适配新报告格式（buildNewReport 五模块渲染）
  - 修复前端未传 enable_crawl 导致后端从不爬虫
  - 修复 crawler.py 重写时丢失 _extract_mentions / _classify_comment / POSITIVE_KEYWORDS / NEGATIVE_KEYWORDS
  - 修复简化报告路径详情总显示"数据不足"（改为算法维度填补）
  - 端到端测试通过：B站 5视频+27评论 → Artisan Zero 69.7%好评 / ZOWIE G-SR 77%好评 → 五模块报告输出
  - 修复服务崩溃后重启
- 2026-07-24：鼠标垫产品图片批量爬取 — 17/17 全部成功
  - 新增 `backend/image_crawler.py`：批量爬取脚本（HTML 解析 + 启发式筛选 + 下载 + manifest）
  - 新增 `backend/manual_urls.json`：人工标注的图片 URL（子代理搜索结果，16 条 + 1 条评测图）
  - 新增 `frontend/images/pads/`：17 张产品图（{pad_id}.jpg）+ `manifest.json`（源 URL/尺寸/文件名映射）+ `failed.json`
  - 策略优先级：`manual_urls.json` > `data.py image` 字段 > `official` 页面 HTML 解析
  - 反爬应对：429 限流重试（指数退避 12s/24s）+ 3 个 UA 轮换 + SSL 证书 fallback（`assets3.razerzone.com` 证书链不完整，第 2 次重试起 `verify=False`）
  - 图片源分布：Artisan 官方 CDN（doubaocdn，5 款）+ Amazon 主图（m.media-amazon.com，3 款）+ Shopify CDN（lgg 2 款）+ Logitech CDN（resource.logitechg.com）+ Razer Phoenix CDN（assets3.razerzone.com）+ Gamesense Shopify CDN + 搜狐评测图（glorious-ice 已停产，无官方图）
  - 透明 PNG 合成白底处理（logitech-g440 是 RGBA PNG，`save_as_jpeg` 中 paste 到白底）
  - 尺寸范围：480×480（xraypad-equate）到 5305×3316（glorious-ice），3 款小图（aqua-control-plus 520×520 / xraypad-equate 480×480 / skypad-glass 500×500）因官方源仅有此分辨率，已跳过尺寸检查下载
  - 宽高比过滤：MAX 2.2（防 banner 误判，razer-strider 首次拿到的 1920×700 hero banner 被拒）
  - `manifest.json` 每条记录含 `needs_review: true` — 视角是否为正俯视需人工核对（脚本无法自动判断）
  - 版权提示：产品图版权归原作者所有，商用前需获得授权；manifest.json 保留每张图的 `source_url` 便于追溯

## 未完成 / 待确认事项
- 移动端实际设备适配待验证（目前仅 CSS 响应式断点，未在真机测试）
- 档位分界线 (TIER_HIGH/MID_HIGH/MID/MID_LOW) 后续需一并确认
- 抖音爬虫代码已删除，DrissionPage 仍在 venv 中（可 clean）
- B站 Cookie 写在 test_e2e.py 中（已删除），正式使用时需通过环境变量 COOKIE_B 传入
- **17 张产品图需人工核对视角是否为正俯视**（manifest.json 中 `needs_review: true`）
- **data.py 的 `image` 字段未更新**：当前 5 款指向已失效的 artisan-jp.com 旧 URL，12 款为 None；下载的本地图片在 `frontend/images/pads/{pad_id}.jpg`，需决定是否更新 data.py 让前端引用本地路径
- **3 款低分辨率图**（aqua-control-plus 520 / xraypad-equate 480 / skypad-glass 500）官方源仅有此尺寸，如需更高清需另找源
- **glorious-ice 图片来自搜狐评测**（非官方产品图），且 data.py 中该垫描述（Hybrid Cloth/2mm 薄款）与实际产品（Glorious Element ICE 玻璃纤维/4mm）可能不符，待核对

## 每次任务完成后的固定动作
1. 更新本文件「已完成工作日志」。
2. 有新问题就更新「未完成事项」。
3. 跑一次语法检查：`python -m py_compile backend/*.py`
4. 最后说明 git status。

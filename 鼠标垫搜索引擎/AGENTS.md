# 项目规则

## 项目身份
这是一个鼠标垫量化推荐引擎（DPI2Pad），核心功能是 基于鼠标 DPI + 游戏内灵敏度 + 游戏 Yaw 值计算 cm/360，通过摩擦力学算法匹配最适合的鼠标垫、支持 12 款游戏 Yaw 校准和 17 款鼠标垫数据、提供 5 档灵敏度分档与动态推力微调。

## 新对话先做这件事
每次开始处理本项目前，先读：
- AGENTS.md（本文件）
- AI_HANDOFF.md
- docs/PROJECT_MEMORY.md

## 常用命令
- 启动：双击 `start.bat` 或 `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
- 初始化：双击 `setup.bat`（首次运行创建虚拟环境并安装依赖）
- 检查：`python -m py_compile backend/main.py backend/algorithm.py backend/data.py`
- 构建：本项目无编译构建步骤（原生 HTML/JS 前端 + Python 后端）

## 项目结构
```
DPI2Pad/
├── setup.bat            # 首次运行：创建虚拟环境 + 安装依赖
├── start.bat            # 启动服务
├── README.md
├── backend/
│   ├── main.py          # FastAPI 入口
│   ├── algorithm.py     # 匹配算法核心
│   ├── data.py          # 鼠标垫数据库 + 游戏 Yaw 值
│   └── requirements.txt
└── frontend/
    └── index.html       # 前端页面
```

## 用户偏好
- 交流语言：中文。
- 沟通风格：少废话，直接做，做完验证。
- 审美方向：白底玻璃质感、舞台光、iOS 原生感，拒绝廉价渐变和默认白框。
- 质量底线：不能为了性能牺牲视觉效果；留白营造"舞台感"；动画需有物理依据（匀速旋转、正弦呼吸、余弦衰减）。

## 红线（禁止做的事）
- 不要重写核心文件的大块逻辑，先定位再小改。
- 没有明确要求时，不要上传/推送/发布。
- 不要随意改动算法参数（摩擦权重、推力奖励、分档阈值），除非用户明确要求。
- 不要引入前端框架——前端保持原生 HTML/CSS/JS 零依赖。

## 记忆协议
当用户说"保留""喜欢""记住""保存一下"时：
1. 判断是代码、视觉、交互还是流程偏好。
2. 追加到 docs/PROJECT_MEMORY.md。
3. 记录日期、涉及文件、关键参数。

## 收尾动作
每次任务完成后：
1. 更新 AI_HANDOFF.md 的工作日志。
2. 跑一次语法检查：`python -m py_compile backend/*.py`
3. 说明哪些已提交、哪些是本地未提交产物。

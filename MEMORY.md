# MEMORY.md - 台股稳健投资组合量化模型构建项目记忆

## 1. 前置项目信息
- **项目名**: 台股稳健投资组合量化模型构建 (台股量化Antigravity)
- **创建/更新日期**: 2026-07-13
- **技术栈**: Python 3.x, NumPy, Pandas, QVeris, Shioaji, CSS/HTML
- **包管理器**: pip (`requirements.txt`, 虚拟环境 `.venv/`)
- **主要目录结构**:
  - `src/`: 核心业务逻辑与仪表盘生成代码（如 `src/risk_dashboard.py`）
  - `config/`: 股票池及分类配置（如 `config/universe_tw.csv`）
  - `dashboard/`: 静态网页输出目录（如 `dashboard/index.html`）
  - `data/`: 包含日更行情缓存、矩阵聚合缓存、本地模拟盘持仓及成交记录
  - `scripts/`: 包含本地 QA 脚本、一键发布脚本、本地服务和差异比较脚本

---

## 2. 长期项目上下文与架构决策
- **静态仪表盘 MVP 与公网部署**:
  - 核心展示采用纯静态 HTML 页面（`dashboard/index.html`）。
  - 已移除 Render 免费实例配置 `render.yaml`，转而将公网统一托管在 Cloudflare Pages（`https://futienchun.com/dashboard/`）。
- **稳健协方差与因子收缩模型**:
  - 模型方法使用 `multi-factor-shrink` 扩充多因子收缩框架（趋势强度、行业/主题相对强弱、AI 暴露、资金流与风险偏好等分数），搭配 Ledoit-Wolf 收缩协方差。
  - 支持通过 `--ai-tilt` 控制 AI 供应链倾斜约束（`moderate` 目标约 33% 且群组上限 35%，`strong` 目标约 38% 且群组上限 40%）。
- **行情只读与本地模拟盘隔离**:
  - 严格保持行情只读，默认不连接券商交易端下单。
  - 模拟盘落账使用本地 CSV 记录（`data/simulated_trades_*.csv` 和 `data/simulated_positions_latest.csv`）。
  - 通过交易日、建仓日、策略方法等生成稳定的 `trade_id` 以及分批序列号 `batch_seq`，确保多次重建时的幂等防重。
- **总经理执掌与 Agent 经理团队分工**:
  - 用户已正式授权我担任台股量化基金的 **总经理 (General Manager)**，统筹全盘战略、执行模拟盘交易授权决策。
  - 下设 4 位专业 Subagent 经理：
    1. `quant_research_manager`（量化研究经理）：负责 Alpha 股票池筛选、20日/60日动能与趋势打分。
    2. `risk_sentiment_manager`（风控与市场情绪经理）：负责大盘多空格局判断、RSI 情绪指数监控、100% 破均线清仓止损纪律。
    3. `trading_execution_manager`（交易执行经理）：负责模拟盘订单撮合、盘后待执行订单锁定、次日开盘价/盘中价真实撮合与零未来函数时序管理。
    4. `investor_relations_manager`（投资者关系经理）：负责将研究与交易记录翻译为零门槛的白话决策报告，维护 Dashboard 交互。
- **绝对收益与选股原则**:
  - 考核标准：绝对正收益（年化收益率 $\ge 8\%$），“亏损但跑赢大盘”算作不合格。
  - 选股策略：剔除宽基/高息 ETF 等被动稀释资产，100% 聚焦于有高 Alpha 驱动的独立成长股与动量龙头。
  - 止损与轮换：破 20 日均线或亏损达 4% 触发 100% 清仓止损，回收资金立即轮换投入最强动量龙头。
- **离线矩阵缓存设计 (`--offline-cache`)**:
  - 首次聚合时逐档读取 `data/cache/` 缓存 JSON，随后在 `data/matrix_cache/` 生成聚合的行情矩阵 `*.npz` 文件以加速后续回测，避免大量小文件读取带来的卡顿。

---

## 3. 踩坑记录与解决方案
- **TWSE API 限流与离线回退**:
  - TWSE 存在频繁请求 429 限流问题。已对抓取流程升级重试和跳过缓存逻辑。
  - 修复了 `latest_available_public_close_date()` 中 `offline_cache` 强制 False 的 Bug，确保能完全离线安全运行。
- **当月行情矩阵停滞问题**:
  - 曾因 `--offline-cache` 复用了不完整的月缓存导致数据无法更新。已在 `src/risk_dashboard.py` 中补充当月公开收盘资料的主动刷新逻辑。
- **模拟盘旧格式兼容**:
  - 针对旧版没有 `trade_id` 的模拟成交记录，采用交易日、标的和方向作为去重依据，在 Dashboard 中统一显示为“舊格式 2 筆”，避免被错误硬判为新批次。
- **Obsidian 同步变更**:
  - 曾经接入 Obsidian 自动同步，但在 2026-06-26 遵循用户要求，**已完全停用 Obsidian 自动同步与同步验证机制**。
- **服务器重启与自动挂载方案**:
  - 遇到系统/服务器重启时，后台配置的 Antigravity 内存级 Schedule 定时任务会被清空。
  - **终极解决方案**：为了防止重启/关机导致定时器失效，已在 macOS 用户层注册了系统级 LaunchAgent (`com.tonyfu.tw_quant_daily_update.plist`)，配置在每天 `13:45` 自动执行 `scripts/auto_daily_update.py`。即便系统重启或关机，只要开机登录即可由 `launchd` 自动拉起，无需手动激活。
- **自动网络重试与标记秒退机制**:
  - 针对网络波动、休眠后唤醒等导致的 API 登录或 Git 推送超时，在 `scripts/auto_daily_update.py` 中引入了自动网络重试（最多重试 3 次，间隔 30 秒）。
  - 为实现断线自动补更，配置了 LaunchAgent 每 30 分钟轮询一次。为避免频繁更新产生的 CPU 占用和冗余 git 推送，设计了成功日期标记文件 `data/.last_success_date`，今日已成功执行时可在 0.1 秒内快速退出。
- **硬编码月份限制导致停更**:
  - 曾因 `scripts/auto_daily_update.py` 中将重建参数硬编码为 `--end 2026-06` 导致跨月后行情停更，现已修改为动态获取当前月 `datetime.now().strftime("%Y-%m")`。
- **公网缓存与即时刷新问题**:
  - 为了保证在其他设备端能立刻看到最新的 Dashboard，采用了三重缓存清除方案：
    1. 在 `src/risk_dashboard.py` 中为生成的 HTML `<head>` 加入 `Cache-Control: no-cache, no-store, must-revalidate`、`Pragma` 和 `Expires` 等 Meta 元标签。
    2. 修改了 `scripts/publish_dashboard.py`，在同步发布时自动在静态网页仓库根目录下生成 Cloudflare Pages 识别的 `_headers` 配置文件，写入 `/dashboard/*` 下的所有资源返回 HTTP `Cache-Control` 强刷头，强制 CDN 及浏览器每次请求都进行最新验证。
    3. 升级了 `scripts/publish_dashboard.py`，在发布时自动向个人网站主导航 `index.html` 中的跳转链接以及其外联静态 CSS/JS 资源链接注入最新的秒级版本号参数（例如 `href="/dashboard/index.html?v=YYYYMMDDHHMMSS"`）。当用户从主页点击跳转时，强制浏览器完全穿透本地和 CDN 缓存获取最新的渲染页面。
- **不同脚本正则表达式提取冲突**:
  - 曾因 `sync_all_metrics.py` 和 `validate_research_brief_metrics.py` 中用于从 HTML 提取 `trade_count` 的正则表达式存在匹配顺序分歧，导致在新一天数据无待确认交易时（已有历史交易转观察）解析不一致，引起 QA 崩溃。已将两个脚本的正则表达式统一。
- **新股历史行情补齐与 Shioaji 30 天拉取限制**：
  - 往股票池引入新资产时，必须补全自回测起点（2024-01-01）至当下的全量历史日线 JSON 缓存，否则回测矩阵合并会发生序列不完整报错。
  - 由于部分台股上柜（OTC）股票（如 3491 昇達科）在第三方 QVeris / EODHD 数据源中缺失，降级改用 Shioaji 接口直接获取。
  - 针对 Shioaji `api.kbars` 接口单次拉取区间不能超过 30 天的硬性物理限制，设计了“每 25 天一段”的自动分段拉取并合并 the 方案（`sync_historical_new_stocks_shioaji.py`），且内置了登录自愈重试，保证了数据拉取的完整性。
- **知识库归档与二级目录编码避坑**：
  - 往 Obsidian 知识库中归档技术部署或财务分析等新笔记时，必须严格遵守 OKF 规范：禁止在正文使用双括号 `[[Wikilinks]]`，所有中文字符及空格链接必须进行 URL 编码（保留 `/`），采用相对路径 Markdown 链接。
  - 归档技术部署笔记时，禁止直接零散存放在一级类目根目录下（如 `09-网站部署与网络基础设施/`），必须遵循顺势归类原则建立二级子文件夹（如 `02-台股量化Dashboard部署与缓存控制/`）进行物理打包隔离，保持一级目录的高可读性。
  - 每次文件位置移动或新建，必须及时同步创建并重构父级与子级的 `index.md` 索引地图，最后在提交前运行 `verify_okf.py` 检查以实现 100% 格式绿灯通过。
- **每日简报 (Daily Summary) 与结构化量化看板重构**：
  - **背景原因**：为响应用户对组合盈亏、个股涨跌红黑榜、现金占比、以及已执行成交明细的综合追踪需求，在网页顶部/首个 Tab 处整合了包含核心量化 KPI 卡片、个股收益前/后三名涨跌幅排名，以及从成交 CSV 解析得出的股数均价明细表格的全新交互面板。
  - **样式规范**：在 f-string HTML 模板拼接中，所有 CSS 样式的大括号 `{` 与 `}` 必须双写为 `{{` 与 `}}` 避免语法冲突，颜色样式必须严格对齐系统现有的 `--neon-emerald` (positive) 与 `--crimson` (negative) 变量。



---

## 4. 常用运维与验证命令
- **日常短区间冒烟验证**:
  ```bash
  ./.venv/bin/python src/risk_dashboard.py --start 2024-01 --end 2024-06 --offline-cache --model-portfolio
  ```
- **正式日更（不落账，仅更新 Dashboard 数据）**:
  ```bash
  ./.venv/bin/python src/risk_dashboard.py --offline-cache --model-portfolio --model-build-date 2026-06-03 --model-method multi-factor-shrink --ai-tilt moderate --market-source public-close --market-mode close
  ```
- **正式模拟盘落账（更新模拟持仓 CSV）**:
  ```bash
  ./.venv/bin/python src/risk_dashboard.py --offline-cache --model-portfolio --model-build-date 2026-06-03 --model-method multi-factor-shrink --ai-tilt moderate --market-source public-close --market-mode close --execute-simulated-trades
  ```
- **运行本地 QA 回归测试**:
  ```bash
  ./.venv/bin/python scripts/run_local_qa_checks.py
  ```
- **一键构建、QA 并发布到 Cloudflare Pages**:
  ```bash
  ./.venv/bin/python scripts/publish_dashboard.py
  ```

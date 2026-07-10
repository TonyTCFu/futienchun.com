# MEMORY.md - 台股稳健投资组合量化模型构建项目记忆

## 1. 前置项目信息
- **项目名**: 台股稳健投资组合量化模型构建 (台股量化Antigravity)
- **创建/更新日期**: 2026-07-10
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
- **服务器重启与硬编码月份停更问题**:
  - 遇到系统/服务器重启时，后台配置的 Antigravity Schedule 定时任务会被清空，需要重新注册 Cron 定时器（`45 13 * * *`）。
  - 曾因 `scripts/auto_daily_update.py` 中将重建参数硬编码为 `--end 2026-06` 导致跨月后行情停更，现已修改为动态获取当前月 `datetime.now().strftime("%Y-%m")`。

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

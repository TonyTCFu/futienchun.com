# Loop Engineering Findings

## 2026-06-14 初始发现

- 项目路径：`/Users/tonyfu/Documents/稳健投资组合量化模型构建`。
- 当前项目已有 `README.md` 与 `.codex/PROJECT_CONTEXT.md`，但初始没有项目级 `AGENTS.md`、`task_plan.md`、`findings.md`、`progress.md`。
- 项目不是 Git 仓库；原版 autoresearch 要求 Git 分支、提交与 reset，因此不能原样使用。
- 可采用 Loop Engineering 的核心思想：目标设定、基线记录、小步实验、度量、保留/放弃、交接。
- 当前核心脚本为 `src/risk_dashboard.py`。
- 当前 Dashboard 路径为 `dashboard/index.html`。
- 默认资产池为 `config/universe_tw.csv`，包含 `sector`、`theme`、`ai_supply_chain` 字段。
- 项目安全边界已明确：只读行情、本地模拟盘、不连接券商交易端、不读取密钥。
- 常用模型方法包含 `drawdown-risk` 与 `multi-factor-shrink`。
- AI 供应链倾斜参数为 `--ai-tilt none|moderate|strong`，当前项目上下文记录使用 `moderate`。
- 模拟盘建议单落账通过 `--execute-simulated-trades` 写本地 CSV，不连接券商。
- 当前性能线索：完整 2024-01 至 2026-06 复跑约 33 秒，其中滚动回测约 27 秒。

## Skill 与 Agent 发现

- 已使用 `agent-teams-playbook` 方法定义多 Agent 协作。
- 已使用 `planning-with-files` 方法建立持久化计划文件。
- 台股/Shioaji 场景匹配 `shioaji` skill，但本项目当前默认不触碰真实交易。
- 台股分析可参考 `tw-stocker-consultant` 的数据驱动原则，但不替代本项目现有脚本。
- 原版 `autoresearch` 需要 Git 仓库，不适合作为当前直接执行机制。

## 2026-06-14 Agent 侦察汇总

- 文档/交接 Agent 确认：初始项目已有 `README.md` 与 `.codex/PROJECT_CONTEXT.md`，缺少 `AGENTS.md`、`task_plan.md`、`findings.md`、`progress.md`；当前已补齐。
- 工程运行 Agent 确认：主入口是 `src/risk_dashboard.py`，输出为 `dashboard/index.html`。
- 工程运行 Agent 确认：主要运行模式包括研究仪表盘、`--model-portfolio` 模拟模型盘、`--update-daily-market` 每日行情市值档；`--execute-simulated-trades` 只做本地模拟落账。
- 工程运行 Agent 确认：关键 CLI 参数包含 `--offline-cache`、`--allow-stale-cache`、`--data-source twse|shioaji|auto`、`--model-method drawdown-risk|shrink-minvar|multi-factor-shrink`、`--ai-tilt none|moderate|strong`。
- 工程运行 Agent 建议：完整复跑总耗时与滚动回测耗时应作为 Loop Engineering 的首要性能指标。
- 工程运行 Agent 建议：后续应记录 `data_freshness_date`、`dashboard_generated_ok`、`simulated_trade_idempotency`、`model_weight_sum`、`max_single_weight`。
- 量化/数据边界 Agent 确认：当前是台股稳健组合研究与 paper portfolio，不是实盘交易系统。
- 量化/数据边界 Agent 确认：`--model-portfolio`、`--update-daily-market`、`--execute-simulated-trades` 均不应连接券商交易端；源码关键词搜索未发现 `place_order/cancel_order/update_order` 等下单调用。
- 量化/数据边界 Agent 确认：数据源参数层是 `twse/shioaji/auto`；QVeris/EODHD 是项目上下文中的市值档 fallback 来源，不是主脚本 `--data-source` 选项。
- 量化/数据边界 Agent 确认：当前股票池是 15 檔人工核心资产池，不是全市场扫描；`ai_supply_chain=true` 不穿透 ETF 成分。
- 量化/数据边界 Agent 建议：增加 Risk Control Agent 与模拟盘执行 Agent 的职责边界，避免策略研究误触落账或交易端。

## 2026-06-14 第一轮 Loop 发现

- 短区间离线 Dashboard 冒烟暴露问题：不传 `--model-portfolio` 时，页面脚本仍引用 `default_trade_state_json`，但该变量只在模型盘分支内赋值。
- 最小修复：在进入 `model_portfolio` 分支前设置 `default_trade_state_json = "{}"`。
- 修复不改变策略、数据源、模拟盘落账或 Dashboard 正式产物，仅修复无模型盘页面生成路径。
- 修复后短区间离线 Dashboard 可生成到 `/tmp/tw_quant_loop_smoke.html`，输出大小约 4.95 MB。

## 2026-06-14 第二轮性能基线发现

- 完整复跑命令使用 `--offline-cache --model-portfolio --model-method multi-factor-shrink --ai-tilt moderate`，并输出到 `/tmp/tw_quant_loop_perf.html` 与 `/tmp/tw_quant_loop_perf_model.csv`，未覆盖正式 Dashboard 或正式模型盘 CSV。
- 完整复跑 `run_total_seconds=28.60`，命令成功生成临时仪表盘。
- 单独量测滚动回测 `backtest_seconds=27.9764`，样本为 15 檔资产、575 个收益观察值、74 次调仓。
- cProfile 画像显示回测内 148 次 `min_variance_weights()` 几乎占满全部耗时；其中 fallback 路径 `projected_gradient_min_variance()` 与 `project_capped_simplex()` 的重复 `np.clip()` / `sum()` 是主要瓶颈。
- 当前性能优化应优先减少每次最小方差求解的迭代成本；在未做结果一致性对照前，不建议调整回测窗口、调仓间隔或策略口径来“变快”。

## 2026-06-14 第三轮性能优化发现

- 已采用安全优化：`project_capped_simplex()` 在投影权重和接近 1 时提前停止，最终仍执行 clip、sum 检查和归一化兜底。
- `min_variance_weights()` 已支持可选 `initial` 参数，但正式滚动回测仍使用默认等权初始，避免 warm start 改变 fallback 迭代收敛路径。
- 安全优化后，单独回测 `backtest_seconds` 从本轮实测基线 `29.1977` 秒降至 `15.0964` 秒，约 `1.93x` 加速。
- 完整临时复跑 `run_total_seconds` 从上一轮记录 `28.60` 秒降至 `16.00` 秒。
- 结果一致性对照通过：sample/shrink 期末净值、最大回撤、平均换手率差异均在 `1e-12` 量级；sample/shrink 当前权重最大绝对差异约 `4.7e-14`。
- warm start 临时版本虽把回测降至约 `14.79` 秒，但净值与换手率出现小幅漂移，已撤回正式回测调用。
- 临时 active-set 求解器可把单独回测降至约 `0.06` 秒，但 sample 回测结果明显改变；该方案只适合作为后续研究分支，不应直接替换正式口径。

## 2026-06-14 第四轮模拟盘幂等性发现

- 新增 `--simulated-trades-output` 与 `--simulated-positions-output`，只在 `--execute-simulated-trades` 时用于重定向模拟成交与最新持仓输出；默认行为仍写正式 `data/simulated_*`。
- `build_trade_signals()` 与 Dashboard 渲染已支持同一个临时成交输出路径，避免临时验证被正式 `data/simulated_trades_交易日.csv` 历史记录压住。
- `load_simulated_trade_keys()` 已把 `status` 做 `strip().lower()` 标准化；`write_simulated_trades()` 同次写入时会同步更新 `existing_keys`，避免同次重复 key。
- 临时幂等性闭环通过：第一次 `/tmp` 落账新增 2 笔，第二次使用同一临时成交文件并把 `--model-execution-orders` 指向临时最新持仓，新增 0 笔。
- 第二次后 `/tmp/tw_quant_idempotency_trades.csv` 行数仍为 3 行、成交记录仍为 2 笔，`duplicate_executed_keys=0`；临时成交 hash 保持 `848d7a6270868b59dc0c75c09b0fab942a3d9f95f6c31bb783c1de30dd2610c7`。
- 第二次后 `/tmp/tw_quant_idempotency_positions.csv` 与 dated positions hash 均保持 `4336a4280bc05c0a0f611cf0d7d8d25e2a657f99e56f5d8970e30d90476208aa`，确认持仓未继续减少。
- 安全边界：验证命令使用 `--offline-cache --data-source twse`，未使用 `--data-source shioaji`、非离线 `auto`、`--update-daily-market` 或任何真实交易端参数。

## 2026-06-14 第五轮 Dashboard 报告解释发现

- Dashboard 最容易误读的点是“手动订单交易”“标记已执行 / 已执行”：这些看起来像真实订单或正式 CSV 落账，但实际只是浏览器 `localStorage` 页面检查状态。
- 已把手动交易区标题改为“模拟盘调仓确认”，按钮与状态改为“页面标记已确认 / 页面已确认 / 待确认”，表格列改为“页面复核 / 脚本落账”。
- 已在策略监控区加入“訊號口徑”说明：建议买入/卖出只代表本地模拟盘待确认，不会送到券商；已落账标的会转为观察，避免重复列为待确认清单。
- 已把模型盘 footer 明确为研究用途 paper portfolio：持仓、盈亏和建议单都只属于本地模拟盘，不是券商委托状态。
- 正式 `dashboard/index.html` 已重建，新增文案在生成 HTML 中可检索；旧歧义文案 `手动订单交易`、`标记已执行`、`后续我们可以再把已执行状态落成 CSV` 已无命中。
- 验证全程使用 `--offline-cache --data-source twse`；未使用 Shioaji、`--update-daily-market` 或 `--execute-simulated-trades`。

## 2026-06-14 第六轮风险归因与调仓摘要发现

- 已新增 Dashboard 区块“本轮风险归因与调仓摘要”，位置在资产池策略说明之后、风险图表之前，先给使用者 3 个短结论：主要风险、压力情境、调仓原因。
- 摘要复用既有变量：`top_shrink_risk_index`、`shrink_rc`、`max_pair_text`、`sample_stress`、`shrink_stress`、`actionable_signals`、`settled_signal_count`，不新增模型、不改变策略或交易规则。
- 主要风险文案明确：最大风险贡献标的和最高相关资产对用于识别同源风险，不代表个股买卖建议。
- 压力情境文案改为正数损失口径：普通协方差估计损失约 19.62%，收缩协方差估计损失约 19.56%；明确不是未来预测。
- 调仓原因文案支持三种状态：有待确认单、已有本日落账转观察、完全无新触发。
- 持仓区新增“持仓状态解释”，说明当前市值/未实现盈亏来自本地模拟持仓和市值档，不是券商账户资料；持仓表和建议单不是同一件事。
- 正式 `dashboard/index.html` 已重建，新文案可检索；未使用 Shioaji、`--update-daily-market` 或 `--execute-simulated-trades`，正式模拟成交/持仓 CSV 未改。

## 2026-06-14 第七轮模拟盘稳定 trade_id 发现

- 模拟盘建议单新增稳定 `trade_id`，格式为 `paper-YYYYMMDD-symbol-action-01-digest`；digest 来自 `paper-v1`、交易日、建仓日、模型方法、标的、方向、稳定 `trigger_code` 与默认批次 `01`。
- `trade_id` 不包含 `latest_price`、`proposed_shares` 或中文 `reason`，避免行情、持仓数量或说明文案微调导致同一建议换 ID。
- 已把四类触发分支转成稳定 `trigger_code`：`market_loss_stop_25`、`cost_or_trend_stop_25`、`profit_take_hot_20`、`pullback_add_15`。
- `load_simulated_trade_keys()` 现在读取新 CSV 的 `trade_id`，同时保留 `legacy:{trade_date}:{symbol}:{action}`，旧模拟成交 CSV 没有 `trade_id` 时仍能阻止同日重复落账。
- `write_simulated_trades()` 写入新成交时会新增 `trade_id` 欄位；既有旧行若无该列，会在重写时补空值，不影响旧 CSV 读取。
- Dashboard 的“模拟盘调仓确认”待确认行新增 `data-trade-id`，页面状态 localStorage key 升级为 `risk-dashboard-manual-trades-v2-...`，状态对象按 `trade_id` 记录；`data-symbol` 仅保留作人工检查辅助。
- 临时预览 Dashboard 可看到 `单号：paper-20260608-2317-sell-01-c5ac2f144a` 与 `paper-20260608-1301-sell-01-61defce39b`；正式 Dashboard 因本日正式模拟成交已落账，当前没有待确认行，但脚本结构已升级为 v2。
- 本轮没有改变“同日同标的同方向只落账一次”的模拟盘语义；若未来要真正支持同日分批，需要另一定义 `batch_seq` 何时从 `01` 递增到 `02`。

## 2026-06-14 第八轮显式分批 batch_seq 发现

- 不采用自动递增 `batch_seq`：自动找下一批会破坏幂等性，最坏情况是同一命令重复执行不断新增 `02/03/04`。
- 新增 CLI 参数 `--simulated-trade-batch-seq`，校验规则为 `01` 到 `99`；允许输入 `1` 自动补成 `01`，拒绝 `00`、非数字与超过两位。
- 默认批次为 `01`，继续保留旧无 `trade_id` CSV 的 legacy `(trade_date, symbol, action)` 防重，避免旧资料无法识别批次时重复落账。
- 新格式 CSV 若已有 `trade_id`，不再把 legacy key 作为全局阻挡；显式 `02` 可与 `01` 同日同标的同方向共存，但第二次同样 `02` 会被相同 `trade_id` 阻挡。
- `load_simulated_trade_keys()` 已拆成 `trade_ids` 与 `legacy_keys` 两组：有 `trade_id` 的新行走精准 ID 幂等；没有 `trade_id` 的旧行才进入 legacy 保护。
- Dashboard footer 与 README 已说明：默认批次 `01` 保持幂等，只有明确使用新的模拟成交批次号才视为同日分批；分批是人为确认的第二/第三批，不是绕过重复落账保护。
- `/tmp` 验证结果：`01` 第一次生成 2 笔、第二次仍 2 笔；显式 `02` 后共 4 笔，其中 `-01-` 两笔、`-02-` 两笔；第二次同样 `02` 复跑仍 4 笔，`duplicate_trade_ids=0`。
- 正式 `dashboard/index.html` 已重建并包含默认批次说明；正式模拟成交/持仓 CSV hash 未变化。

## 2026-06-14 第九轮行业/AI 供应链风险归因发现

- 已新增解释型群组归因，不改变模型权重、回测、策略阈值、建议单或模拟盘落账逻辑。
- 归因口径：若有模型盘，使用模型盘目标权重作为群组暴露，并用收缩协方差计算风险贡献；没有模型盘时退回收缩协方差最小方差权重。
- Dashboard 新增“行业、主题与 AI 供应链风险归因”区块，位置在“本轮风险归因与调仓摘要”之后、风险图表之前。
- 新区块包含行业 Top 5、主题 Top 5 和 AI/非 AI 二元分组，展示檔数、权重、风险贡献和“风险-权重”差值。
- 正式口径下，AI 供应链直接标记标的共 5 檔，模型盘目标权重 33.00%，风险贡献 48.49%，风险贡献相对权重差 +15.49%。
- 已明确边界：群组归因只用于解释同源风险与组合暴露，不代表个股买卖建议，也不是未来报酬预测；AI 供应链只按标的本身分类，不穿透 ETF 成分。
- 正式 `dashboard/index.html` 已重建并命中新文案；模型盘 CSV 内容 hash 不变，正式模拟成交/持仓 CSV 未改。

## 2026-06-15 第十轮 Dashboard 批次状态小结发现

- 批次状态小结应是解释层，不应改变 `trade_id`、`batch_seq`、建议单触发或模拟落账语义。
- 已新增只读批次汇总：从本地模拟成交 CSV 的 `trade_id` 解析批次；没有 `trade_id` 的旧记录单独归为“舊格式”，不硬判为 `01`。
- Dashboard “模拟盘调仓确认”区块现在显示“模擬盤批次狀態小結”，包含目前批次、已写入本地模拟成交 CSV 的批次、旧格式记录与目前待确认。
- 正式 2026-06-08 模拟成交 CSV 仍是旧格式，Dashboard 显示“舊格式 2 筆”，标的为 `1301、2317`，方向为 `sell`。
- `/tmp` 临时验证确认：批次 `01` 两次保持 2 笔；显式 `02` 后共 4 笔；第二次同样 `02` 仍 4 笔，`duplicate_trade_ids=0`。
- 正式 `dashboard/index.html` 已重建；`data/model_portfolio_latest.csv` 内容 hash 不变，正式模拟成交/持仓 CSV hash 不变。
- 页面文案强调：页面确认只保存在当前浏览器，真正写入本地模拟成交 CSV 仍需执行 Python 主脚本；不代表券商成交或委托状态。

## 2026-06-15 第十一轮群组风险研究报告摘要发现

- 研究报告摘要应复用既有群组归因、相关性、压力情境和模拟盘状态，不新增模型信号、不改变权重、不改变建议单触发或模拟落账。
- Dashboard “本轮风险归因与调仓摘要”区块新增只读 `textarea`，标题为“群组风险研究报告摘要”，方便复制到报告或 Obsidian。
- 正式摘要显示：AI 供应链权重 `33.00%`、风险贡献 `48.49%`、风险-权重差 `+15.49%`，与第九轮群组归因表一致。
- 摘要边界已明确：仅用于本地模拟盘研究记录，不代表未来报酬预测、个股买卖建议、实盘订单或券商账户状态；不会新增交易信号，不会写入模拟成交 CSV，也不连接券商。
- 正式 `dashboard/index.html` 已重建；`data/model_portfolio_latest.csv` 与 `data/model_portfolio_2026-06-03.csv` 内容 hash 不变，正式模拟成交/持仓 CSV hash 不变。
- README 已补充：研究摘要复用当前权重、收缩协方差风险贡献、行业/主题/AI 供应链归因、相关性、压力情境和本地模拟盘状态。

## 2026-06-15 第十二轮旧格式 fixture 验证发现

- 新增 `scripts/validate_legacy_trade_batch_status.py`，用 `/tmp/tw_quant_legacy_trade_fixture.csv` 生成无 `trade_id` 的旧格式模拟成交 fixture，不读取或覆盖正式 `data/simulated_*`。
- 默认脚本验证 `load_simulated_trade_batch_status()`：两笔旧成交归为 `batch_seq == "legacy"`、`label == "舊格式"`、`trade_count == 2`、标的为 `1301、2317`、方向为 `sell`。
- fixture 第二笔 `status` 使用 `" executed "`，覆盖 `strip().lower()` 标准化兼容。
- 带 `--dashboard` 时会临时重建 `/tmp/tw_quant_legacy_trade_fixture_dashboard.html`，断言页面显示“暫無新格式批次”“舊格式紀錄：舊格式 2 筆”“舊成交 CSV 無 trade_id”，且不出现 `<td>批次 01</td><td>2</td>`。
- `--simulated-trades-output` 的 help 已调整为“模拟成交 CSV 路径；落账时写入，Dashboard 验证时可读取指定路径”，与当前渲染验证用途一致。
- 本轮未重建正式 Dashboard；正式 Dashboard、模型盘 CSV、正式模拟成交/持仓 CSV hash 均保持第十一轮结果不变。

## 2026-06-15 第十三轮 Obsidian 研究记录同步发现

- iCloud Obsidian 正确落点已验证为 `/Users/tonyfu/Library/Mobile Documents/iCloud~md~obsidian/Documents/AI-Knowledge-Wiki/02-The-Wiki/05-商业金融与量化交易/01-量化交易/03-策略实践/台股量化基金.md`；本机 `/Users/tonyfu/Documents/Obsidian` 与历史噪音路径未找到同名项目卡片。
- `00-索引-MOC.md` 已包含 `[[03-策略实践/台股量化基金|台股量化基金]]`，本轮无需修改索引。
- 已把 Dashboard 群组风险研究报告摘要同步到项目卡片，包含最大风险贡献、最高相关资产对、AI 供应链权重 33.00%、风险贡献 48.49%、风险-权重差 +15.49%、压力情境与模拟盘状态。
- Obsidian 卡片已同步第九至第十二轮稳定结论：群组风险归因不穿透 ETF 成分、旧格式模拟成交显示“舊格式 2 筆”、fixture 验证只写 `/tmp`。
- 本轮只改研究记录与交接文档，不改源码、不重建 Dashboard、不覆盖正式模型盘或模拟盘 CSV。

## 2026-06-15 第十四轮研究摘要同步检查发现

- 新增 `scripts/validate_research_brief_sync.py`，默认只读取正式 `dashboard/index.html` 与 iCloud Obsidian `台股量化基金.md`，不重建 Dashboard、不写入 `data/`、不触碰 Shioaji。
- 脚本会从 Dashboard 的 `research-report` 只读 textarea 抽取研究摘要，逐行确认这些摘要已存在于 Obsidian 项目卡片。
- 脚本额外检查关键边界与数字：AI 供应链权重 33.00%、风险贡献 48.49%、风险-权重差 +15.49%、旧格式模拟成交“舊格式 2 筆”、不代表未来报酬预测或券商账户状态。
- 本轮把 Dashboard -> Obsidian 的人工同步结果升级为可复跑 QA 闸门；正式 Dashboard、模型盘 CSV、模拟成交与持仓 CSV 均未改。

## 2026-06-15 第十五轮 Markdown 摘要预览导出发现

- 新增 `scripts/export_research_brief_markdown.py`，复用 `validate_research_brief_sync.extract_research_brief()` 从正式 `dashboard/index.html` 抽取 `research-report` 摘要，避免重复维护两套解析逻辑。
- 默认输出 `/tmp/tw_quant_research_brief.md`，只作为 Markdown 预览；不写入 Obsidian，不重建 Dashboard，不覆盖正式 `data/`。
- 导出内容包含来源 Dashboard、用途、研究边界和 Obsidian callout 形式的摘要，保留“不代表未来报酬预测、个股买卖建议、实盘订单或券商账户状态”的边界。
- 本轮把“复制摘要”从手动页面操作扩展为可复跑临时产物，但仍保持本地模拟盘与解释型研究边界。

## 2026-06-15 第十六轮本地 QA 汇总发现

- 新增 `scripts/run_local_qa_checks.py`，把 `validate_research_brief_sync.py`、`export_research_brief_markdown.py` 与 `validate_legacy_trade_batch_status.py` 串成一条顺序执行的本地 QA 汇总命令。
- 汇总脚本会在执行前后分别计算正式 `dashboard/index.html`、模型盘 CSV、模拟成交/持仓 CSV 与市值档的 SHA-256，确保本地 QA 检查没有改动正式产物。
- 脚本默认只生成 `/tmp/tw_quant_local_qa_research_brief.md` 与旧格式 fixture CSV；在第十六轮时，若显式启用当时的可选 Dashboard fixture 参数，才会额外跑旧格式 fixture 的临时 Dashboard 页面验证。

## 2026-06-16 第十八轮 QA 文案漂移清理发现

- 已把本地 QA 汇总相关交接文档中的旧参数名统一更新为当前口径：默认包含旧格式 fixture 的临时 Dashboard 页面验证，较快模式使用 `--skip-dashboard-fixture`。
- 本轮只清理脚本说明与交接文案，不改变 `scripts/run_local_qa_checks.py` 的当前行为，不改正式 Dashboard，不改模型盘或模拟盘 CSV。
- 本轮把第十二至第十五轮分散的验证脚本变成单一入口，降低续跑成本，同时继续守住“只读行情、本地模拟盘、正式产物不改”的边界。

## 2026-06-16 第十七轮固定 Dashboard Fixture 回归发现

- `scripts/run_local_qa_checks.py` 现已把旧格式 fixture 的临时 Dashboard 页面验证纳入默认回归，避免每次手动记得加参数才覆盖该分支。
- 为了保留较快检查路径，新增 `--skip-dashboard-fixture`，在需要快速本地检查时可跳过临时 HTML 生成，但默认仍走覆盖面更完整的回归。
- 本轮只调整 QA 汇总脚本与说明文档，不改研究摘要内容、不改正式 Dashboard、不改模型盘或模拟盘 CSV。

## 2026-06-16 第十九轮 QA 摘要文件输出发现

- 本地 QA 汇总原先只有终端单行 `local_qa_checks_ok`，续跑时若没保留终端上下文，不够适合交接与复核。
- 新增 `--summary-output`，默认把摘要写到 `/tmp/tw_quant_local_qa_summary.md`；内容包含执行时间、检查模式、Markdown 预览路径、三段检查结果和正式产物 SHA-256。
- 摘要文件只写 `/tmp`，不改正式 Dashboard、不改模型盘或模拟盘 CSV，也不改变默认/较快模式的 QA 行为。

## 2026-06-16 第二十轮 QA JSON 摘要输出发现

- 第十九轮的 Markdown 摘要更适合人看，但若要给后续 agent、脚本或自动巡检复用，仍缺一个稳定的机器可读载体。
- 新增 `--summary-json-output`，默认写 `/tmp/tw_quant_local_qa_summary.json`；内容包含时间、模式、`dashboard_fixture` 开关、Markdown/Markdown 摘要路径、三段检查结果与正式产物 hash。
- JSON 摘要和 Markdown 摘要一样只写 `/tmp`，不改正式 Dashboard、不改模型盘或模拟盘 CSV，也不改变既有 QA 检查顺序。

## 2026-06-16 第二十一轮关键数字回归检查发现

- 现有 QA 已能检查摘要存在、同步一致、可导出，但还没有把最关键的稳定数字做成显式断言。
- 新增 `scripts/validate_research_brief_metrics.py`，直接从正式 Dashboard 的 `research-report` 摘要解析并校验 4 个关键值：`AI 供应链权重 33.00%`、`风险贡献 48.49%`、`风险-权重差 +15.49%`、`已有 2 笔本日模拟调仓转为观察`。
- 该脚本只读正式 Dashboard，不重建页面、不改正式 CSV；接入 `scripts/run_local_qa_checks.py` 后，关键数字回归会成为本地 QA 汇总的默认闸门。

## 2026-06-16 第二十二轮公网部署与每日重建发现

- `src/risk_dashboard.py` 现在支持 `--market-source public-close`，会用公开收盘价重建每日市值檔，并优先读取最新已生成的 `model_portfolio_market_*.csv`，避免继续固定落到旧市值档。
- `scripts/serve_dashboard.py` 已改成“先提供首页、后台按时重建”的 Web 服务：启动时会先跑一次重建命令，之后按固定时刻继续重建。
- Render 蓝图已同步默认环境：`Asia/Shanghai`、每日 `18:30`、公开收盘重建命令，适合直接把生成后的 Dashboard 挂到公网。
- 本轮已验证：`py_compile` 通过；`scripts/run_local_qa_checks.py --skip-dashboard-fixture` 通过；`--market-source public-close` 的临时 Dashboard 成功生成；`/healthz` 与 `/` 端点正常返回。
- 本轮临时验证时写出的 `data/model_portfolio_market_2024-06-28.csv` 已清理，避免污染后续“最新市值档”选择。

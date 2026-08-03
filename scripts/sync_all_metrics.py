from __future__ import annotations

import html as html_lib
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard" / "index.html"
OBSIDIAN_NOTE = Path(
    "/Users/tonyfu/Library/Mobile Documents/iCloud~md~obsidian/Documents/"
    "AI-Knowledge-Wiki/02-The-Wiki/05-商业金融与量化交易/01-量化交易/"
    "台股量化基金.md"
)
VALIDATE_METRICS = ROOT / "scripts" / "validate_research_brief_metrics.py"
VALIDATE_SYNC = ROOT / "scripts" / "validate_research_brief_sync.py"
RUN_QA = ROOT / "scripts" / "run_local_qa_checks.py"


def main() -> None:
    # 1. Parse research brief from dashboard/index.html
    if not DASHBOARD.exists():
        print(f"Error: {DASHBOARD} not found.")
        return

    html_text = DASHBOARD.read_text(encoding="utf-8")
    match = re.search(
        r'<textarea class="research-report"[^>]*>(.*?)</textarea>',
        html_text,
        flags=re.S,
    )
    if not match:
        print("Error: Could not find research brief in dashboard.")
        return

    brief = html_lib.unescape(match.group(1)).strip()
    brief_lines = [line.strip() for line in brief.splitlines() if line.strip()]
    print("Extracted brief lines:\n" + "\n".join(brief_lines))

    # Parse metrics
    ai_line = next((line for line in brief_lines if "AI 供应链权重" in line), "")
    trade_line = next((line for line in brief_lines if "调仓状态" in line), "")

    ai_weight = re.search(r"AI 供应链权重 ([0-9.]+%)", ai_line).group(1)
    risk_contrib = re.search(r"风险贡献 ([0-9.]+%)", ai_line).group(1)
    risk_gap = re.search(r"风险-权重差 ([+-][0-9.]+%)", ai_line).group(1)

    trade_match = re.search(
        r"(?:已有|本轮有) (\d+) 笔(?:本日模拟调仓转为观察|待确认调仓)|本轮(没有)新的待确认调仓",
        trade_line
    )
    if trade_match:
        val = trade_match.group(1) or trade_match.group(2)
        trade_count = "0" if val in (None, "没有") else val
    else:
        trade_count = "0"

    print(
        f"Parsed Metrics: AI Weight={ai_weight}, Risk Contrib={risk_contrib}, Gap={risk_gap}, Trades={trade_count}"
    )

    # 2. Update validate_research_brief_metrics.py EXPECTED_METRICS
    metrics_py = VALIDATE_METRICS.read_text(encoding="utf-8")
    metrics_py = re.sub(
        r'"ai_weight_percent": "[^"]+"',
        f'"ai_weight_percent": "{ai_weight}"',
        metrics_py,
    )
    metrics_py = re.sub(
        r'"risk_contribution_percent": "[^"]+"',
        f'"risk_contribution_percent": "{risk_contrib}"',
        metrics_py,
    )
    metrics_py = re.sub(
        r'"risk_weight_gap_percent": "[^"]+"',
        f'"risk_weight_gap_percent": "{risk_gap}"',
        metrics_py,
    )
    metrics_py = re.sub(r'"trade_count": "[^"]+"', f'"trade_count": "{trade_count}"', metrics_py)
    VALIDATE_METRICS.write_text(metrics_py, encoding="utf-8")
    print("Updated validate_research_brief_metrics.py")

    # 3. Update run_local_qa_checks.py check lines
    qa_py = RUN_QA.read_text(encoding="utf-8")
    qa_py = re.sub(r'"AI 供应链权重 [^"]+"', f'"AI 供应链权重 {ai_weight}"', qa_py)
    qa_py = re.sub(r'"风险贡献 [^"]+"', f'"风险贡献 {risk_contrib}"', qa_py)
    qa_py = re.sub(r'"风险-权重差 [^"]+"', f'"风险-权重差 {risk_gap}"', qa_py)
    RUN_QA.write_text(qa_py, encoding="utf-8")
    print("Updated run_local_qa_checks.py")

    # 4. Update validate_research_brief_sync.py required_fragments
    sync_py = VALIDATE_SYNC.read_text(encoding="utf-8")
    sync_py = re.sub(r'"AI 供应链权重 [^"]+"', f'"AI 供应链权重 {ai_weight}"', sync_py)
    sync_py = re.sub(r'"风险贡献 [^"]+"', f'"风险贡献 {risk_contrib}"', sync_py)
    sync_py = re.sub(r'"风险-权重差 [^"]+"', f'"风险-权重差 {risk_gap}"', sync_py)
    VALIDATE_SYNC.write_text(sync_py, encoding="utf-8")
    print("Updated validate_research_brief_sync.py")

    # 5. Update Obsidian Note
    if OBSIDIAN_NOTE.exists():
        note_text = OBSIDIAN_NOTE.read_text(encoding="utf-8")
        
        # 匹配 KPI
        kpis = []
        kpi_matches = re.finditer(
            r'<div class="kpi-report-card">.*?<span class="lbl">(.*?)</span>.*?<span class="val [^>]*>(.*?)</span>.*?<span class="sub">(.*?)</span>',
            html_text,
            flags=re.S
        )
        for m in kpi_matches:
            lbl = m.group(1).strip()
            val = re.sub(r'<[^>]+>', '', m.group(2)).strip()
            sub = re.sub(r'<[^>]+>', '', m.group(3)).strip()
            kpis.append(f"| {lbl} | **{val}** | {sub} |")
        kpi_table_md = "\n".join(kpis)

        # 匹配红榜
        winners_section = re.search(r'今日標的表現紅榜 \(Winners\)(.*?)</div>\s*</div>', html_text, flags=re.S)
        winners_list = []
        if winners_section:
            w_items = re.finditer(r'<div class="ranking-item">.*?<span class="ranking-symbol"><b>(.*?)</b>\s*(.*?)</span>.*?<span class="ranking-value positive-text">(.*?)</span>', winners_section.group(1), flags=re.S)
            for m in w_items:
                winners_list.append(f"- 🔴 **{m.group(1)}** {m.group(2)} (`{m.group(3)}`)")
        winners_md = "\n".join(winners_list) if winners_list else "- (無)"

        # 匹配黑榜
        losers_section = re.search(r'今日標的表現黑榜 \(Losers\)(.*?)</div>\s*</div>', html_text, flags=re.S)
        losers_list = []
        if losers_section:
            l_items = re.finditer(r'<div class="ranking-item">.*?<span class="ranking-symbol"><b>(.*?)</b>\s*(.*?)</span>.*?<span class="ranking-value negative-text">(.*?)</span>', losers_section.group(1), flags=re.S)
            for m in l_items:
                losers_list.append(f"- 🟢 **{m.group(1)}** {m.group(2)} (`{m.group(3)}`)")
        losers_md = "\n".join(losers_list) if losers_list else "- (無)"

        # 匹配交易明细
        trade_tbody_match = re.search(r'<table class="dashboard-table trade-details-table">.*?<tbody>(.*?)</tbody>', html_text, flags=re.S)
        trade_rows = []
        if trade_tbody_match:
            tr_matches = re.finditer(
                r'<tr>\s*<td>(.*?)</td>\s*<td><b>(.*?)</b>\s*<span class="asset-name-small">(.*?)</span></td>\s*<td><span class="action-badge [^>]*>(.*?)</span></td>\s*<td class="num-col">(.*?)</td>\s*<td class="num-col">(.*?)</td>\s*<td class="num-col font-mono">(.*?)</td>\s*</tr>',
                trade_tbody_match.group(1),
                flags=re.S
            )
            for m in tr_matches:
                trade_rows.append(f"| {m.group(1)} | {m.group(2)} {m.group(3)} | {m.group(4)} | {m.group(5)} | {m.group(6)} | {m.group(7)} |")
        
        trade_table_md = ""
        if trade_rows:
            trade_table_md = "\n".join([
                "| 交易日期 | 標的 | 方向 | 成交股數 | 成交均價 | 交易總金額 |",
                "| --- | --- | --- | ---: | ---: | ---: |",
                *trade_rows
            ])
        else:
            trade_table_md = "*今日無模擬調倉交易。*"

        # 拼接 Obsidian 版面
        structure_block = f"""

### 📊 核心量化 KPI 儀表盤
| 指標 | 數值 | 說明 |
| --- | ---: | --- |
{kpi_table_md}

### 📈 本日標的表現 (紅黑榜)
- **漲幅前三名 (Winners)**：
{winners_md}
- **跌幅前三名 (Losers)**：
{losers_md}

### 📝 今日模擬調倉交易明細
{trade_table_md}
"""

        pattern = r"(## 七、最新研究摘要.*?）\n\n> \[\!note\] Dashboard 研究摘要\n)(.*?)(## 八、)"

        brief_block = "\n".join(f"> {line}" for line in brief_lines) + "\n\n" + structure_block
        today_str = datetime.now().strftime("%Y-%m-%d")
        new_header = f"## 七、最新研究摘要（{today_str} 收盘定稿）\n\n> [!note] Dashboard 研究摘要\n"

        def repl(m: re.Match) -> str:
            return new_header + brief_block + m.group(3)

        new_note_text, count = re.subn(pattern, repl, note_text, flags=re.S)
        if count > 0:
            OBSIDIAN_NOTE.write_text(new_note_text, encoding="utf-8")
            print("Successfully updated Obsidian Note research brief!")
        else:
            print("Error: Could not locate the research brief section in Obsidian note.")
    else:
        print(f"Warning: Obsidian note {OBSIDIAN_NOTE} not found. Skipping Obsidian update.")


if __name__ == "__main__":
    main()

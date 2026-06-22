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
    "03-策略实践/台股量化基金.md"
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

    trade_match = re.search(r"(?:已有|本轮有|本轮有新的) (\d+) 笔", trade_line)
    trade_count = trade_match.group(1) if trade_match else "0"

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
        pattern = r"(## 七、最新研究摘要.*?）\n\n> \[\!note\] Dashboard 研究摘要\n)(.*?)(## 八、)"

        brief_block = "\n".join(f"> {line}" for line in brief_lines) + "\n\n"
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

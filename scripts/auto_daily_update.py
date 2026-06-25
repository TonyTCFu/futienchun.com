#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台股量化自动化每日更新汇总脚本：
顺序执行：
1. shioaji_sync_recent.py (同步收盘数据)
2. risk_dashboard.py (重建 Dashboard)
3. sync_all_metrics.py (同步指标与 Obsidian 笔记)
4. publish_dashboard.py (QA测试与网页/代码推送)
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "bin" / "python"
LOG_FILE = ROOT / "data" / "auto_daily_update.log"

def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as exc:
        print(f"写入日志文件失败: {exc}")

def run_script(script_name: str, args: list[str] = []) -> bool:
    script_path = ROOT / script_name
    cmd = [str(PYTHON), str(script_path)] + args
    log(f"开始执行: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        log(f"错误: {script_name} 执行失败，退出码 {res.returncode}")
        if res.stdout:
            log(f"标准输出:\n{res.stdout}")
        if res.stderr:
            log(f"标准错误:\n{res.stderr}")
        return False
    log(f"成功: {script_name} 执行完毕。")
    if res.stdout:
        lines = res.stdout.strip().splitlines()
        tail = lines[-3:] if len(lines) >= 3 else lines
        log(f"输出片段: {' | '.join(tail)}")
    return True

def main():
    log("=== 启动每日自动化更新 ===")
    
    # 1. 同步数据 (Shioaji)
    if not run_script("scripts/shioaji_sync_recent.py"):
        sys.exit(1)
        
    # 2. 重建风险仪表盘与落账模拟盘
    rebuild_args = [
        "src/risk_dashboard.py",
        "--start", "2024-01",
        "--end", "2026-06",
        "--offline-cache",
        "--model-portfolio",
        "--model-method", "multi-factor-shrink",
        "--ai-tilt", "moderate",
        "--market-source", "public-close",
        "--market-mode", "close",
        "--execute-simulated-trades"
    ]
    log(f"开始执行重建命令: {PYTHON} {' '.join(rebuild_args)}")
    res = subprocess.run([str(PYTHON)] + rebuild_args, cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        log(f"错误: risk_dashboard.py 执行失败，退出码 {res.returncode}")
        if res.stdout:
            log(f"标准输出:\n{res.stdout}")
        if res.stderr:
            log(f"标准错误:\n{res.stderr}")
        sys.exit(1)
    log("成功: risk_dashboard.py 重建完毕。")
    
    # 3. 同步测试指标与 Obsidian
    if not run_script("scripts/sync_all_metrics.py"):
        sys.exit(1)
        
    # 4. QA 与一键推送部署
    if not run_script("scripts/publish_dashboard.py"):
        sys.exit(1)
        
    log("=== 每日自动化更新与部署全部成功完成 ===")

if __name__ == "__main__":
    main()

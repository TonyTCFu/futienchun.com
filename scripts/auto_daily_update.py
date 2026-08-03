#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台股量化自动化每日更新汇总脚本：
顺序执行：
1. shioaji_sync_recent.py (同步收盘数据，带重试)
2. risk_dashboard.py (重建 Dashboard，带重试)
3. sync_all_metrics.py (同步指标与 Obsidian 笔记)
4. publish_dashboard.py (QA测试与网页/代码推送，带重试)
"""

import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "bin" / "python"
LOG_FILE = ROOT / "data" / "auto_daily_update.log"
SUCCESS_MARK_FILE = ROOT / "data" / ".last_success_date"

def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as exc:
        print(f"写入日志文件失败: {exc}")

def run_script(script_name: str, args: list[str] = [], max_retries: int = 1, delay: int = 30) -> bool:
    script_path = ROOT / script_name
    cmd = [str(PYTHON), str(script_path)] + args
    
    for attempt in range(1, max_retries + 1):
        log(f"开始执行 (第 {attempt}/{max_retries} 次尝试): {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if res.returncode == 0:
            log(f"成功: {script_name} 执行完毕。")
            if res.stdout:
                lines = res.stdout.strip().splitlines()
                tail = lines[-3:] if len(lines) >= 3 else lines
                log(f"输出片段: {' | '.join(tail)}")
            return True
        
        log(f"警告: {script_name} 执行失败 (尝试 {attempt}/{max_retries})，退出码 {res.returncode}")
        if res.stdout:
            log(f"标准输出:\n{res.stdout}")
        if res.stderr:
            log(f"标准错误:\n{res.stderr}")
        
        if attempt < max_retries:
            log(f"将在 {delay} 秒后重试...")
            time.sleep(delay)
            
    return False

def main():
    log("=== 启动每日自动化更新 ===")
    
    # 0. 先从 GitHub 远端拉取最新代码，保障 Documents 工作区与 runner 空间的双向同步
    log("正在从 origin 远端拉取最新代码...")
    res_pull = subprocess.run(["git", "pull", "origin", "main"], cwd=ROOT, capture_output=True, text=True)
    if res_pull.returncode != 0:
        log(f"警告: git pull origin main 失败，退出码 {res_pull.returncode}，可能存在本地冲突或网络波动。")
        if res_pull.stderr:
            log(f"标准错误:\n{res_pull.stderr}")
    else:
        log("git pull origin main 成功，代码已同步为最新。")
        
    # 检查是否已完成今日的更新，避免重复执行
    today = date.today()
    weekday = today.weekday()
    last_success_str = ""
    if SUCCESS_MARK_FILE.exists():
        try:
            last_success_str = SUCCESS_MARK_FILE.read_text(encoding="utf-8").strip()
        except Exception as exc:
            log(f"读取最后成功标记文件失败: {exc}")
            
    if last_success_str:
        if weekday in (5, 6):  # 周末 (周六=5, 周日=6)
            days_to_friday = weekday - 4
            last_friday = today - timedelta(days=days_to_friday)
            if last_success_str in (today.isoformat(), (today - timedelta(days=1)).isoformat(), last_friday.isoformat()):
                log(f"今日为周末且数据已是最新 (最后成功日期: {last_success_str})，跳过执行。")
                sys.exit(0)
        else:  # 工作日
            now_time = datetime.now().time()
            if now_time < datetime.strptime("13:45", "%H:%M").time():
                yesterday = today - timedelta(days=1)
                allowed_past_success = [today.isoformat(), yesterday.isoformat()]
                if weekday == 0:  # 周一
                    allowed_past_success.extend([
                        (today - timedelta(days=2)).isoformat(),
                        (today - timedelta(days=3)).isoformat(),
                    ])
                if last_success_str in allowed_past_success:
                    log(f"当前时间早于 13:45 且数据已就绪 (最后成功日期: {last_success_str})，跳过执行。")
                    sys.exit(0)
            else:
                if last_success_str == today.isoformat():
                    log(f"今日已于 {last_success_str} 成功更新完毕，无需重复执行。")
                    sys.exit(0)
    
    # 1. 同步数据 (Shioaji，设置 3 次网络重试)
    if not run_script("scripts/shioaji_sync_recent.py", max_retries=3, delay=30):
        sys.exit(1)
        
    # 2. 重建风险仪表盘与落账模拟盘
    rebuild_args = [
        "src/risk_dashboard.py",
        "--start", "2024-01",
        "--end", datetime.now().strftime("%Y-%m"),
        "--offline-cache",
        "--model-portfolio",
        "--model-method", "multi-factor-shrink",
        "--ai-tilt", "moderate",
        "--market-source", "public-close",
        "--market-mode", "close",
        "--execute-simulated-trades"
    ]
    log(f"开始执行重建命令: {PYTHON} {' '.join(rebuild_args)}")
    
    rebuild_success = False
    for attempt in range(1, 3):
        log(f"重建尝试 (第 {attempt}/2 次)...")
        res = subprocess.run([str(PYTHON)] + rebuild_args, cwd=ROOT, capture_output=True, text=True)
        if res.returncode == 0:
            rebuild_success = True
            log("成功: risk_dashboard.py 重建完毕。")
            break
        log(f"警告: risk_dashboard.py 重建失败，退出码 {res.returncode}")
        if res.stdout:
            log(f"标准输出:\n{res.stdout}")
        if res.stderr:
            log(f"标准错误:\n{res.stderr}")
        if attempt < 2:
            log("将在 10 秒后重试重建...")
            time.sleep(10)
            
    if not rebuild_success:
        sys.exit(1)
        
    # 3. 同步测试指标与 Obsidian
    if not run_script("scripts/sync_all_metrics.py"):
        sys.exit(1)
        
    # 4. QA 与一键推送部署 (网络依赖，设置 3 次重试)
    if not run_script("scripts/publish_dashboard.py", max_retries=3, delay=30):
        sys.exit(1)
        
    # 写入成功标记
    try:
        SUCCESS_MARK_FILE.write_text(today.isoformat(), encoding="utf-8")
        log(f"已写入成功标记: {today.isoformat()}")
    except Exception as exc:
        log(f"写入成功标记文件失败: {exc}")
        
    log("=== 每日自动化更新与部署全部成功完成 ===")

if __name__ == "__main__":
    main()

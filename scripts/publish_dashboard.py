#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动发布脚本：
1. 运行本地 QA 检查，确保所有数据、指标、Obsidian 卡片与 Dashboard 一致。
2. 拷贝最新的 dashboard/index.html 到个人静态网站工作目录。
3. 将静态网页推送到 Cloudflare Pages 关联的 GitHub 仓库。
4. 将策略主仓库中的最新改动也推送到 GitHub 托管仓。
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 项目主目录
ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "bin" / "python"
QA_CHECK_SCRIPT = ROOT / "scripts" / "run_local_qa_checks.py"
MAIN_DASHBOARD = ROOT / "dashboard" / "index.html"

# 静态网站本地仓库目录
WEBSITE_DIR = Path("/Users/tonyfu/.gemini/antigravity/scratch/portfolio-website")
WEBSITE_DASHBOARD = WEBSITE_DIR / "dashboard" / "index.html"


def run_command(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    print(f"正在执行命令: {' '.join(args)} 在目录: {cwd}")
    result = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"命令执行失败，错误码 {result.returncode}。")
        if result.stdout:
            print(f"标准输出:\n{result.stdout}")
        if result.stderr:
            print(f"标准错误:\n{result.stderr}")
    return result


def main() -> None:
    print("=== 开始发布流程 ===")

    # 1. 运行本地 QA 检查
    print("\n[步骤 1] 运行本地 QA 检查...")
    if not QA_CHECK_SCRIPT.exists():
        print(f"错误: 找不到 QA 检查脚本: {QA_CHECK_SCRIPT}")
        sys.exit(1)

    qa_res = run_command([str(PYTHON), str(QA_CHECK_SCRIPT)], ROOT)
    if qa_res.returncode != 0:
        print("错误: 本地 QA 检查失败，中止发布！")
        sys.exit(1)
    print("本地 QA 检查通过。")

    # 2. 复制 Dashboard 文件
    print("\n[步骤 2] 同步网页文件到个人网站本地仓库...")
    if not WEBSITE_DIR.exists():
        print(f"错误: 找不到个人静态网站本地目录: {WEBSITE_DIR}")
        sys.exit(1)

    if not MAIN_DASHBOARD.exists():
        print(f"错误: 本地尚未生成 Dashboard: {MAIN_DASHBOARD}")
        sys.exit(1)

    WEBSITE_DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(MAIN_DASHBOARD, WEBSITE_DASHBOARD)
        print(f"已成功拷贝 {MAIN_DASHBOARD.name} 到 {WEBSITE_DASHBOARD}")
    except Exception as exc:
        print(f"错误: 拷贝网页文件失败: {exc}")
        sys.exit(1)

    # 3. 提交并推送 Cloudflare Pages 静态网站仓库
    print("\n[步骤 3] 推送静态网页到 Cloudflare Pages 托管仓库...")
    # 检查是否有改动
    status_res = run_command(["git", "status", "--porcelain"], WEBSITE_DIR)
    if not status_res.stdout.strip():
        print("Cloudflare Pages 静态网站无任何文件改动，跳过推送。")
    else:
        # 添加并提交
        run_command(["git", "add", "dashboard/index.html"], WEBSITE_DIR)
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"deploy: sync dashboard updates on {today_str}"
        run_command(["git", "commit", "-m", commit_msg], WEBSITE_DIR)
        # 推送
        push_res = run_command(["git", "push", "origin", "main"], WEBSITE_DIR)
        if push_res.returncode != 0:
            print("警告: 静态网页推送失败！")
        else:
            print("静态网页推送成功，Cloudflare Pages 会自动触发构建部署。")

    # 4. 提交并推送主代码仓库
    print("\n[步骤 4] 推送改动到台股量化主代码仓库...")
    status_res = run_command(["git", "status", "--porcelain"], ROOT)
    if not status_res.stdout.strip():
        print("主代码仓库无任何文件改动，跳过推送。")
    else:
        # 添加所有变更（排除已忽略的）
        run_command(["git", "add", "."], ROOT)
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"feat: sync data and dashboard updates on {today_str}"
        run_command(["git", "commit", "-m", commit_msg], ROOT)
        # 推送
        push_res = run_command(["git", "push", "origin", "main"], ROOT)
        if push_res.returncode != 0:
            print("警告: 主仓库推送失败！")
        else:
            print("主仓库推送成功。")

    print("\n=== 发布流程执行完毕 ===")
    print("Cloudflare Pages 稳定公网地址: https://futienchun.com/dashboard/")


if __name__ == "__main__":
    main()

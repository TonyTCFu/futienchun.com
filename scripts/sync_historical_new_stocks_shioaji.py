#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 Shioaji 接口补齐新个股历史 K 线数据脚本：
拉取 2049, 3491, 2313 自 2024-01-01 至今的完整历史 K线 (分 25 天一段段拉取)，
并按年月拆分、去重合并到本地 cache json 中。
"""

import os
import csv
import json
import sys
import math
import numpy as np
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "cache"
DEFAULT_SHIOAJI_HOME = ROOT / ".shioaji.runtime"
NEW_STOCKS = ["2049", "3491", "2313"]

def shioaji_credentials() -> tuple[str, str]:
    env_file = ROOT / ".shioaji.local.env"
    if env_file.exists():
        text = env_file.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            parts = line.split("=", 1)
            if len(parts) == 2:
                key, val = parts[0].strip(), parts[1].strip().strip('"').strip("'")
                os.environ[key] = val

    api_key = os.environ.get("SHIOAJI_API_KEY", "").strip()
    secret_key = os.environ.get("SHIOAJI_SECRET_KEY", "").strip()
    if not api_key or not secret_key:
        raise RuntimeError("缺少 SHIOAJI_API_KEY 或 SHIOAJI_SECRET_KEY，请检查 .shioaji.local.env。")
    return api_key, secret_key

def main() -> None:
    print("=== 开始通过 Shioaji 补齐新股 2024-01 至今历史行情 ===")

    try:
        import shioaji as sj
    except ImportError as exc:
        print(f"错误: 找不到 shioaji 包，请使用虚拟环境安装: {exc}")
        sys.exit(1)

    try:
        api_key, secret_key = shioaji_credentials()
    except Exception as exc:
        print(f"错误: 获取凭证失败: {exc}")
        sys.exit(1)

    os.environ.setdefault("SJ_HOME_PATH", str(DEFAULT_SHIOAJI_HOME))
    DEFAULT_SHIOAJI_HOME.mkdir(parents=True, exist_ok=True)
    DEFAULT_SHIOAJI_HOME.chmod(0o700)

    api = sj.Shioaji()
    login_success = False
    for attempt in range(1, 4):
        try:
            print(f"正在登录永丰金 Shioaji API (第 {attempt}/3 次尝试)...")
            api.login(api_key=api_key, secret_key=secret_key)
            print("登录成功。")
            login_success = True
            break
        except Exception as exc:
            print(f"警告: 登录 Shioaji 失败: {exc}")
            if attempt < 3:
                print("将在 30 秒后重试登录...")
                time.sleep(30)

    if not login_success:
        print("错误: 登录 Shioaji 失败已达最大次数，程序退出。")
        sys.exit(1)

    # 计算 25 天的分段区间，严格避开 30 天限制
    start_dt = datetime.strptime("2024-01-01", "%Y-%m-%d")
    end_dt = datetime.today()
    
    intervals = []
    curr = start_dt
    while curr <= end_dt:
        nxt = min(curr + timedelta(days=24), end_dt)
        intervals.append((curr.strftime("%Y-%m-%d"), nxt.strftime("%Y-%m-%d")))
        curr = nxt + timedelta(days=1)

    print(f"共生成 {len(intervals)} 个分段区间。")

    for symbol in NEW_STOCKS:
        try:
            print(f"\n--- 正在分段拉取 {symbol} 历史 K 线 ---")
            contract = api.Contracts.Stocks[symbol]
            if not contract:
                print(f"错误: 找不到标的 {symbol} 的合约。")
                continue
            
            data_by_month = {}
            for start_str, end_str in intervals:
                # 提示进度，但不刷屏
                kbars = api.kbars(contract=contract, start=start_str, end=end_str)
                
                timestamps = list(getattr(kbars, "ts", []))
                opens = list(getattr(kbars, "Open", []))
                highs = list(getattr(kbars, "High", []))
                lows = list(getattr(kbars, "Low", []))
                closes = list(getattr(kbars, "Close", []))
                volumes = list(getattr(kbars, "Volume", []))
                amounts = list(getattr(kbars, "Amount", []))

                for offset, (ts_value, close) in enumerate(zip(timestamps, closes)):
                    timestamp = np.datetime64(ts_value, "ns")
                    day_str = str(timestamp.astype("datetime64[D]"))
                    dt = datetime.strptime(day_str, "%Y-%m-%d")
                    
                    roc_year = dt.year - 1911
                    roc_date = f"{roc_year}/{dt.month:02d}/{dt.day:02d}"
                    month_str = f"{dt.year}{dt.month:02d}"

                    close_val = float(close)
                    if math.isfinite(close_val):
                        open_val = str(opens[offset])
                        high_val = str(highs[offset])
                        low_val = str(lows[offset])
                        vol_val = str(int(volumes[offset]))
                        amt_val = str(int(amounts[offset]))

                        row = [
                            roc_date,
                            vol_val,
                            amt_val,
                            open_val,
                            high_val,
                            low_val,
                            str(close_val),
                            "0.00",
                            "0",
                            ""
                        ]
                        if month_str not in data_by_month:
                            data_by_month[month_str] = []
                        data_by_month[month_str].append(row)
                
                # 稍作停顿，避免请求过频
                time.sleep(0.5)

            if not data_by_month:
                print(f"警告: {symbol} 抓取到的 K 线数据为空。")
                continue

            # 写入各月的缓存 JSON
            for month_str, rows in data_by_month.items():
                cache_path = CACHE_DIR / f"{symbol}_{month_str}.json"
                
                cache_data = {
                    "stat": "OK",
                    "date": f"{month_str}01",
                    "title": f"民國年 {month_str[4:]}月 {symbol} 各日成交資訊",
                    "fields": ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌價差", "成交筆數", "註記"],
                    "data": []
                }

                if cache_path.exists():
                    try:
                        cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
                    except Exception as exc:
                        print(f"  读取旧缓存失败: {exc}，将覆盖重建。")

                existing_data = {r[0]: r for r in cache_data.get("data", [])}
                for r in rows:
                    existing_data[r[0]] = r  # 覆盖或者追加

                sorted_dates = sorted(existing_data.keys(), key=lambda d: [int(x) for x in d.split("/")])
                cache_data["data"] = [existing_data[d] for d in sorted_dates]

                cache_path.write_text(json.dumps(cache_data, ensure_ascii=False), encoding="utf-8")
            
            print(f"成功同步并保存 {symbol} 至今共 {len(data_by_month)} 个月的缓存文件。")
        except Exception as exc:
            print(f"处理标的 {symbol} 时发生异常: {exc}")

    print("\n=== 所有新股历史数据通过 Shioaji 同步完成 ===")

if __name__ == "__main__":
    main()

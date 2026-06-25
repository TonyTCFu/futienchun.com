#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shioaji 备用行情同步脚本：
使用永丰金 Shioaji 接口获取本月最新的日 K 线数据，
并写回本地月缓存 `data/cache/{symbol}_YYYYMM.json`。
这完全规避了 TWSE 的 429 限流问题。
"""

import csv
import json
import os
import sys
import math
import numpy as np
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_CSV = ROOT / "config" / "universe_tw.csv"
CACHE_DIR = ROOT / "data" / "cache"
DEFAULT_SHIOAJI_HOME = ROOT / ".shioaji.runtime"


def shioaji_credentials() -> tuple[str, str]:
    # 优先从本地已忽略的凭证文件中加载密钥
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
    print("=== Shioaji 行情同步补全启动 ===")

    # 1. 加载股票池
    if not UNIVERSE_CSV.exists():
        print(f"错误: 找不到股票池定义文件 {UNIVERSE_CSV}")
        sys.exit(1)

    symbols = []
    with open(UNIVERSE_CSV, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # 跳过 header
        for row in reader:
            if row:
                symbols.append(row[0].strip())

    print(f"股票池加载成功，共 {len(symbols)} 档标的: {', '.join(symbols)}")

    # 2. 登录 Shioaji
    os.environ.setdefault("SJ_HOME_PATH", str(DEFAULT_SHIOAJI_HOME))
    DEFAULT_SHIOAJI_HOME.mkdir(parents=True, exist_ok=True)
    DEFAULT_SHIOAJI_HOME.chmod(0o700)

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

    api = sj.Shioaji()
    try:
        print("正在登录永丰金 Shioaji API...")
        api.login(api_key=api_key, secret_key=secret_key)
        print("登录成功。")
    except Exception as exc:
        print(f"错误: 登录 Shioaji 失败: {exc}")
        sys.exit(1)

    # 3. 定位时间范围：抓取本月的日线 K 线
    today = datetime.today()
    start_date = f"{today.year}-{today.month:02d}-01"
    end_date = today.strftime("%Y-%m-%d")
    month_str = today.strftime("%Y%m")  # 格式如 "202606"

    # 4. 循环获取各档 K 线并更新缓存
    success_count = 0
    for symbol in symbols:
        try:
            print(f"正在查询 {symbol} ({start_date} 至 {end_date})...")
            contract = api.Contracts.Stocks[symbol]
            kbars = api.kbars(contract=contract, start=start_date, end=end_date)
            
            # 解析 kbars
            timestamps = list(getattr(kbars, "ts", []))
            opens = list(getattr(kbars, "Open", []))
            highs = list(getattr(kbars, "High", []))
            lows = list(getattr(kbars, "Low", []))
            closes = list(getattr(kbars, "Close", []))
            volumes = list(getattr(kbars, "Volume", []))
            amounts = list(getattr(kbars, "Amount", []))

            new_rows = []
            for offset, (ts_value, close) in enumerate(zip(timestamps, closes)):
                timestamp = np.datetime64(ts_value, "ns")
                day_str = str(timestamp.astype("datetime64[D]"))  # YYYY-MM-DD
                dt = datetime.strptime(day_str, "%Y-%m-%d")
                roc_year = dt.year - 1911
                roc_date = f"{roc_year}/{dt.month:02d}/{dt.day:02d}"

                close_val = float(close)
                if math.isfinite(close_val):
                    open_val = str(opens[offset])
                    high_val = str(highs[offset])
                    low_val = str(lows[offset])
                    vol_val = str(int(volumes[offset]))
                    amt_val = str(int(amounts[offset]))

                    # 拼成 TWSE 格式行: 
                    # ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌價差", "成交筆數", "註記"]
                    row = [
                        roc_date,
                        vol_val,
                        amt_val,
                        open_val,
                        high_val,
                        low_val,
                        str(close_val),
                        "0.00",  # 涨跌价差默认
                        "0",     # 成交笔数默认
                        ""       # 备注
                    ]
                    new_rows.append(row)

            if not new_rows:
                print(f"警告: {symbol} 抓取到的 K 线数据解析为空，跳过。")
                continue

            # 合并并写回本地 json 缓存
            cache_path = CACHE_DIR / f"{symbol}_{month_str}.json"
            cache_data = {
                "stat": "OK",
                "date": f"{month_str}01",
                "title": f"民國年 {today.month:02d}月 {symbol} 各日成交資訊",
                "fields": ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌價差", "成交筆數", "註記"],
                "data": []
            }
            if cache_path.exists():
                try:
                    cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
                except Exception as exc:
                    print(f"读取旧缓存失败: {exc}，将覆盖重建。")

            existing_data = {row[0]: row for row in cache_data.get("data", [])}
            for row in new_rows:
                existing_data[row[0]] = row  # 覆盖更新或追加

            # 按日期排序
            sorted_dates = sorted(existing_data.keys(), key=lambda d: [int(x) for x in d.split("/")])
            cache_data["data"] = [existing_data[d] for d in sorted_dates]

            # 写回文件
            cache_path.write_text(json.dumps(cache_data, ensure_ascii=False), encoding="utf-8")
            print(f"已成功更新缓存 {cache_path.name}，当前共有 {len(cache_data['data'])} 天数据。")
            success_count += 1
        except Exception as exc:
            print(f"处理标的 {symbol} 时发生异常: {exc}")

    print(f"\n=== 同步完成: 成功 {success_count}/{len(symbols)} 档标的 ===")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QVeris 备用行情同步脚本：
当 TWSE 网页爬虫因为限流（Connection Reset / HTTP 429）而无法获取最新行情时，
运行此脚本，利用 QVeris API 获取最新日线数据，并写回本地月缓存 `data/cache/{symbol}_YYYYMM.json`。
"""

import csv
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_CSV = ROOT / "config" / "universe_tw.csv"
CACHE_DIR = ROOT / "data" / "cache"


def run_qveris_call(symbol: str, start_date: str, end_date: str) -> str:
    # 转换标的格式，例如 "0050" -> "0050.TW"
    symbol_exchange = f"{symbol}.TW"
    params = {
        "symbol_exchange": symbol_exchange,
        "from": start_date,
        "to": end_date
    }
    # qveris call eodhd.eod_historical_data.retrieve.v1.a43f3b91
    cmd = [
        "qveris", "call", "eodhd.eod_historical_data.retrieve.v1.a43f3b91",
        "--params", json.dumps(params),
        "--json"
    ]
    print(f"正在调用 QVeris 查询 {symbol_exchange} ({start_date} 至 {end_date})...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"QVeris 调用失败，错误码 {result.returncode}。")
        if result.stderr:
            print(f"标准错误输出:\n{result.stderr}")
        return ""
    return result.stdout.strip()


def parse_qveris_json_to_rows(qveris_output: str) -> list[list[str]]:
    """将 QVeris 返回的原始输出转换为 TWSE 月度 json 中的 data 格式。"""
    csv_text = ""

    # 1. 尝试作为整体 JSON 解析并提取 result 中的 data 字段
    try:
        payload = json.loads(qveris_output)
        if isinstance(payload, dict):
            res_obj = payload.get("result")
            if isinstance(res_obj, dict):
                csv_text = res_obj.get("data", "")
            elif isinstance(res_obj, str):
                csv_text = res_obj
            else:
                csv_text = payload.get("data", "")
        elif isinstance(payload, str):
            csv_text = payload
    except Exception:
        pass

    # 如果 csv_text 解析出来的依然是个 dict（安全保护）
    if isinstance(csv_text, dict):
        csv_text = csv_text.get("data", "") or csv_text.get("result", "")

    # 2. 如果失败，尝试提取被双引号包裹的 CSV 转义大文本段（针对带 billing 等提示的多行输出）
    if not csv_text or not isinstance(csv_text, str):
        match = re.search(r'"(Date,Open,High,Low,Close,Adjusted_close,Volume\\n.*?)"', qveris_output, re.DOTALL)
        if match:
            try:
                # 重新用 json.loads 解密该转义后的 CSV 字符串
                csv_text = json.loads('"' + match.group(1) + '"')
            except Exception as exc:
                print(f"提取并解密转义 CSV 失败: {exc}")

    # 3. 如果还是没有，尝试通过按行过滤提取
    if not csv_text or not isinstance(csv_text, str):
        lines = qveris_output.strip().splitlines()
        csv_lines = []
        for line in lines:
            # 如果某行本身包含符合 CSV 的特征（如 7 列逗号），或者是 header 或者是日期开头
            if line.startswith("Date,Open") or re.match(r'^\d{4}-\d{2}-\d{2},', line):
                csv_lines.append(line)
        if csv_lines:
            csv_text = "\n".join(csv_lines)

    if not csv_text or not isinstance(csv_text, str):
        print("未能在输出中提取出任何合法的 CSV 文本段。")
        return []


    lines = csv_text.strip().splitlines()
    if not lines or len(lines) < 2:
        return []

    # 第一行是 header: Date,Open,High,Low,Close,Adjusted_close,Volume
    data_rows = []
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7:
            continue
        try:
            date_str = parts[0]  # YYYY-MM-DD
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            # 转为民國年格式: "115/06/25"
            roc_year = dt.year - 1911
            roc_date = f"{roc_year}/{dt.month:02d}/{dt.day:02d}"

            open_val = parts[1]
            high_val = parts[2]
            low_val = parts[3]
            close_val = parts[4]
            volume_val = parts[6]

            # 估算成交金额
            amount_val = str(int(float(volume_val) * float(close_val)))

            # TWSE data 列表行包含 10 列：
            # ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌價差", "成交筆數", "註記"]
            row = [
                roc_date,
                volume_val,
                amount_val,
                open_val,
                high_val,
                low_val,
                close_val,
                "0.00",  # 涨跌价差默认
                "0",     # 成交笔数默认
                ""       # 备注
            ]
            data_rows.append(row)
        except Exception as exc:
            print(f"解析 CSV 数据行时出错 '{line}': {exc}")
            continue

    return data_rows


def update_local_cache(symbol: str, month: str, new_rows: list[list[str]]) -> None:
    cache_path = CACHE_DIR / f"{symbol}_{month}.json"
    cache_data = {
        "stat": "OK",
        "date": f"{month}01",
        "title": f"民國年 06月 {symbol} 各日成交資訊",
        "fields": ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌價差", "成交筆數", "註記"],
        "data": []
    }

    if cache_path.exists():
        try:
            cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"读取旧缓存失败: {exc}，将覆盖重建。")

    # 合并数据并根据日期去重，保留最新数据
    existing_data = {row[0]: row for row in cache_data.get("data", [])}
    for row in new_rows:
        existing_data[row[0]] = row  # 覆盖或者新增

    # 按日期排序
    sorted_dates = sorted(existing_data.keys(), key=lambda d: [int(x) for x in d.split("/")])
    cache_data["data"] = [existing_data[d] for d in sorted_dates]

    # 写回文件
    cache_path.write_text(json.dumps(cache_data, ensure_ascii=False), encoding="utf-8")
    print(f"已成功更新缓存 {cache_path.name}，当前共有 {len(cache_data['data'])} 天数据。")


def main() -> None:
    print("=== QVeris 行情同步 fallback 启动 ===")

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

    # 2. 定位时间范围：抓取本月的最新数据
    today = datetime.today()
    start_date = f"{today.year}-{today.month:02d}-01"
    end_date = today.strftime("%Y-%m-%d")
    month_str = today.strftime("%Y%m")  # 格式如 "202606"

    # 3. 逐个更新
    success_count = 0
    for symbol in symbols:
        try:
            # 每次请求前休眠 3 秒，规避 QVeris 网关高频限制
            time.sleep(3.0)
            raw_output = run_qveris_call(symbol, start_date, end_date)
            if not raw_output:
                print(f"警告: 抓取标的 {symbol} 数据失败，跳过。")
                continue
            new_rows = parse_qveris_json_to_rows(raw_output)
            if not new_rows:
                print(f"警告: 标的 {symbol} 返回数据解析为空，跳过。")
                continue
            update_local_cache(symbol, month_str, new_rows)
            success_count += 1
        except Exception as exc:
            print(f"处理标的 {symbol} 时发生异常: {exc}")

    print(f"\n=== 同步完成: 成功 {success_count}/{len(symbols)} 档标的 ===")


if __name__ == "__main__":
    main()

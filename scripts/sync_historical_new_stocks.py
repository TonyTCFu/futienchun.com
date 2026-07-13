#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次性补齐新个股历史 K 线数据脚本：
使用 QVeris API 分段拉取 2049.TW, 3491.TW, 2313.TW 自 2024-01-01 至今的完整历史 K 线，
并按年月拆分、去重合并到本地 cache json 中。
"""

import os
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "cache"

NEW_STOCKS = ["2049", "3491", "2313"]

def run_qveris_call(symbol: str, start_date: str, end_date: str) -> str:
    symbol_exchange = f"{symbol}.TW"
    params = {
        "symbol_exchange": symbol_exchange,
        "from": start_date,
        "to": end_date
    }
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

def parse_qveris_csv_to_daily_rows(qveris_output: str) -> list[tuple[str, str, list[str]]]:
    """
    解析 QVeris 输出的 CSV 内容，
    返回包含 (month_str, roc_date, row_data) 的列表，用于按月切分。
    """
    import re
    csv_text = ""
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

    if isinstance(csv_text, dict):
        csv_text = csv_text.get("data", "") or csv_text.get("result", "")

    if not csv_text or not isinstance(csv_text, str):
        match = re.search(r'"(Date,Open,High,Low,Close,Adjusted_close,Volume\\n.*?)"', qveris_output, re.DOTALL)
        if match:
            try:
                csv_text = json.loads('"' + match.group(1) + '"')
            except Exception:
                pass

    if not csv_text or not isinstance(csv_text, str):
        lines = qveris_output.strip().splitlines()
        csv_lines = []
        for line in lines:
            if line.startswith("Date,Open") or re.match(r'^\d{4}-\d{2}-\d{2},', line):
                csv_lines.append(line)
        if csv_lines:
            csv_text = "\n".join(csv_lines)

    if not csv_text or not isinstance(csv_text, str):
        print("未能提取出合法 CSV 文本段。")
        return []

    lines = csv_text.strip().splitlines()
    if not lines or len(lines) < 2:
        return []

    rows_by_date = []
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7:
            continue
        try:
            date_str = parts[0]  # YYYY-MM-DD
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            
            roc_year = dt.year - 1911
            roc_date = f"{roc_year}/{dt.month:02d}/{dt.day:02d}"
            month_str = f"{dt.year}{dt.month:02d}"  # 例如 "202401"

            open_val = parts[1]
            high_val = parts[2]
            low_val = parts[3]
            close_val = parts[4]
            volume_val = parts[6]
            amount_val = str(int(float(volume_val) * float(close_val)))

            row = [
                roc_date,
                volume_val,
                amount_val,
                open_val,
                high_val,
                low_val,
                close_val,
                "0.00",
                "0",
                ""
            ]
            rows_by_date.append((month_str, roc_date, row))
        except Exception as exc:
            print(f"解析行出错 '{line}': {exc}")
            continue

    return rows_by_date

def save_to_monthly_caches(symbol: str, parsed_rows: list[tuple[str, str, list[str]]]):
    data_by_month = {}
    for month_str, roc_date, row in parsed_rows:
        if month_str not in data_by_month:
            data_by_month[month_str] = []
        data_by_month[month_str].append(row)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
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
                print(f"读取 {cache_path.name} 失败: {exc}，将覆盖重建。")

        existing_data = {r[0]: r for r in cache_data.get("data", [])}
        for r in rows:
            existing_data[r[0]] = r  # 合并覆盖

        # 排序
        sorted_dates = sorted(existing_data.keys(), key=lambda d: [int(x) for x in d.split("/")])
        cache_data["data"] = [existing_data[d] for d in sorted_dates]

        cache_path.write_text(json.dumps(cache_data, ensure_ascii=False), encoding="utf-8")
        print(f"  已保存/合并缓存: {cache_path.name}，包含 {len(cache_data['data'])} 天数据。")

def main():
    print("=== 开始分段拉取新个股 2024-01 至今的历史 K 线 ===")
    
    end_date = datetime.today().strftime("%Y-%m-%d")
    intervals = [
        ("2024-01-01", "2024-12-31"),
        ("2025-01-01", "2025-12-31"),
        ("2026-01-01", end_date)
    ]
    
    for symbol in NEW_STOCKS:
        print(f"\n--- 处理标的: {symbol} ---")
        all_parsed_rows = []
        for start_dt, end_dt in intervals:
            qveris_out = run_qveris_call(symbol, start_dt, end_dt)
            if not qveris_out:
                print(f"  警告: 无法获取 {symbol} 在 {start_dt} 至 {end_dt} 的数据。")
                continue
            
            parsed_rows = parse_qveris_csv_to_daily_rows(qveris_out)
            if not parsed_rows:
                print(f"  警告: {symbol} 在 {start_dt} 至 {end_dt} 的行情数据解析为空。")
                continue
            
            print(f"  成功解析 {start_dt} 至 {end_dt} 共 {len(parsed_rows)} 条记录。")
            all_parsed_rows.extend(parsed_rows)
            time.sleep(3.0)  # 礼貌防频限
            
        if not all_parsed_rows:
            print(f"错误: {symbol} 的历史数据全部拉取失败。")
            continue
            
        print(f"合并成功，共 {len(all_parsed_rows)} 条日线记录。正在保存到月缓存...")
        save_to_monthly_caches(symbol, all_parsed_rows)

    print("\n=== 所有新股历史数据同步合并完成 ===")

if __name__ == "__main__":
    main()

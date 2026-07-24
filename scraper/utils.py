"""工具函数：请求封装、数据清洗、文件IO"""
import json
import os
import re
import random
import time
from datetime import datetime, timezone, timedelta

import requests

from config import PROXY, TIMEOUT, MAX_RETRIES, REQUEST_DELAY, OUTPUT_DIR


def log(msg: str):
    """带时间的日志输出"""
    ts = datetime.now(timezone(timedelta(hours=8))).strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')


def get_timestamp() -> str:
    """ISO 格式时间戳"""
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def make_request(url: str, headers: dict | None = None,
                 proxy: bool = True, params: dict | None = None) -> requests.Response | None:
    """带重试、代理、随机延迟的 GET 请求"""
    proxies = PROXY if proxy else None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            delay = random.uniform(*REQUEST_DELAY)
            time.sleep(delay)
            resp = requests.get(
                url, headers=headers, proxies=proxies,
                params=params, timeout=TIMEOUT,
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            log(f'请求失败 ({attempt}/{MAX_RETRIES}): {e}')
    return None


def clean_price(price_str) -> float:
    """价格字符串 → float，失败返回 0.0"""
    if price_str is None:
        return 0.0
    s = str(price_str).replace('¥', '').replace('￥', '').replace(',', '').strip()
    m = re.search(r'[\d.]+', s)
    return float(m.group()) if m else 0.0


def clean_sales(sales_str) -> int:
    """销量清洗：'1万+' → 10000, '2.3万' → 23000"""
    if sales_str is None:
        return 0
    s = str(sales_str).replace('+', '').replace('件', '').replace('已拼', '').strip()
    m = re.search(r'([\d.]+)\s*万', s)
    if m:
        return int(float(m.group(1)) * 10000)
    m = re.search(r'[\d]+', s.replace(',', ''))
    return int(m.group()) if m else 0


def save_json(data, filename: str):
    """保存数据到 data/ 目录"""
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log(f'已保存 → {path} ({len(data)} 条)')


def load_json(filename: str) -> list:
    """读取已有数据，支持 dict(keywords结构) 和 list 两种格式"""
    path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and 'keywords' in data:
                # 旧格式: {"keywords": {"牛奶": [...]}} → 展平为 list
                items = []
                for kw_items in data['keywords'].values():
                    items.extend(kw_items)
                return items
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, IOError):
            pass
    return []


def _normalize_item(item: dict) -> dict:
    """统一字段名（兼容旧格式 originalPrice/shop → original_price/shop_name）"""
    if 'originalPrice' in item and 'original_price' not in item:
        item['original_price'] = item.pop('originalPrice')
    if 'shop' in item and 'shop_name' not in item:
        item['shop_name'] = item.pop('shop')
    return item


def merge_items(existing: list, new_items: list) -> list:
    """合并去重（按 id），兼容旧格式字段名"""
    merged = []
    seen = set()
    for item in existing:
        if not isinstance(item, dict):
            continue
        item = _normalize_item(item)
        if item.get('id') not in seen:
            merged.append(item)
            seen.add(item.get('id'))
    for item in new_items:
        if not isinstance(item, dict):
            continue
        if item.get('id') not in seen:
            merged.append(item)
            seen.add(item.get('id'))
    return merged

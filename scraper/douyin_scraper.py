"""抖音团购搜索抓取

抖音团购反爬较严：
- 主要数据通过 https://www.douyin.com/aweme/v1/web/search/ 等API加载
- 需要有效的 X-Bogus / a_bogus 签名参数
- 没有签名参数，API 会返回空或 403
- 网页版 HTML 不含商品数据（纯 SPA）

策略: 尝试网页搜索页 → 提取可能的 SSR/内联数据 → 失败则降级
"""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DESKTOP_UA
from utils import (make_request, clean_price, clean_sales,
                   save_json, load_json, merge_items, log)

HEADERS = {
    'User-Agent': DESKTOP_UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://www.douyin.com/',
}


def _parse_items(raw_items: list, keyword: str) -> list[dict]:
    """解析抖音团购商品列表"""
    items = []
    for idx, it in enumerate(raw_items):
        try:
            title = it.get('title', '') or it.get('name', '') or it.get('group_name', '')
            if not title:
                continue
            price = clean_price(it.get('price', 0) or it.get('sale_price', 0))
            # 抖音价格有时以分为单位
            if price > 1000 and '.' not in str(it.get('price', '')):
                price = price / 100
            original = clean_price(it.get('origin_price', 0) or it.get('market_price', 0) or price)
            if original > 1000 and '.' not in str(it.get('origin_price', '')):
                original = original / 100
            rating = 0
            try:
                rating = float(it.get('score', 0) or it.get('rating', 0))
            except (ValueError, TypeError):
                pass
            items.append({
                'id': f'douyin_{keyword}_{idx}',
                'title': title,
                'price': price,
                'original_price': original,
                'platform': 'douyin',
                'platform_name': '抖音',
                'url': it.get('url', '') or it.get('share_url', ''),
                'image': it.get('cover', '') or it.get('image_url', ''),
                'sales': clean_sales(it.get('sold_count', 0) or it.get('sales', 0)),
                'coupon': '',
                'source': 'real',
                'rating': rating,
                'shop_name': it.get('poi_name', '') or it.get('shop_name', ''),
                'category': keyword,
            })
        except Exception as e:
            log(f'[抖音] 解析第 {idx} 条失败: {e}')
            continue
    return items


def _try_web_search(keyword: str) -> list[dict]:
    """尝试抖音搜索页面"""
    import urllib.parse
    url = f'https://www.douyin.com/search/{urllib.parse.quote(keyword)}?type=general'
    resp = make_request(url, headers=HEADERS, proxy=True)
    if resp is None:
        return []

    html = resp.text
    if len(html) < 500:
        log('[抖音] 页面为空')
        return []

    # 尝试提取 SSR 数据 (RENDER_DATA / __NEXT_DATA__)
    import json
    patterns = [
        r'<script id="RENDER_DATA" type="application/json">(.*?)</script>',
        r'window\._SSR_DATA\s*=\s*({.*?})\s*;?\s*</script>',
        r'"group_list"\s*:\s*(\[.*?\])\s*[,}]',
        r'"goods_list"\s*:\s*(\[.*?\])\s*[,}]',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.DOTALL)
        if m:
            try:
                raw_text = m.group(1)
                # RENDER_DATA 可能是 URL-encoded
                if '%' in raw_text[:50]:
                    raw_text = urllib.parse.unquote(raw_text)
                data = json.loads(raw_text)
                # 递归查找列表
                raw = _find_items_list(data)
                if raw:
                    return _parse_items(raw, keyword)
            except (json.JSONDecodeError, Exception):
                continue

    log('[抖音] 未能从页面提取团购数据（需要有效签名参数）')
    return []


def _find_items_list(data, depth=0) -> list | None:
    """递归查找包含团购商品的列表"""
    if depth > 5:
        return None
    if isinstance(data, list) and len(data) > 0:
        if isinstance(data[0], dict) and ('title' in data[0] or 'group_name' in data[0]):
            return data
    if isinstance(data, dict):
        for key in ('group_list', 'goods_list', 'items', 'list', 'data'):
            if key in data:
                result = _find_items_list(data[key], depth + 1)
                if result:
                    return result
        for v in data.values():
            if isinstance(v, (dict, list)):
                result = _find_items_list(v, depth + 1)
                if result:
                    return result
    return None


def scrape(keyword: str) -> list[dict]:
    """抖音团购搜索，失败返回空列表"""
    log(f'[抖音] 搜索: {keyword}')
    items = _try_web_search(keyword)
    if items:
        log(f'[抖音] 获取 {len(items)} 条团购')
    else:
        log('[抖音] 抓取失败（反爬严格），返回空列表')
    return items


def run_and_save(query_str: str):
    """解析关键词，抓取并合并保存到 groupbuy.json"""
    keywords = [k.strip() for k in query_str.split(',') if k.strip()]
    all_items = []
    for kw in keywords:
        all_items.extend(scrape(kw))

    existing = load_json('groupbuy.json')
    merged = merge_items(existing, all_items)
    save_json(merged, 'groupbuy.json')
    log(f'[抖音] 总计 {len(merged)} 条 (新增 {len(all_items)})')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='抖音团购搜索抓取')
    parser.add_argument('--query', required=True, help='搜索关键词，逗号分隔')
    args = parser.parse_args()
    run_and_save(args.query)

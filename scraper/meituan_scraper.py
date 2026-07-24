"""美团团购搜索抓取

搜索页: https://www.meituan.com/s/{keyword}
美团网页搜索页数据主要通过前端渲染，HTML中可能包含 SSR 数据。
策略: 请求搜索页 → 提取内联 JSON / HTML 解析 → 失败则降级
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
    'Referer': 'https://www.meituan.com/',
}

BASE_URL = 'https://www.meituan.com/s/{keyword}'


def _parse_items(raw_items: list, keyword: str) -> list[dict]:
    """解析美团团购商品列表"""
    items = []
    for idx, it in enumerate(raw_items):
        try:
            title = it.get('title', '') or it.get('name', '') or it.get('dealTitle', '')
            if not title:
                continue
            price = clean_price(it.get('price', 0) or it.get('currentPrice', 0))
            original = clean_price(it.get('value', 0) or it.get('originPrice', 0) or price)
            rating = 0
            try:
                rating = float(it.get('avgScore', 0) or it.get('rating', 0))
            except (ValueError, TypeError):
                pass
            items.append({
                'id': f'meituan_{keyword}_{idx}',
                'title': title,
                'price': price,
                'original_price': original,
                'platform': 'meituan',
                'platform_name': '美团',
                'url': it.get('url', '') or f'https://www.meituan.com/deal/{it.get("dealId", "")}',
                'image': it.get('imageUrl', '') or it.get('imgUrl', ''),
                'sales': clean_sales(it.get('sold', 0) or it.get('salesCount', 0)),
                'coupon': '',
                'source': 'real',
                'rating': rating,
                'shop_name': it.get('brandName', '') or it.get('poiName', ''),
                'category': keyword,
            })
        except Exception as e:
            log(f'[美团] 解析第 {idx} 条失败: {e}')
            continue
    return items


def _try_web_search(keyword: str) -> list[dict]:
    """请求美团搜索网页，尝试提取数据"""
    import urllib.parse
    url = BASE_URL.format(keyword=urllib.parse.quote(keyword))
    resp = make_request(url, headers=HEADERS, proxy=True)
    if resp is None:
        return []

    html = resp.text

    # 检测是否被拦截
    if len(html) < 500 or '验证' in html[:1000]:
        log('[美团] 页面为空或触发验证')
        return []

    # 尝试从 SSR 数据提取 JSON
    patterns = [
        r'window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;?\s*</script>',
        r'"dealList"\s*:\s*(\[.*?\])\s*[,}]',
        r'"poiList"\s*:\s*(\[.*?\])\s*[,}]',
        r'"searchResult"\s*:\s*({.*?})\s*[,}]',
    ]
    import json
    for pat in patterns:
        m = re.search(pat, html, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                if isinstance(data, list):
                    return _parse_items(data, keyword)
                # 嵌套结构
                raw = (data.get('dealList') or data.get('poiList')
                       or data.get('data', {}).get('list', []))
                if raw:
                    return _parse_items(raw, keyword)
            except (json.JSONDecodeError, AttributeError):
                continue

    # 尝试 BeautifulSoup 解析 HTML 结构
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        deal_cards = soup.select('.deal-card, .poi-card, .search-deal-item, [class*="deal"]')
        if deal_cards:
            items = []
            for idx, card in enumerate(deal_cards[:20]):
                title_el = card.select_one('.deal-title, .poi-name, h3, [class*="title"]')
                price_el = card.select_one('.deal-price, .price, [class*="price"]')
                title = title_el.get_text(strip=True) if title_el else ''
                price = clean_price(price_el.get_text(strip=True)) if price_el else 0
                if title:
                    items.append({
                        'id': f'meituan_{keyword}_{idx}',
                        'title': title, 'price': price, 'original_price': price,
                        'platform': 'meituan', 'platform_name': '美团',
                        'url': '', 'image': '', 'sales': 0,
                        'coupon': '', 'source': 'real', 'rating': 0,
                        'shop_name': '', 'category': keyword,
                    })
            if items:
                return items
    except ImportError:
        pass

    log('[美团] 未能从页面提取商品数据')
    return []


def scrape(keyword: str) -> list[dict]:
    """美团团购搜索，失败返回空列表"""
    log(f'[美团] 搜索: {keyword}')
    items = _try_web_search(keyword)
    if items:
        log(f'[美团] 获取 {len(items)} 条团购')
    else:
        log('[美团] 抓取失败，返回空列表')
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
    log(f'[美团] 总计 {len(merged)} 条 (新增 {len(all_items)})')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='美团团购搜索抓取')
    parser.add_argument('--query', required=True, help='搜索关键词，逗号分隔')
    args = parser.parse_args()
    run_and_save(args.query)

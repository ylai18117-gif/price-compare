"""拼多多移动端搜索抓取

目标: https://mobile.yangkeduo.com/search_result.html?search_key={keyword}
反爬非常严格：
- 需要有效的 anti_content / anti-spam 参数
- 频繁请求会触发验证码
- 数据通过异步 API 加载，HTML 页面本身不包含商品 JSON
- 大概率需要降级（返回空列表）

策略: 尝试请求移动端页面 → 解析可能的内联数据 → 失败则降级
"""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import MOBILE_UA
from utils import make_request, clean_price, clean_sales, log

# UA 轮换池（拼多多反爬会检测固定UA）
_UA_POOL = [
    MOBILE_UA,
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
]

_BASE = 'https://mobile.yangkeduo.com/search_result.html'


def _get_headers(idx: int = 0) -> dict:
    """轮换 UA"""
    ua = _UA_POOL[idx % len(_UA_POOL)]
    return {
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://mobile.yangkeduo.com/',
    }


def _try_search_page(keyword: str) -> list[dict]:
    """尝试请求搜索页并提取内联数据"""
    import urllib.parse
    url = f'{_BASE}?search_key={urllib.parse.quote(keyword)}'
    headers = _get_headers(hash(keyword) % len(_UA_POOL))
    resp = make_request(url, headers=headers, proxy=True)
    if resp is None:
        return []

    html = resp.text

    # 检测是否触发验证码 / 反爬
    if 'verify' in html.lower() or 'captcha' in html.lower() or len(html) < 500:
        log('[拼多多] 触发反爬验证或页面为空')
        return []

    # 尝试从 window.__INITIAL_STATE__ 或 rawResponse 提取 JSON
    patterns = [
        r'window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;',
        r'"goods_list"\s*:\s*(\[.*?\])\s*[,}]',
        r'"items"\s*:\s*(\[.*?\])\s*[,}]',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.DOTALL)
        if m:
            try:
                import json
                data = json.loads(m.group(1))
                raw = data if isinstance(data, list) else data.get('goods_list', data.get('items', []))
                return _parse_items(raw, keyword)
            except Exception:
                continue

    log('[拼多多] 页面中未找到商品数据（数据可能通过异步API加载）')
    return []


def _parse_items(raw_items: list, keyword: str) -> list[dict]:
    items = []
    for idx, it in enumerate(raw_items):
        try:
            items.append({
                'id': f'pdd_{keyword}_{idx}',
                'title': it.get('goods_name', '') or it.get('title', ''),
                'price': clean_price(it.get('min_group_price', 0) or it.get('price', 0)) / 100,
                'original_price': clean_price(it.get('min_normal_price', 0) or it.get('price', 0)) / 100,
                'platform': 'pdd',
                'platform_name': '拼多多',
                'url': f'https://mobile.yangkeduo.com/goods.html?goods_id={it.get("goods_id", "")}',
                'image': it.get('image_url', '') or it.get('thumb_url', ''),
                'sales': clean_sales(it.get('sales_tip', 0)),
                'coupon': it.get('coupon_discount', ''),
                'source': 'real',
                'rating': 0,
                'shop_name': it.get('mall_name', ''),
                'category': keyword,
            })
        except Exception:
            continue
    return items


def scrape(keyword: str) -> list[dict]:
    """拼多多搜索，失败返回空列表"""
    log(f'[拼多多] 搜索: {keyword}')
    items = _try_search_page(keyword)
    if items:
        log(f'[拼多多] 获取 {len(items)} 条商品')
    else:
        log('[拼多多] 抓取失败（反爬严格），返回空列表')
    return items


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='拼多多商品搜索抓取')
    parser.add_argument('--query', required=True, help='搜索关键词，逗号分隔')
    args = parser.parse_args()
    for kw in [k.strip() for k in args.query.split(',') if k.strip()]:
        results = scrape(kw)
        log(f'  → {kw}: {len(results)} 条')

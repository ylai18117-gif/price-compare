"""淘宝搜索抓取（多级降级）

方案1: 移动端 H5 mtop API —— 需要 sign 签名 + _m_h5_tk cookie，成功率极低
方案2: 桌面端网页 https://s.taobao.com/search?q= —— 需要登录 cookie，否则跳转登录页
方案3: 最终降级 —— 记录日志，返回空列表

淘宝反爬非常严格：
- mtop 接口需要 sign = md5(token + '&' + timestamp + '&' + appKey + '&' + data)
- 没有有效的 _m_h5_tk token 就无法生成正确 sign
- 网页版需要登录态 cookie，未登录会返回 302 到 login.taobao.com
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import MOBILE_UA, DESKTOP_UA
from utils import make_request, clean_price, clean_sales, log

import hashlib
import time
import json


def _try_mtop_api(keyword: str) -> list[dict]:
    """方案1: mtop H5 API（大概率因缺少有效 token 而失败）"""
    log('[淘宝] 尝试方案1: mtop H5 API...')
    ts = str(int(time.time() * 1000))
    app_key = '12574478'
    data_str = json.dumps({'keyword': keyword, 'page': '1'})

    # 没有有效 _m_h5_tk，token 为空 → sign 必然无效
    token = ''
    sign_str = f'{token}&{ts}&{app_key}&{data_str}'
    sign = hashlib.md5(sign_str.encode()).hexdigest()

    url = 'https://h5api.m.taobao.com/h5/mtop.relationrecommend.wirelessrecommend.recommend/2.0/'
    params = {
        'jsv': '2.7.2', 'appKey': app_key, 't': ts,
        'sign': sign, 'api': 'mtop.relationrecommend.WirelessRecommend.recommend',
        'v': '2.0', 'type': 'jsonp', 'dataType': 'jsonp',
        'data': data_str,
    }
    headers = {'User-Agent': MOBILE_UA, 'Referer': 'https://s.m.taobao.com/'}
    resp = make_request(url, headers=headers, proxy=True, params=params)
    if resp is None:
        return []
    try:
        body = resp.json()
        # 检查是否返回了有效的商品数据
        items_data = body.get('data', {}).get('itemsArray', [])
        if not items_data:
            log(f'[淘宝] mtop 返回无数据 (ret={body.get("ret", "?")})')
            return []
        return _parse_mtop_items(items_data, keyword)
    except Exception as e:
        log(f'[淘宝] mtop 解析失败: {e}')
        return []


def _parse_mtop_items(raw_items: list, keyword: str) -> list[dict]:
    """解析 mtop 返回的商品数据"""
    items = []
    for idx, it in enumerate(raw_items):
        try:
            items.append({
                'id': f'taobao_{keyword}_{idx}',
                'title': it.get('title', ''),
                'price': clean_price(it.get('priceShow', {}).get('price', 0)),
                'original_price': clean_price(it.get('priceShow', {}).get('price', 0)),
                'platform': 'taobao',
                'platform_name': '淘宝',
                'url': f'https://item.taobao.com/item.htm?id={it.get("item_id", "")}',
                'image': it.get('pic_path', ''),
                'sales': clean_sales(it.get('realSales', 0)),
                'coupon': '',
                'source': 'real',
                'rating': 0,
                'shop_name': it.get('shopInfo', {}).get('title', ''),
                'category': keyword,
            })
        except Exception:
            continue
    return items


def _try_web_search(keyword: str) -> list[dict]:
    """方案2: 桌面端网页搜索（需要登录cookie，否则被重定向到登录页）"""
    log('[淘宝] 尝试方案2: 桌面端网页搜索...')
    url = f'https://s.taobao.com/search?q={keyword}'
    headers = {
        'User-Agent': DESKTOP_UA,
        'Accept': 'text/html,application/xhtml+xml',
        'Referer': 'https://www.taobao.com/',
    }
    resp = make_request(url, headers=headers, proxy=True)
    if resp is None:
        return []

    # 检测是否被重定向到登录页
    if 'login.taobao.com' in resp.url or '亲，请登录' in resp.text:
        log('[淘宝] 网页版需要登录，无法获取数据')
        return []

    # 尝试从页面中提取 JSON 数据（g_page_config / g_srp_loadData）
    import re
    match = re.search(r'g_page_config\s*=\s*({.*?});', resp.text, re.DOTALL)
    if not match:
        match = re.search(r'"itemsArray"\s*:\s*(\[.*?\])', resp.text, re.DOTALL)
    if not match:
        log('[淘宝] 网页中未找到商品数据')
        return []

    try:
        data = json.loads(match.group(1))
        raw = data.get('mods', {}).get('itemlist', {}).get('data', {}).get('auctions', [])
        items = []
        for idx, it in enumerate(raw):
            items.append({
                'id': f'taobao_{keyword}_{idx}',
                'title': it.get('raw_title', ''),
                'price': clean_price(it.get('view_price', 0)),
                'original_price': clean_price(it.get('view_price', 0)),
                'platform': 'taobao',
                'platform_name': '淘宝',
                'url': f'https://item.taobao.com/item.htm?id={it.get("nid", "")}',
                'image': it.get('pic_url', ''),
                'sales': clean_sales(it.get('view_sales', 0)),
                'coupon': '',
                'source': 'real',
                'rating': 0,
                'shop_name': it.get('nick', ''),
                'category': keyword,
            })
        return items
    except Exception as e:
        log(f'[淘宝] 网页数据解析失败: {e}')
        return []


def scrape(keyword: str) -> list[dict]:
    """淘宝搜索：依次尝试 mtop → 网页 → 返回空"""
    log(f'[淘宝] 搜索: {keyword}')
    # 方案1
    items = _try_mtop_api(keyword)
    if items:
        log(f'[淘宝] mtop 成功，{len(items)} 条')
        return items
    # 方案2
    items = _try_web_search(keyword)
    if items:
        log(f'[淘宝] 网页成功，{len(items)} 条')
        return items
    # 方案3: 降级
    log('[淘宝] 所有方案均失败（需要有效cookie/token），返回空列表')
    return []


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='淘宝商品搜索抓取')
    parser.add_argument('--query', required=True, help='搜索关键词，逗号分隔')
    args = parser.parse_args()
    for kw in [k.strip() for k in args.query.split(',') if k.strip()]:
        results = scrape(kw)
        log(f'  → {kw}: {len(results)} 条')

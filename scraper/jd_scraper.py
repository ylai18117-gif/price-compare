"""京东移动端搜索抓取
API: https://so.m.jd.com/ware/search.action?keyword={q}&datatype=json
无需签名，移动端UA即可访问。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import MOBILE_UA
from utils import make_request, clean_price, clean_sales, save_json, load_json, merge_items, log


HEADERS = {
    'User-Agent': MOBILE_UA,
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://so.m.jd.com/',
}

BASE_URL = 'https://so.m.jd.com/ware/search.action'


def scrape(keyword: str) -> list[dict]:
    """抓取京东搜索结果，失败返回空列表"""
    log(f'[京东] 搜索: {keyword}')
    params = {'keyword': keyword, 'datatype': 'json', 'pagesize': 20}
    resp = make_request(BASE_URL, headers=HEADERS, proxy=True, params=params)
    if resp is None:
        log('[京东] 请求失败，所有重试已耗尽')
        return []

    try:
        data = resp.json()
    except Exception as e:
        log(f'[京东] JSON 解析失败: {e}')
        return []

    # 响应结构: {"wareInfo": [...]} 或 {"result": {"wareInfo": [...]}}
    ware_list = data.get('wareInfo') or data.get('result', {}).get('wareInfo', [])
    if not ware_list:
        log('[京东] 未找到商品数据（可能需要更换UA或接口已变）')
        return []

    items = []
    for idx, w in enumerate(ware_list):
        try:
            title = w.get('wname', '') or w.get('ad_title', '')
            if not title:
                continue
            price = clean_price(w.get('jdPrice') or w.get('price'))
            image = w.get('imageurl', '')
            if image and not image.startswith('http'):
                image = 'https:' + image
            shop = w.get('shopName', '') or w.get('venderId', '')
            sku_id = w.get('wareId', '') or w.get('sku_id', str(idx))
            url = f'https://item.m.jd.com/product/{sku_id}.html' if sku_id else ''
            sales = clean_sales(w.get('commentCount', 0))

            items.append({
                'id': f'jd_{keyword}_{idx}',
                'title': title,
                'price': price,
                'original_price': price,
                'platform': 'jd',
                'platform_name': '京东',
                'url': url,
                'image': image,
                'sales': sales,
                'coupon': '',
                'source': 'real',
                'rating': 0,
                'shop_name': str(shop),
                'category': keyword,
            })
        except Exception as e:
            log(f'[京东] 解析第 {idx} 条失败: {e}')
            continue

    log(f'[京东] 获取 {len(items)} 条商品')
    return items


def run_and_save(query_str: str):
    """解析逗号分隔的关键词，抓取并合并保存"""
    keywords = [k.strip() for k in query_str.split(',') if k.strip()]
    all_items = []
    for kw in keywords:
        all_items.extend(scrape(kw))

    existing = load_json('shopping.json')
    merged = merge_items(existing, all_items)
    save_json(merged, 'shopping.json')
    log(f'[京东] 总计 {len(merged)} 条 (新增 {len(all_items)})')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='京东商品搜索抓取')
    parser.add_argument('--query', required=True, help='搜索关键词，逗号分隔')
    args = parser.parse_args()
    run_and_save(args.query)

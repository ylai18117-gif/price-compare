#!/usr/bin/env python3
"""
比价数据聚合脚本 - 一键抓取所有平台数据
用法: python run_all.py --query "牛奶,纸巾,洗衣液"
      python run_all.py --query "火锅,奶茶" --type tuan
      python run_all.py --query "牛奶" --type all
"""
import argparse
import sys
import time
from datetime import datetime

from utils import log, load_json, save_json, merge_items, get_timestamp
import jd_scraper
import taobao_scraper
import pdd_scraper
import meituan_scraper
import douyin_scraper


def run_shopping(keywords: list[str]) -> dict:
    """抓取购物平台数据（京东/淘宝/拼多多）"""
    results = {"success": {}, "failed": {}}

    for kw in keywords:
        log(f"{'='*50}")
        log(f"开始抓取购物数据: {kw}")
        items = []

        # 京东
        try:
            jd_items = jd_scraper.scrape(kw)
            items.extend(jd_items)
            results["success"][f"京东-{kw}"] = len(jd_items)
            log(f"  京东: {len(jd_items)} 条")
        except Exception as e:
            results["failed"][f"京东-{kw}"] = str(e)
            log(f"  京东: 失败 - {e}")

        time.sleep(1)

        # 淘宝
        try:
            tb_items = taobao_scraper.scrape(kw)
            items.extend(tb_items)
            results["success"][f"淘宝-{kw}"] = len(tb_items)
            log(f"  淘宝: {len(tb_items)} 条")
        except Exception as e:
            results["failed"][f"淘宝-{kw}"] = str(e)
            log(f"  淘宝: 失败 - {e}")

        time.sleep(1)

        # 拼多多
        try:
            pdd_items = pdd_scraper.scrape(kw)
            items.extend(pdd_items)
            results["success"][f"拼多多-{kw}"] = len(pdd_items)
            log(f"  拼多多: {len(pdd_items)} 条")
        except Exception as e:
            results["failed"][f"拼多多-{kw}"] = str(e)
            log(f"  拼多多: 失败 - {e}")

        # 合并到 shopping.json
        if items:
            existing = load_json("shopping.json")
            existing_items = existing.get("items", [])
            merged = merge_items(existing_items, items)
            save_json({
                "updated_at": get_timestamp(),
                "items": merged
            }, "shopping.json")
            log(f"  已保存: shopping.json ({len(merged)} 条总计)")

    return results


def run_groupbuy(keywords: list[str]) -> dict:
    """抓取团购数据（美团/抖音）"""
    results = {"success": {}, "failed": {}}

    for kw in keywords:
        log(f"{'='*50}")
        log(f"开始抓取团购数据: {kw}")
        items = []

        # 美团
        try:
            mt_items = meituan_scraper.scrape(kw)
            items.extend(mt_items)
            results["success"][f"美团-{kw}"] = len(mt_items)
            log(f"  美团: {len(mt_items)} 条")
        except Exception as e:
            results["failed"][f"美团-{kw}"] = str(e)
            log(f"  美团: 失败 - {e}")

        time.sleep(1)

        # 抖音
        try:
            dy_items = douyin_scraper.scrape(kw)
            items.extend(dy_items)
            results["success"][f"抖音-{kw}"] = len(dy_items)
            log(f"  抖音: {len(dy_items)} 条")
        except Exception as e:
            results["failed"][f"抖音-{kw}"] = str(e)
            log(f"  抖音: 失败 - {e}")

        # 合并到 groupbuy.json
        if items:
            existing = load_json("groupbuy.json")
            existing_items = existing.get("items", [])
            merged = merge_items(existing_items, items)
            save_json({
                "updated_at": get_timestamp(),
                "items": merged
            }, "groupbuy.json")
            log(f"  已保存: groupbuy.json ({len(merged)} 条总计)")

    return results


def print_summary(shopping_results: dict | None, tuan_results: dict | None):
    """打印抓取汇总"""
    log(f"\n{'='*60}")
    log("📊 抓取汇总")
    log(f"{'='*60}")

    for name, res in [("购物", shopping_results), ("团购", tuan_results)]:
        if res is None:
            continue
        log(f"\n【{name}比价】")
        total_ok = sum(res["success"].values())
        total_fail = len(res["failed"])
        log(f"  ✅ 成功: {total_ok} 条数据")
        for k, v in res["success"].items():
            if v > 0:
                log(f"     {k}: {v} 条")
        if total_fail:
            log(f"  ❌ 失败: {total_fail} 个平台")
            for k, v in res["failed"].items():
                log(f"     {k}: {v[:50]}")

    log(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    parser = argparse.ArgumentParser(description="多平台比价数据抓取")
    parser.add_argument("--query", required=True, help="搜索关键词，逗号分隔")
    parser.add_argument("--type", choices=["shopping", "tuan", "all"], default="all",
                        help="抓取类型: shopping(购物), tuan(团购), all(全部)")
    args = parser.parse_args()

    keywords = [kw.strip() for kw in args.query.split(",") if kw.strip()]
    if not keywords:
        log("❌ 未提供有效关键词")
        sys.exit(1)

    log(f"🚀 开始抓取 | 关键词: {keywords} | 类型: {args.type}")
    start = time.time()

    shopping_res = None
    tuan_res = None

    if args.type in ("shopping", "all"):
        shopping_res = run_shopping(keywords)

    if args.type in ("tuan", "all"):
        tuan_res = run_groupbuy(keywords)

    elapsed = time.time() - start
    print_summary(shopping_res, tuan_res)
    log(f"\n⏱️ 总耗时: {elapsed:.1f}秒")


if __name__ == "__main__":
    main()

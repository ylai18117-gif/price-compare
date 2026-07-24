#!/usr/bin/env python3
"""
数据上传脚本 - 将抓取的数据推送到 GitHub，触发 Cloudflare 自动部署
用法: python upload.py
      python upload.py --message "更新牛奶价格数据"
"""
import argparse
import subprocess
import sys
import os
from datetime import datetime

from utils import log


def run_git(args: list[str], cwd: str = None) -> tuple[int, str]:
    """执行 git 命令"""
    if cwd is None:
        cwd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    return result.returncode, result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description="上传数据到 GitHub")
    parser.add_argument("--message", "-m", default=None, help="提交信息")
    parser.add_argument("--dry-run", action="store_true", help="只显示状态，不提交")
    args = parser.parse_args()

    log("📤 检查数据变更...")

    # 检查 git 状态
    code, output = run_git(["status", "--short", "data/"])
    if code != 0:
        log(f"❌ git status 失败: {output}")
        sys.exit(1)

    if not output.strip():
        log("✅ 数据无变更，无需上传")
        return

    log(f"变更文件:\n{output}")

    if args.dry_run:
        log("🔍 dry-run 模式，不执行提交")
        return

    # 提交信息
    msg = args.message or f"data: 更新比价数据 {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # git add
    log("正在添加文件...")
    code, output = run_git(["add", "data/"])
    if code != 0:
        log(f"❌ git add 失败: {output}")
        sys.exit(1)

    # git commit
    log(f"正在提交: {msg}")
    code, output = run_git(["commit", "-m", msg])
    if code != 0:
        log(f"❌ git commit 失败: {output}")
        sys.exit(1)

    # git push
    log("正在推送到 GitHub...")
    code, output = run_git(["push", "origin", "main"])
    if code != 0:
        log(f"❌ git push 失败: {output}")
        log("提示: 请确认远程仓库已配置 (git remote -v)")
        sys.exit(1)

    log("✅ 推送成功！Cloudflare 将在约 60 秒内自动部署更新")
    log("🌐 站点: https://compare.lovemysoul.top")


if __name__ == "__main__":
    main()

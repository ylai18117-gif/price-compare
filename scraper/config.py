"""全局配置文件"""
import os

# 代理设置 (Clash Verge)
PROXY = {
    'http': 'http://127.0.0.1:7897',
    'https': 'http://127.0.0.1:7897',
}

# User-Agent 字符串
MOBILE_UA = (
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) '
    'AppleWebKit/605.1.15 (KHTML, like Gecko) '
    'Version/17.4 Mobile/15E148 Safari/604.1'
)

DESKTOP_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)

# 请求配置
TIMEOUT = 15          # 秒
MAX_RETRIES = 3       # 最大重试次数
REQUEST_DELAY = (1, 3)  # 随机延迟范围（秒）

# 输出目录（相对于本文件）
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

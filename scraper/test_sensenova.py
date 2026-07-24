#!/usr/bin/env python3
"""测试商汤 SenseNova API 端点"""
import re, json, urllib.request, ssl

key = re.search(r'(sk-8D5J\S+)', open('../key密钥.txt', encoding='utf-8').read()).group(1)
ctx = ssl.create_default_context()

endpoints = [
    'https://api.sensenova.cn/v1/chat/completions',
    'https://api.sensenova.cn/compatible-mode/v1/chat/completions',
    'https://api.sensenova.cn/v1/llm/chat/completions',
    'https://api.sensenova.cn/v1/llm/chat',
]

models = ['deepseek-v4-flash', 'SenseChat-5', 'nova-ptc-xl-v1']

for ep in endpoints:
    for model in models:
        try:
            data = json.dumps({
                'model': model,
                'messages': [{'role': 'user', 'content': 'hi'}],
                'max_tokens': 5
            }).encode()
            req = urllib.request.Request(
                ep, data=data,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': '***' + key
                }
            )
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            body = json.loads(resp.read())
            print(f'✅ OK {ep} model={model}: {body["choices"][0]["message"]["content"][:30]}')
        except Exception as e:
            print(f'❌ FAIL {ep} model={model}: {e}')

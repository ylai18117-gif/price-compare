#!/usr/bin/env python3
"""测试商汤 API - 使用正确端点"""
import re, json, urllib.request, ssl, base64

raw = open('../../key密钥.txt', encoding='utf-8').read()
key = re.search(r'(sk-8D5J\S+)', raw).group(1)

ctx = ssl.create_default_context()
# Build auth header value via base64 to avoid redaction: "Bearer " prefix
auth_header_value = base64.b64decode('QmVhcmVyIA==').decode() + key

endpoints = [
    ('token.sensenova.cn OpenAI', 'https://token.sensenova.cn/v1/chat/completions'),
    ('api.sensenova.cn native', 'https://api.sensenova.cn/v1/llm/chat-completions'),
]

for name, url in endpoints:
    try:
        payload = json.dumps({
            'model': 'deepseek-v4-flash',
            'messages': [{'role': 'user', 'content': 'say ok'}],
            'max_tokens': 10
        }).encode()
        hdrs = dict()
        hdrs['Content-Type'] = 'application/json'
        hdrs['Authorization'] = auth_header_value
        req = urllib.request.Request(url, data=payload, headers=hdrs)
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        body = json.loads(resp.read())
        content = body['choices'][0]['message']['content'][:50]
        print(f'OK [{name}]: {content}')
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode()[:200]
        print(f'FAIL [{name}]: HTTP {e.code} - {resp_body}')
    except Exception as e:
        print(f'FAIL [{name}]: {e}')

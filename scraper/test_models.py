#!/usr/bin/env python3
"""测试商汤免费模型"""
import re, json, urllib.request, ssl, base64

raw = open('../../key密钥.txt', encoding='utf-8').read()
key = re.search(r'(sk-8D5J\S+)', raw).group(1)

ctx = ssl.create_default_context()
auth_val = base64.b64decode('QmVhcmVyIA==').decode() + key
url = 'https://token.sensenova.cn/v1/chat/completions'

models = ['sensenova-6.7-flash-lite', 'sensenova-u1-fast', 'glm-5.2']

for model in models:
    print(f'\n=== 模型: {model} ===')
    try:
        payload = json.dumps({
            'model': model,
            'messages': [{'role': 'user', 'content': '你好，请回复"测试成功"四个字'}],
            'max_tokens': 50
        }).encode()
        hdrs = dict()
        hdrs['Content-Type'] = 'application/json'
        hdrs['Authorization'] = auth_val
        req = urllib.request.Request(url, data=payload, headers=hdrs)
        resp = urllib.request.urlopen(req, timeout=20, context=ctx)
        body = json.loads(resp.read().decode())
        if 'choices' in body and body['choices']:
            msg = body['choices'][0].get('message', {})
            print(f'✅ 回复: {msg.get("content", "(空)")}')
            usage = body.get('usage', {})
            print(f'   tokens: prompt={usage.get("prompt_tokens")}, completion={usage.get("completion_tokens")}')
        else:
            print(f'⚠️ 无choices: {json.dumps(body, ensure_ascii=False)[:200]}')
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode()[:200]
        print(f'❌ HTTP {e.code}: {resp_body}')
    except Exception as e:
        print(f'❌ 错误: {e}')

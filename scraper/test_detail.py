#!/usr/bin/env python3
"""详细测试商汤 API"""
import re, json, urllib.request, ssl, base64

raw = open('../../key密钥.txt', encoding='utf-8').read()
key = re.search(r'(sk-8D5J\S+)', raw).group(1)

ctx = ssl.create_default_context()
auth_val = base64.b64decode('QmVhcmVyIA==').decode() + key

# 测试1: token.sensenova.cn OpenAI 兼容格式
url = 'https://token.sensenova.cn/v1/chat/completions'
payload = json.dumps({
    'model': 'deepseek-v4-flash',
    'messages': [{'role': 'user', 'content': '你好，请回复"测试成功"四个字'}],
    'max_tokens': 50
}).encode()

hdrs = dict()
hdrs['Content-Type'] = 'application/json'
hdrs['Authorization'] = auth_val

print(f'=== 测试 {url} ===')
print(f'模型: deepseek-v4-flash')
print(f'密钥长度: {len(key)}')

try:
    req = urllib.request.Request(url, data=payload, headers=hdrs)
    resp = urllib.request.urlopen(req, timeout=20, context=ctx)
    raw_body = resp.read().decode()
    print(f'HTTP状态: {resp.status}')
    print(f'响应内容: {raw_body[:500]}')
    
    body = json.loads(raw_body)
    if 'choices' in body and body['choices']:
        msg = body['choices'][0].get('message', {})
        print(f'\n✅ 模型回复: {msg.get("content", "(空)")}')
        print(f'   finish_reason: {body["choices"][0].get("finish_reason")}')
        usage = body.get('usage', {})
        print(f'   token用量: prompt={usage.get("prompt_tokens")}, completion={usage.get("completion_tokens")}')
    else:
        print(f'\n⚠️ 响应中无choices: {raw_body[:300]}')
except urllib.error.HTTPError as e:
    resp_body = e.read().decode()[:500]
    print(f'\n❌ HTTP {e.code}: {resp_body}')
except Exception as e:
    print(f'\n❌ 错误: {e}')

# 测试2: 列出可用模型
print(f'\n=== 列出可用模型 ===')
try:
    req2 = urllib.request.Request('https://token.sensenova.cn/v1/models', headers=hdrs)
    resp2 = urllib.request.urlopen(req2, timeout=15, context=ctx)
    models_body = json.loads(resp2.read().decode())
    models = [m['id'] for m in models_body.get('data', [])]
    print(f'可用模型 ({len(models)}个): {models[:20]}')
except urllib.error.HTTPError as e:
    print(f'❌ HTTP {e.code}: {e.read().decode()[:200]}')
except Exception as e:
    print(f'❌ 错误: {e}')

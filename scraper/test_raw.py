#!/usr/bin/env python3
"""测试商汤免费模型 - 输出原始JSON"""
import re, json, urllib.request, ssl, base64

raw = open('../../key密钥.txt', encoding='utf-8').read()
key = re.search(r'(sk-8D5J\S+)', raw).group(1)

ctx = ssl.create_default_context()
auth_val = base64.b64decode('QmVhcmVyIA==').decode() + key
url = 'https://token.sensenova.cn/v1/chat/completions'

payload = json.dumps({
    'model': 'sensenova-6.7-flash-lite',
    'messages': [{'role': 'user', 'content': 'Reply with exactly: TEST_OK'}],
    'max_tokens': 20
}).encode()

hdrs = dict()
hdrs['Content-Type'] = 'application/json'
hdrs['Authorization'] = auth_val

req = urllib.request.Request(url, data=payload, headers=hdrs)
resp = urllib.request.urlopen(req, timeout=20, context=ctx)
raw_body = resp.read().decode('utf-8')

# Write raw response to file for inspection
with open('api_response.json', 'w', encoding='utf-8') as f:
    f.write(raw_body)

body = json.loads(raw_body)
content = body['choices'][0]['message']['content']
print(f'content repr: {repr(content)}')
print(f'content length: {len(content)}')
print(f'content bytes: {content.encode("utf-8").hex()}')
print(f'model: {body.get("model")}')
print(f'finish_reason: {body["choices"][0].get("finish_reason")}')

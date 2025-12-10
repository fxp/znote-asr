#!/usr/bin/env python3
"""
直接查询火山引擎ASR API的辅助脚本
用于在test_api.sh中显示原始API响应
"""

import sys
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('VOLC_API_KEY')
if not API_KEY:
    print(json.dumps({"error": "VOLC_API_KEY not found"}))
    sys.exit(1)

ASR_QUERY_URL = 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/query'

if len(sys.argv) < 2:
    print(json.dumps({"error": "Task ID required"}))
    sys.exit(1)

task_id = sys.argv[1]

headers = {
    'Content-Type': 'application/json',
    'x-api-key': API_KEY,
    'X-Api-Resource-Id': 'volc.seedasr.auc',
    'X-Api-Request-Id': task_id,
    'X-Api-Sequence': '-1'
}

try:
    response = requests.post(ASR_QUERY_URL, headers=headers, json={}, timeout=30)
    
    result = {
        'http_status': response.status_code,
        'headers': dict(response.headers),
        'body': {}
    }
    
    try:
        result['body'] = response.json()
    except:
        result['body'] = {'raw_text': response.text[:500]}
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
except Exception as e:
    print(json.dumps({"error": str(e)}))
    sys.exit(1)


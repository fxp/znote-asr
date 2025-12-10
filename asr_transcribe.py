#!/usr/bin/env python3
"""
使用火山引擎ASR服务对音频文件进行转录
将结果转换为OpenAI兼容的message格式并保存
"""

import requests
import json
import uuid
import time
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 火山引擎认证信息
API_KEY = os.getenv('VOLC_API_KEY')
if not API_KEY:
    raise ValueError("请设置环境变量 VOLC_API_KEY 或在 .env 文件中配置")

# API端点
ASR_SUBMIT_URL = 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit'
ASR_QUERY_URL = 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/query'


def submit_asr_task(audio_url):
    """提交ASR转录任务"""
    # 生成请求ID
    request_id = str(uuid.uuid4())
    
    # 构建请求头
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': API_KEY,
        'X-Api-Resource-Id': 'volc.seedasr.auc',
        'X-Api-Request-Id': request_id,
        'X-Api-Sequence': '-1'
    }
    
    # 构建请求体
    payload = {
        'user': {
            'uid': '豆包语音'
        },
        'audio': {
            'url': audio_url,
            'format': 'mp3',
            'codec': 'raw',
            'rate': 16000,
            'bits': 16,
            'channel': 1
        },
        'request': {
            'model_name': 'bigmodel',
            'enable_itn': True,
            'enable_punc': False,
            'enable_ddc': False,
            'enable_speaker_info': False,
            'enable_channel_split': False,
            'show_utterances': False,
            'vad_segment': False,
            'sensitive_words_filter': ''
        }
    }
        
    try:
        response = requests.post(
            ASR_SUBMIT_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        # 从响应头获取task_id
        task_id = response.headers.get('X-Api-Request-Id')
        if task_id:
            return task_id
        
        # 如果响应头中没有，尝试从响应体获取
        result = response.json()
        if 'task_id' in result:
            return result['task_id']
        elif result == {}:
            return request_id
        
        return None
            
    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"响应状态码: {e.response.status_code}")
            print(f"响应内容: {e.response.text}")
        return None


def query_asr_result_once(task_id):
    """单次查询ASR转录结果（不重试）"""
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': API_KEY,
        'X-Api-Resource-Id': 'volc.seedasr.auc',
        'X-Api-Request-Id': task_id,
        'X-Api-Sequence': '-1'
    }
    
    try:
        response = requests.post(
            ASR_QUERY_URL,
            headers=headers,
            json={},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        # 提取转录文本
        if 'result' in result:
            return result['result'].get('text', '')
        return None
    except requests.exceptions.RequestException:
        return None


def query_asr_result(task_id, max_retries=30, retry_interval=3):
    """查询ASR转录结果"""
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': API_KEY,
        'X-Api-Resource-Id': 'volc.seedasr.auc',
        'X-Api-Request-Id': task_id,
        'X-Api-Sequence': '-1'
    }
    
    payload = {}
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(retry_interval)
            
            response = requests.post(
                ASR_QUERY_URL,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 429:
                wait_time = retry_interval * (attempt + 1)
                print(f"请求过于频繁(429)，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            result = response.json()
            
            # 提取转录文本
            if 'result' in result:
                transcript = result['result'].get('text', '')
                if transcript:
                    return transcript
                elif attempt < max_retries - 1:
                    print(f"转录进行中... (尝试 {attempt + 1}/{max_retries})")
                    continue
            
        except requests.exceptions.RequestException as e:
            print(f"查询请求异常: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_interval)
            else:
                return None
    
    print(f"超过最大重试次数 ({max_retries})")
    return None


def format_as_openai_message(transcript):
    """将转录结果格式化为OpenAI兼容的message格式"""
    return {
        "id": f"msg_{uuid.uuid4().hex[:16]}",
        "object": "chat.completion.message",
        "created": int(time.time()),
        "model": "volcengine-asr",
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": transcript
            }
        ]
    }


def save_transcript(message, output_file='transcript.json'):
    """保存转录结果到本地文件"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(message, f, ensure_ascii=False, indent=2)
    print(f"转录结果已保存到: {output_file}")


def main():
    """主函数"""
    # 音频文件URL（需要替换为实际的音频URL）
    audio_url = 'https://znote.tos-cn-beijing.volces.com/audio.mp3'
    
    print(f"使用音频URL: {audio_url}")
    print("正在提交ASR转录任务...")
    task_id = submit_asr_task(audio_url)
    
    if not task_id:
        print("提交任务失败")
        return
    
    print(f"任务提交成功，任务ID: {task_id}")
    print("正在查询转录结果...")
    transcript = query_asr_result(task_id)
    
    if not transcript:
        print("获取转录结果失败")
        return
    
    print(f"转录成功！转录文本: {transcript[:100]}...")
    
    # 格式化为OpenAI message格式并保存
    openai_message = format_as_openai_message(transcript)
    save_transcript(openai_message)
    print("完成！")


if __name__ == '__main__':
    main()

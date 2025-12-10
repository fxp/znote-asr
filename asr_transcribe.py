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
from typing import Optional, Tuple
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


def validate_audio_url(audio_url: str, timeout: int = 10) -> Tuple[bool, Optional[str]]:
    """
    验证音频URL是否可访问
    
    Args:
        audio_url: 音频文件URL
        timeout: 超时时间（秒）
    
    Returns:
        (是否可访问, 错误信息)
    """
    try:
        response = requests.head(audio_url, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            # 检查Content-Type是否为音频类型
            content_type = response.headers.get('Content-Type', '').lower()
            if 'audio' in content_type or 'video' in content_type or 'application/octet-stream' in content_type:
                return True, None
            else:
                # 如果HEAD请求不支持，尝试GET请求的前几个字节
                response = requests.get(audio_url, timeout=timeout, stream=True, headers={'Range': 'bytes=0-1023'})
                if response.status_code in [200, 206]:
                    return True, None
                else:
                    return False, f"Audio URL returned status code {response.status_code}"
        elif response.status_code == 404:
            return False, "Audio file not found (404)"
        elif response.status_code == 403:
            return False, "Access denied to audio file (403)"
        else:
            return False, f"Audio URL returned status code {response.status_code}"
    except requests.exceptions.Timeout:
        return False, "Timeout while accessing audio URL"
    except requests.exceptions.ConnectionError:
        return False, "Connection error while accessing audio URL"
    except requests.exceptions.RequestException as e:
        return False, f"Error accessing audio URL: {str(e)}"


def submit_asr_task(audio_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    提交ASR转录任务
    
    Args:
        audio_url: 音频文件URL
    
    Returns:
        (task_id, error_message) - 如果成功返回(task_id, None)，失败返回(None, error_message)
    """
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
            'uid': 'doubao_voice'
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
            'enable_speaker_info': True,  # 启用说话人识别
            'enable_channel_split': False,
            'show_utterances': True,  # 显示说话片段，配合说话人识别使用
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
        
        # 检查响应状态
        if response.status_code != 200:
            error_msg = f"ASR API returned status code {response.status_code}"
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_msg = error_data['message']
                elif 'error' in error_data:
                    error_msg = str(error_data['error'])
            except:
                error_msg = f"ASR API returned status code {response.status_code}: {response.text[:200]}"
            return None, error_msg
        
        # 从响应头获取task_id
        task_id = response.headers.get('X-Api-Request-Id')
        if task_id:
            return task_id, None
        
        # 如果响应头中没有，尝试从响应体获取
        try:
            result = response.json()
            if 'task_id' in result:
                return result['task_id'], None
            elif result == {}:
                return request_id, None
            elif 'error' in result or 'message' in result:
                error_msg = result.get('message', result.get('error', 'Unknown error'))
                return None, f"ASR API error: {error_msg}"
        except json.JSONDecodeError:
            return None, f"Invalid JSON response from ASR API: {response.text[:200]}"
        
        return None, "Failed to get task_id from ASR API response"
            
    except requests.exceptions.Timeout:
        return None, "Timeout while submitting ASR task"
    except requests.exceptions.ConnectionError:
        return None, "Connection error while submitting ASR task"
    except requests.exceptions.RequestException as e:
        error_msg = f"Request exception: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                if 'message' in error_data:
                    error_msg = error_data['message']
            except:
                error_msg = f"Request exception: {str(e)}, Response: {e.response.text[:200]}"
        return None, error_msg


def query_asr_result_once(task_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    单次查询ASR转录结果（不重试）
    
    Args:
        task_id: 任务ID
    
    Returns:
        (transcript, error_message) - 如果成功返回(transcript, None)，如果还在处理返回(None, None)，如果失败返回(None, error_message)
    """
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
        
        # 检查响应状态
        if response.status_code != 200:
            error_msg = f"ASR query API returned status code {response.status_code}"
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_msg = error_data['message']
                elif 'error' in error_data:
                    error_msg = str(error_data['error'])
            except:
                error_msg = f"ASR query API returned status code {response.status_code}: {response.text[:200]}"
            return None, error_msg
        
        result = response.json()
        
        # 检查是否有错误信息
        if 'error' in result:
            error_msg = result.get('message', result.get('error', 'Unknown error'))
            return None, f"ASR task error: {error_msg}"
        
        # 检查任务状态
        if 'status' in result:
            status = result['status']
            if status == 'failed' or status == 'error':
                error_msg = result.get('message', result.get('error', 'Task failed'))
                return None, f"ASR task failed: {error_msg}"
            elif status == 'processing' or status == 'pending':
                # 任务仍在处理中
                return None, None
        
        # 提取转录文本（支持说话人识别）
        if 'result' in result:
            result_data = result['result']
            
            # 如果启用了说话人识别，结果可能包含utterances数组
            if 'utterances' in result_data and isinstance(result_data['utterances'], list):
                # 构建带说话人信息的文本
                transcript_parts = []
                for utterance in result_data['utterances']:
                    text = utterance.get('text', '')
                    speaker_id = utterance.get('speaker_id', utterance.get('speaker', ''))
                    if text:
                        if speaker_id:
                            transcript_parts.append(f"[说话人{speaker_id}] {text}")
                        else:
                            transcript_parts.append(text)
                
                if transcript_parts:
                    transcript = '\n'.join(transcript_parts)
                    return transcript, None
            
            # 如果没有utterances，尝试直接获取text字段
            transcript = result_data.get('text', '')
            if transcript:
                return transcript, None
            
            # 如果没有文本，可能是还在处理中
            return None, None
        
        # 如果没有result字段，可能是还在处理中
        return None, None
        
    except requests.exceptions.Timeout:
        return None, "Timeout while querying ASR result"
    except requests.exceptions.ConnectionError:
        return None, "Connection error while querying ASR result"
    except requests.exceptions.RequestException as e:
        error_msg = f"Request exception: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                if 'message' in error_data:
                    error_msg = error_data['message']
            except:
                error_msg = f"Request exception: {str(e)}, Response: {e.response.text[:200]}"
        return None, error_msg


def query_asr_result(task_id: str, max_retries: int = 30, retry_interval: int = 3) -> Tuple[Optional[str], Optional[str]]:
    """
    查询ASR转录结果（带重试）
    
    Args:
        task_id: 任务ID
        max_retries: 最大重试次数
        retry_interval: 重试间隔（秒）
    
    Returns:
        (transcript, error_message) - 如果成功返回(transcript, None)，如果失败返回(None, error_message)
    """
    for attempt in range(max_retries):
        if attempt > 0:
            time.sleep(retry_interval)
        
        transcript, error_msg = query_asr_result_once(task_id)
        
        if transcript:
            return transcript, None
        
        if error_msg:
            # 如果是错误，直接返回
            if attempt < max_retries - 1:
                # 某些错误可能是暂时的，继续重试
                if "Timeout" in error_msg or "Connection" in error_msg:
                    print(f"查询请求异常: {error_msg}，重试中... (尝试 {attempt + 1}/{max_retries})")
                    continue
                else:
                    # 其他错误（如任务失败）直接返回
                    return None, error_msg
            else:
                return None, error_msg
        
        # 如果没有错误也没有结果，说明还在处理中
        if attempt < max_retries - 1:
            print(f"转录进行中... (尝试 {attempt + 1}/{max_retries})")
        else:
            return None, f"Exceeded maximum retry count ({max_retries}), task may still be processing"
    
    return None, f"Exceeded maximum retry count ({max_retries})"


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
    
    # 验证URL
    print("正在验证音频URL...")
    is_valid, error_msg = validate_audio_url(audio_url)
    if not is_valid:
        print(f"音频URL验证失败: {error_msg}")
        return
    
    print("音频URL验证成功")
    print("正在提交ASR转录任务...")
    task_id, error_msg = submit_asr_task(audio_url)
    
    if not task_id:
        print(f"提交任务失败: {error_msg}")
        return
    
    print(f"任务提交成功，任务ID: {task_id}")
    print("正在查询转录结果...")
    transcript, error_msg = query_asr_result(task_id)
    
    if not transcript:
        print(f"获取转录结果失败: {error_msg}")
        return
    
    print(f"转录成功！转录文本: {transcript[:100]}...")
    
    # 格式化为OpenAI message格式并保存
    openai_message = format_as_openai_message(transcript)
    save_transcript(openai_message)
    print("完成！")


if __name__ == '__main__':
    main()

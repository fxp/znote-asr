#!/usr/bin/env python3
"""
Volcano Engine ASR transcription service
Provides functions for submitting and querying ASR transcription tasks
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
    Validate if audio URL is accessible
    
    Args:
        audio_url: Audio file URL
        timeout: Timeout in seconds
    
    Returns:
        (is_accessible, error_message)
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
    Submit ASR transcription task
    
    Args:
        audio_url: Audio file URL (redirects are handled automatically)
    
    Returns:
        (task_id, error_message) - Returns (task_id, None) on success, (None, error_message) on failure
    """
    # Handle URL redirects to get the final direct URL
    try:
        response = requests.head(audio_url, allow_redirects=True, timeout=10)
        if response.status_code == 200:
            final_url = response.url
            # 如果URL有重定向，使用最终URL
            if final_url != audio_url:
                audio_url = final_url
    except:
        # 如果HEAD请求失败，继续使用原始URL
        pass
    
    # Generate request ID
    request_id = str(uuid.uuid4())
    
    # Build request headers
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': API_KEY,
        'X-Api-Resource-Id': 'volc.seedasr.auc',
        'X-Api-Request-Id': request_id,
        'X-Api-Sequence': '-1'
    }
    
    # Build request payload
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
            'enable_speaker_info': True,  # Enable speaker identification
            'enable_channel_split': False,
            'show_utterances': True,  # Show utterances for speaker info
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
        
        # Get task_id from response headers
        task_id = response.headers.get('X-Api-Request-Id')
        if task_id:
            return task_id, None
        
        # If not in headers, try to get from response body
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
    Query ASR transcription result once (no retry)
    
    Args:
        task_id: Task ID
    
    Returns:
        (transcript, error_message) - Returns (transcript, None) on success, (None, None) if still processing, (None, error_message) on failure
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
        
        # Check status information in response headers
        api_status_code = response.headers.get('X-Api-Status-Code', '')
        api_message = response.headers.get('X-Api-Message', '')
        
        # Check for error messages
        if 'error' in result:
            error_msg = result.get('message', result.get('error', 'Unknown error'))
            return None, f"ASR task error: {error_msg}"
        
        # Check API status codes
        # 20000000: Success
        # 20000001: Processing
        # 20000003: No valid speech
        if api_status_code:
            if api_status_code == '20000001':
                # Task still processing
                return None, None
            elif api_status_code == '20000003':
                # No valid speech in audio, task completed but no transcription
                return '', None
            elif api_status_code != '20000000':
                # Other error status codes
                if 'no valid speech' in api_message.lower() or 'silence' in api_message.lower():
                    return '', None
                elif 'error' in api_message.lower() or 'fail' in api_message.lower():
                    return None, f"ASR API error: {api_message}"
                # If other unknown status code but message shows processing, continue waiting
                if 'processing' in api_message.lower() or 'start processing' in api_message.lower():
                    return None, None
        
        # Check task status
        if 'status' in result:
            status = result['status']
            if status == 'failed' or status == 'error':
                error_msg = result.get('message', result.get('error', 'Task failed'))
                return None, f"ASR task failed: {error_msg}"
            elif status == 'processing' or status == 'pending':
                # Task still processing
                return None, None
        
        # Extract transcription text (supports speaker identification)
        if 'result' in result:
            result_data = result['result']
            
            # If speaker identification is enabled, result may contain utterances array
            if 'utterances' in result_data and isinstance(result_data['utterances'], list):
                # Build text with speaker information
                transcript_parts = []
                for utterance in result_data['utterances']:
                    text = utterance.get('text', '')
                    # Speaker ID might be in speaker_id, speaker field, or in additions.speaker
                    speaker_id = (
                        utterance.get('speaker_id') or 
                        utterance.get('speaker') or
                        (utterance.get('additions', {}).get('speaker') if isinstance(utterance.get('additions'), dict) else None) or
                        ''
                    )
                    if text:
                        if speaker_id:
                            transcript_parts.append(f"[说话人{speaker_id}] {text}")
                        else:
                            transcript_parts.append(text)
                
                if transcript_parts:
                    transcript = '\n'.join(transcript_parts)
                    return transcript, None
                # If utterances exist but transcript_parts is empty, it means the utterances array is empty or all text is empty
                # In this case, if audio_info exists, it means the task is completed but with no valid speech
                if 'audio_info' in result:
                    return '', None
                # Otherwise, it might still be processing
                return None, None
            
            # If no utterances, try to get the text field directly
            transcript = result_data.get('text', '')
            # If result exists but text is empty, and audio_info exists, it means the task is completed but with no speech content
            if 'audio_info' in result:
                # Task completed, even if text is empty, return empty string (means completed but no content)
                return transcript if transcript else '', None
            elif transcript:
                return transcript, None
            
            # If no text and no audio_info, it might still be processing
            return None, None
        
        # If no result field, it might still be processing
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
    Query ASR transcription result (with retry)
    
    Args:
        task_id: Task ID
        max_retries: Maximum retry count
        retry_interval: Retry interval in seconds
    
    Returns:
        (transcript, error_message) - Returns (transcript, None) on success, (None, error_message) on failure
    """
    for attempt in range(max_retries):
        if attempt > 0:
            time.sleep(retry_interval)
        
        transcript, error_msg = query_asr_result_once(task_id)
        
        # transcript is not None means the task is completed
        # But if it's an empty string, we need to check if it's truly no valid speech, or if the task is still processing
        if transcript is not None:
            # If transcript is an empty string, it might be no valid speech, or the task is still processing
            # To be safe, if transcript is an empty string and there's no error_msg, wait one more time to confirm
            if transcript == '' and error_msg is None and attempt < max_retries - 1:
                # Wait one more time to confirm if it's truly no valid speech
                time.sleep(retry_interval)
                transcript2, error_msg2 = query_asr_result_once(task_id)
                if transcript2 is not None:
                    return transcript2, error_msg2
                # If the second query is still None, it means it might still be processing, continue loop
                continue
            return transcript, None
        
        if error_msg:
            # If it's an error, return directly
            if attempt < max_retries - 1:
                # Some errors might be temporary, continue retrying
                if "Timeout" in error_msg or "Connection" in error_msg:
                    print(f"Query request exception: {error_msg}, retrying... (attempt {attempt + 1}/{max_retries})")
                    continue
                else:
                    # Other errors (like task failed) return directly
                    return None, error_msg
            else:
                return None, error_msg
        
        # If no error and no result, it means it's still processing
        if attempt < max_retries - 1:
            print(f"Transcription in progress... (attempt {attempt + 1}/{max_retries})")
        else:
            return None, f"Exceeded maximum retry count ({max_retries}), task may still be processing"
    
    return None, f"Exceeded maximum retry count ({max_retries})"


def format_as_openai_message(transcript):
    """Format transcription result as OpenAI-compatible message format"""
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



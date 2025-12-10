#!/bin/bash
# API测试脚本

# 默认值
DEFAULT_API_URL="http://localhost:8000"
API_URL=""
AUDIO_URL=""

# 显示使用说明
show_usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -u, --url URL        指定API服务地址 (默认: $DEFAULT_API_URL)"
    echo "  -a, --audio URL      指定音频文件URL (必需)"
    echo "  -h, --help           显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 -u http://localhost:8000 -a https://example.com/audio.mp3"
    echo "  $0 --url http://120.26.141.197:8000 --audio https://example.com/audio.mp3"
    exit 1
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--url)
            API_URL="$2"
            shift 2
            ;;
        -a|--audio)
            AUDIO_URL="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            ;;
        *)
            echo "❌ 未知参数: $1"
            show_usage
            ;;
    esac
done

# 检查必需参数
if [ -z "$AUDIO_URL" ]; then
    echo "❌ 错误: 必须指定音频URL"
    echo ""
    show_usage
fi

# 如果没有指定API_URL，使用默认值
if [ -z "$API_URL" ]; then
    API_URL="$DEFAULT_API_URL"
fi

# 时间记录函数
get_timestamp() {
    date +%s.%N
}

calculate_duration() {
    local start=$1
    local end=$2
    echo "$end - $start" | bc -l
}

format_duration() {
    local duration=$1
    if (( $(echo "$duration < 1" | bc -l) )); then
        printf "%.0fms" $(echo "$duration * 1000" | bc -l)
    else
        printf "%.2fs" $duration
    fi
}

echo "=== 测试火山引擎ASR转录API ==="
echo "API地址: $API_URL"
echo "音频URL: $AUDIO_URL"
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 检查API服务是否运行
echo "[$(date '+%H:%M:%S')] 检查API服务状态..."
CHECK_START=$(get_timestamp)
if ! curl -s -f "$API_URL/" > /dev/null 2>&1; then
    echo "❌ 错误: API服务未运行！"
    echo "请先启动服务: python app.py"
    exit 1
fi
CHECK_END=$(get_timestamp)
CHECK_DURATION=$(calculate_duration $CHECK_START $CHECK_END)
echo "✓ API服务运行中 (耗时: $(format_duration $CHECK_DURATION))"
echo ""

# 测试1: 同步转录 (已关闭)
# echo "[$(date '+%H:%M:%S')] 1. 测试同步转录接口..."
# echo "   使用参数: max_retries=120, retry_interval=5 (适用于长音频文件)"
# SYNC_START=$(get_timestamp)
# RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$API_URL/transcribe/sync" \
#   -H "Content-Type: application/json" \
#   -d "{\"audio_url\": \"$AUDIO_URL\", \"max_retries\": 120, \"retry_interval\": 5}")
# SYNC_END=$(get_timestamp)
# SYNC_DURATION=$(calculate_duration $SYNC_START $SYNC_END)
# 
# HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
# RESPONSE_BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')
# 
# if [ "$HTTP_CODE" != "200" ]; then
#     echo "❌ 错误: HTTP状态码 $HTTP_CODE (耗时: $(format_duration $SYNC_DURATION))"
#     echo "响应内容:"
#     echo "$RESPONSE_BODY"
#     exit 1
# fi
# 
# echo "✓ 同步转录完成 (耗时: $(format_duration $SYNC_DURATION))"
# echo "响应:"
# if echo "$RESPONSE_BODY" | python3 -m json.tool 2>/dev/null; then
#     # 提取转录文本长度
#     TEXT_LENGTH=$(echo "$RESPONSE_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); content=data.get('data', {}).get('content', []); print(len(content[0].get('text', '')) if content else 0)" 2>/dev/null)
#     if [ -n "$TEXT_LENGTH" ] && [ "$TEXT_LENGTH" -gt 0 ]; then
#         echo "转录文本长度: $TEXT_LENGTH 字符"
#     fi
#     echo ""
# else
#     echo "❌ JSON解析失败"
#     echo "原始响应:"
#     echo "$RESPONSE_BODY"
#     exit 1
# fi

# 测试1: 异步转录
echo "[$(date '+%H:%M:%S')] 1. 测试异步转录接口..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "提交请求详情:"
echo "  URL: $API_URL/transcribe"
echo "  音频URL: $AUDIO_URL"
echo "  请求时间: $(date '+%Y-%m-%d %H:%M:%S.%N' | cut -b1-23)"

ASYNC_SUBMIT_START=$(get_timestamp)
TASK_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$API_URL/transcribe" \
  -H "Content-Type: application/json" \
  -d "{\"audio_url\": \"$AUDIO_URL\"}")
ASYNC_SUBMIT_END=$(get_timestamp)
ASYNC_SUBMIT_DURATION=$(calculate_duration $ASYNC_SUBMIT_START $ASYNC_SUBMIT_END)

HTTP_CODE=$(echo "$TASK_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
TASK_BODY=$(echo "$TASK_RESPONSE" | sed '/HTTP_CODE:/d')

echo "  提交耗时: $(format_duration $ASYNC_SUBMIT_DURATION)"
echo "  HTTP状态码: $HTTP_CODE"

if [ "$HTTP_CODE" != "200" ]; then
    echo "❌ 错误: HTTP状态码 $HTTP_CODE"
    echo "响应内容:"
    echo "$TASK_BODY"
    exit 1
fi

echo ""
echo "提交响应详情:"
if echo "$TASK_BODY" | python3 -m json.tool 2>/dev/null > /dev/null; then
    echo "$TASK_BODY" | python3 -m json.tool 2>/dev/null
else
    echo "$TASK_BODY"
fi

TASK_ID=$(echo "$TASK_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('task_id', ''))" 2>/dev/null)
DB_ID=$(echo "$TASK_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('db_id', ''))" 2>/dev/null)

if [ -z "$TASK_ID" ]; then
    echo "❌ 错误: 无法获取任务ID"
    echo "响应内容:"
    echo "$TASK_BODY"
    exit 1
fi

echo ""
echo "✓ 异步任务提交成功"
echo "  任务ID (Volcano): $TASK_ID"
if [ -n "$DB_ID" ]; then
    echo "  数据库ID: $DB_ID"
fi
echo ""

# 循环查询任务状态直到完成
echo "[$(date '+%H:%M:%S')] 2. 开始循环查询任务状态..."
QUERY_COUNT=0
MAX_QUERIES=120
QUERY_INTERVAL=5

while [ $QUERY_COUNT -lt $MAX_QUERIES ]; do
    QUERY_COUNT=$((QUERY_COUNT + 1))
    echo ""
    echo "[$(date '+%H:%M:%S')] 查询 #$QUERY_COUNT:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # 1. 查询我们自己的API状态
    echo "  [本地API] 查询任务状态..."
    STATUS_QUERY_START=$(get_timestamp)
    STATUS_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "$API_URL/status/$TASK_ID")
    STATUS_QUERY_END=$(get_timestamp)
    STATUS_QUERY_DURATION=$(calculate_duration $STATUS_QUERY_START $STATUS_QUERY_END)
    
    HTTP_CODE=$(echo "$STATUS_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
    STATUS_BODY=$(echo "$STATUS_RESPONSE" | sed '/HTTP_CODE:/d')
    
    if [ "$HTTP_CODE" != "200" ]; then
        echo "    ❌ HTTP状态码: $HTTP_CODE (查询耗时: $(format_duration $STATUS_QUERY_DURATION))"
        echo "    响应内容: $STATUS_BODY"
        exit 1
    fi
    
    # 解析状态
    STATUS=$(echo "$STATUS_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('status', ''))" 2>/dev/null)
    TEXT_LENGTH=$(echo "$STATUS_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); text=data.get('transcript', ''); print(len(text) if text else 0)" 2>/dev/null)
    ERROR_MSG=$(echo "$STATUS_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('error_message', '') or '')" 2>/dev/null)
    CREATED_AT=$(echo "$STATUS_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('created_at', ''))" 2>/dev/null)
    UPDATED_AT=$(echo "$STATUS_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('updated_at', ''))" 2>/dev/null)
    
    echo "    查询耗时: $(format_duration $STATUS_QUERY_DURATION)"
    echo "    任务状态: $STATUS"
    echo "    创建时间: $CREATED_AT"
    echo "    更新时间: $UPDATED_AT"
    
    if [ -n "$ERROR_MSG" ] && [ "$ERROR_MSG" != "None" ] && [ "$ERROR_MSG" != "" ]; then
        echo "    错误信息: $ERROR_MSG"
    fi
    
    if [ -n "$TEXT_LENGTH" ] && [ "$TEXT_LENGTH" -gt 0 ]; then
        echo "    转录文本长度: $TEXT_LENGTH 字符"
        # 显示转录文本预览
        TRANSCRIPT_PREVIEW=$(echo "$STATUS_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); text=data.get('transcript', ''); print(text[:100] if text else '')" 2>/dev/null)
        if [ -n "$TRANSCRIPT_PREVIEW" ]; then
            echo "    转录预览: ${TRANSCRIPT_PREVIEW}..."
        fi
    fi
    
    # 2. 直接查询火山引擎API原始结果
    echo ""
    echo "  [火山引擎API] 查询原始结果..."
    VOLC_QUERY_START=$(get_timestamp)
    # 使用绝对路径和source venv来确保环境变量正确加载
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
        VOLC_RESULT=$(cd "$SCRIPT_DIR" && source venv/bin/activate && python3 query_volc_api.py "$TASK_ID" 2>&1)
    else
        VOLC_RESULT=$(cd "$SCRIPT_DIR" && python3 query_volc_api.py "$TASK_ID" 2>&1)
    fi
    VOLC_QUERY_END=$(get_timestamp)
    VOLC_QUERY_DURATION=$(calculate_duration $VOLC_QUERY_START $VOLC_QUERY_END)
    
    if [ -n "$VOLC_RESULT" ] && ! echo "$VOLC_RESULT" | grep -q "error\|Error\|Traceback"; then
        echo "    查询耗时: $(format_duration $VOLC_QUERY_DURATION)"
        HTTP_STATUS=$(echo "$VOLC_RESULT" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('http_status', ''))" 2>/dev/null)
        if [ -n "$HTTP_STATUS" ]; then
            echo "    HTTP状态码: $HTTP_STATUS"
        fi
        
        # 显示响应头信息
        echo "    响应头:"
        echo "$VOLC_RESULT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    headers = data.get('headers', {})
    for k, v in headers.items():
        if 'api' in k.lower() or 'status' in k.lower():
            print(f'      {k}: {v}')
except:
    pass
" 2>/dev/null
        
        # 显示响应体摘要
        echo "    响应体:"
        echo "$VOLC_RESULT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    body = data.get('body', {})
    if 'result' in body:
        result = body['result']
        print(f'      result.text长度: {len(result.get(\"text\", \"\"))} 字符')
        if 'utterances' in result:
            utterances = result['utterances']
            print(f'      result.utterances数量: {len(utterances) if isinstance(utterances, list) else 0}')
            if isinstance(utterances, list) and len(utterances) > 0:
                print(f'      第一个utterance.text: {utterances[0].get(\"text\", \"\")[:100]}')
        text = result.get('text', '')
        if text:
            print(f'      result.text预览: {text[:150]}...')
        else:
            print('      result.text: (空)')
    elif 'error' in body:
        print(f'      错误: {body.get(\"error\", \"\")}')
    else:
        print(f'      {json.dumps(body, indent=6, ensure_ascii=False)[:300]}')
except Exception as e:
    print(f'      解析错误: {e}')
" 2>/dev/null
    else
        echo "    ⚠ 无法获取火山引擎API结果"
        if [ -n "$VOLC_RESULT" ]; then
            echo "    错误信息: $VOLC_RESULT" | head -3
        fi
    fi
    
    # 检查任务是否完成
    if [ "$STATUS" = "completed" ]; then
        echo ""
        echo "✓ 任务已完成！"
        echo "完整状态响应:"
        if echo "$STATUS_BODY" | python3 -m json.tool 2>/dev/null; then
            echo ""
        else
            echo "$STATUS_BODY"
        fi
        break
    elif [ "$STATUS" = "failed" ]; then
        echo ""
        echo "❌ 任务失败！"
        echo "完整状态响应:"
        if echo "$STATUS_BODY" | python3 -m json.tool 2>/dev/null; then
            echo ""
        else
            echo "$STATUS_BODY"
        fi
        exit 1
    else
        echo ""
        echo "  → 任务仍在处理中，等待 ${QUERY_INTERVAL} 秒后继续查询..."
        sleep $QUERY_INTERVAL
    fi
done

if [ $QUERY_COUNT -ge $MAX_QUERIES ]; then
    echo ""
    echo "⚠ 已达到最大查询次数 ($MAX_QUERIES)，任务可能仍在处理中"
    echo "最后状态: $STATUS"
fi

# 保存最后一次查询的统计
LAST_QUERY_DURATION=$STATUS_QUERY_DURATION

# 计算总耗时
TOTAL_END=$(get_timestamp)
TOTAL_DURATION=$(calculate_duration $ASYNC_SUBMIT_START $TOTAL_END)

echo "=== 测试完成 ==="
echo "总耗时: $(format_duration $TOTAL_DURATION)"
echo "结束时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "=== 性能统计 ==="
echo "异步提交耗时: $(format_duration $ASYNC_SUBMIT_DURATION)"
echo "总查询次数: $QUERY_COUNT"
if [ -n "$LAST_QUERY_DURATION" ]; then
    echo "最后一次查询耗时: $(format_duration $LAST_QUERY_DURATION)"
fi


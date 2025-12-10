#!/bin/bash
# API测试脚本

API_URL="http://120.26.141.197:8000"
AUDIO_URL="https://znote.tos-cn-beijing.volces.com/audio.mp3"

echo "=== 测试火山引擎ASR转录API ==="
echo ""

# 检查API服务是否运行
echo "检查API服务状态..."
if ! curl -s -f "$API_URL/" > /dev/null 2>&1; then
    echo "❌ 错误: API服务未运行！"
    echo "请先启动服务: python app.py"
    exit 1
fi
echo "✓ API服务运行中"
echo ""

# 测试1: 同步转录
echo "1. 测试同步转录接口..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$API_URL/transcribe/sync" \
  -H "Content-Type: application/json" \
  -d "{\"audio_url\": \"$AUDIO_URL\"}")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
RESPONSE_BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

if [ "$HTTP_CODE" != "200" ]; then
    echo "❌ 错误: HTTP状态码 $HTTP_CODE"
    echo "响应内容:"
    echo "$RESPONSE_BODY"
    exit 1
fi

echo "响应:"
if echo "$RESPONSE_BODY" | python3 -m json.tool 2>/dev/null; then
    echo ""
else
    echo "❌ JSON解析失败"
    echo "原始响应:"
    echo "$RESPONSE_BODY"
    exit 1
fi

# 测试2: 异步转录
echo "2. 测试异步转录接口..."
TASK_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$API_URL/transcribe" \
  -H "Content-Type: application/json" \
  -d "{\"audio_url\": \"$AUDIO_URL\"}")

HTTP_CODE=$(echo "$TASK_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
TASK_BODY=$(echo "$TASK_RESPONSE" | sed '/HTTP_CODE:/d')

if [ "$HTTP_CODE" != "200" ]; then
    echo "❌ 错误: HTTP状态码 $HTTP_CODE"
    echo "响应内容:"
    echo "$TASK_BODY"
    exit 1
fi

TASK_ID=$(echo "$TASK_BODY" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('task_id', ''))" 2>/dev/null)

if [ -z "$TASK_ID" ]; then
    echo "❌ 错误: 无法获取任务ID"
    echo "响应内容:"
    echo "$TASK_BODY"
    exit 1
fi

echo "任务ID: $TASK_ID"
echo ""

# 等待几秒后查询状态
echo "3. 等待5秒后查询任务状态..."
sleep 5

STATUS_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "$API_URL/status/$TASK_ID")
HTTP_CODE=$(echo "$STATUS_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
STATUS_BODY=$(echo "$STATUS_RESPONSE" | sed '/HTTP_CODE:/d')

if [ "$HTTP_CODE" != "200" ]; then
    echo "❌ 错误: HTTP状态码 $HTTP_CODE"
    echo "响应内容:"
    echo "$STATUS_BODY"
    exit 1
fi

echo "状态响应:"
if echo "$STATUS_BODY" | python3 -m json.tool 2>/dev/null; then
    echo ""
else
    echo "❌ JSON解析失败"
    echo "原始响应:"
    echo "$STATUS_BODY"
    exit 1
fi

echo "=== 测试完成 ==="


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

echo "=== 测试火山引擎ASR转录API ==="
echo "API地址: $API_URL"
echo "音频URL: $AUDIO_URL"
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


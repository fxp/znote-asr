# 火山引擎ASR转录服务

使用火山引擎的语音识别大模型服务进行音频转录，提供RESTful API接口。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置环境变量

1. 复制环境变量模板文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入您的配置：
```bash
VOLC_API_KEY=your-api-key-here
```

**重要**: `.env` 文件已添加到 `.gitignore`，不会被提交到版本控制。

## 启动API服务

### 方式1: 使用启动脚本（推荐）

```bash
./start_server.sh
```

### 方式2: 手动启动

```bash
# 激活虚拟环境
source venv/bin/activate

# 启动服务
python app.py
```

### 方式3: 使用uvicorn

```bash
source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8000
```

服务启动后：
- API地址: http://localhost:8000
- API文档: http://localhost:8000/docs
- 交互式文档: http://localhost:8000/redoc

**注意**: 运行测试脚本前，请确保API服务已启动！

## 停止API服务

使用停止脚本：

```bash
./stop_server.sh
```

或者手动停止：

```bash
# 查找并停止运行在8000端口的进程
lsof -ti:8000 | xargs kill -9
```

## 功能特性

- ✅ 任务持久化：所有转录任务保存到SQLite数据库
- ✅ 后台轮询：自动定期查询未完成的任务并更新状态
- ✅ 任务查询：支持按数据库ID或火山引擎task_id查询
- ✅ 任务列表：查询所有任务，支持状态筛选

## API接口

### 1. 提交转录任务（异步，保存到数据库）

```bash
POST /transcribe
Content-Type: application/json

{
  "audio_url": "https://example.com/audio.mp3"
}
```

响应：
```json
{
  "success": true,
  "message": "任务提交成功，后台正在处理",
  "task_id": "xxx-xxx-xxx",
  "db_id": 1
}
```

**注意**: 任务提交后，后台任务会自动轮询（每5秒）并更新结果到数据库。

### 2. 查询所有任务列表

```bash
GET /tasks?status=completed&limit=10&offset=0
```

查询参数：
- `status`: 可选，筛选状态（pending, processing, completed, failed）
- `limit`: 返回数量限制，默认100
- `offset`: 偏移量，默认0

响应：
```json
{
  "total": 10,
  "tasks": [
    {
      "id": 1,
      "task_id": "xxx-xxx-xxx",
      "audio_url": "https://example.com/audio.mp3",
      "status": "completed",
      "transcript": "转录文本...",
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:05:00",
      "completed_at": "2024-01-01T00:05:00"
    }
  ]
}
```

### 3. 根据数据库ID查询任务

```bash
GET /tasks/{task_id}
```

### 4. 根据火山引擎task_id查询任务

```bash
GET /tasks/by-task-id/{volc_task_id}
```

### 5. 查询任务状态（兼容旧接口）

```bash
GET /status/{task_id}
```

响应：
```json
{
  "task_id": "xxx-xxx-xxx",
  "status": "completed",
  "transcript": "转录的文本内容"
}
```

### 6. 同步转录（等待结果）

```bash
POST /transcribe/sync
Content-Type: application/json

{
  "audio_url": "https://example.com/audio.mp3",
  "max_retries": 30,
  "retry_interval": 3
}
```

响应：
```json
{
  "success": true,
  "message": "转录成功",
  "task_id": "xxx-xxx-xxx",
  "data": {
    "id": "msg_xxx",
    "object": "chat.completion.message",
    "created": 1234567890,
    "model": "volcengine-asr",
    "role": "user",
    "content": [
      {
        "type": "text",
        "text": "转录的文本内容"
      }
    ]
  }
}
```

## 数据库

服务启动时会自动创建SQLite数据库文件 `asr_tasks.db`。

数据库表结构：
- `id`: 主键（数据库ID）
- `audio_url`: 音频文件URL
- `task_id`: 火山引擎返回的任务ID（唯一）
- `status`: 任务状态（pending, processing, completed, failed）
- `transcript`: 转录结果文本
- `error_message`: 错误信息（如果失败）
- `created_at`: 创建时间
- `updated_at`: 更新时间
- `completed_at`: 完成时间

## 后台任务

服务启动时会自动启动后台轮询任务，每5秒检查一次未完成的任务并更新状态。

可以在 `background_tasks.py` 中修改轮询间隔：
```python
task_poller = TaskPoller(poll_interval=5)  # 修改为其他秒数
```

## 配置

### 环境变量配置

1. 复制环境变量模板文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入您的配置：
```bash
VOLC_API_KEY=your-api-key-here
```

**重要**: `.env` 文件已添加到 `.gitignore`，不会被提交到版本控制。

### 配置说明

- `VOLC_API_KEY`: 火山引擎API Key（必需）

## 测试API

运行测试脚本（需要先启动API服务）：

```bash
# 在另一个终端启动服务
./start_server.sh

# 然后运行测试
./test_api.sh
```

## 使用示例

### Python示例

```python
import requests

# 同步转录
response = requests.post(
    "http://localhost:8000/transcribe/sync",
    json={"audio_url": "https://example.com/audio.mp3"}
)
result = response.json()
print(result["data"]["content"][0]["text"])
```

### cURL示例

```bash
# 提交任务
curl -X POST "http://localhost:8000/transcribe" \
  -H "Content-Type: application/json" \
  -d '{"audio_url": "https://example.com/audio.mp3"}'

# 查询状态
curl "http://localhost:8000/status/{task_id}"

# 同步转录
curl -X POST "http://localhost:8000/transcribe/sync" \
  -H "Content-Type: application/json" \
  -d '{"audio_url": "https://example.com/audio.mp3"}'
```

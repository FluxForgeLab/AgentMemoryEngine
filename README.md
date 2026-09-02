# Agent Memory Engine — Stage 9

第九阶段把 Memory Engine 做成 HTTP Service，默认接入百炼 **qwen3-vl-embedding** / **qwen3-vl-rerank**（与 `examples/02_lancedb_demo.py` 同一套凭证和模型）。

Stage 9 使用独立表 `service_memories`，不写入、不混用：

```text
memories
experiences
artifact_memories
image_memories
qwen_multimodal_memories
```

## 架构

```text
FastAPI
  ↓
MemoryService
  ↓
MemoryManager / RetrievalPipeline
  ↓
Repository + EmbeddingAdapter + RerankerAdapter
  ↓
LanceDB  service_memories
```

检索仍是：vector + keyword → RRF → 可选 rerank。

## 运行

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
uvicorn app.main:app --reload
```

Swagger: http://127.0.0.1:8000/docs

## 写入

```bash
curl -X POST http://127.0.0.1:8000/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Planner 在 Planning 前增加 Research 阶段可以降低输入不确定性",
    "memory_type": "reflection",
    "importance": 0.9,
    "metadata": {
      "project": "harness",
      "agent": "planner"
    }
  }'
```

## 搜索

```bash
curl -X POST http://127.0.0.1:8000/v1/memories/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "为什么 Planner 需要 Research 阶段？",
    "top_k": 5,
    "memory_types": ["reflection"],
    "filters": {
      "project": "harness"
    },
    "rerank": true
  }'
```

## Qwen Adapter

默认 `EMBEDDING_PROVIDER=qwen`、`RERANKER_PROVIDER=qwen`。

凭证与 02 相同，写在 `.env`：

```text
DASHSCOPE_API_KEY=sk-...
BAILIAN_WORKSPACE_ID=llm-...
BAILIAN_REGION=cn-beijing
```

走 `qwen3-vl-embedding`（`enable_fusion=true`）和 `qwen3-vl-rerank`。单元测试里才会切到 mock。

## 更早阶段

```bash
python examples/stage8_demo.py
python examples/01_bailian_smoke_test.py
python examples/02_lancedb_demo.py
```

# Qwen3-VL + 阿里云百炼 + LanceDB

这是独立的 Qwen3-VL fusion 向量空间，表名 `qwen_multimodal_memories`。

它不替换、也不混入 Stage 5~8 已有的：

```text
memories
experiences
artifact_memories
image_memories
```

上层只依赖 `EmbeddingAdapter` / `RerankerAdapter`。
百炼 API Key 稍后手动导入环境变量即可，本层不把 Key 写进代码。

## 架构

```text
Query
  ↓
EmbeddingAdapter
  ↓
qwen3-vl-embedding
  ↓
Vector Recall ─────┐
                   ├→ RRF Fusion
FTS / BM25 ────────┘
                        ↓
                  Candidate Pool
                        ↓
                 RerankerAdapter
                        ↓
                 qwen3-vl-rerank
                        ↓
                      Top K
```

核心原则：

```text
Qwen != 系统接口
```

上层只依赖：

```text
EmbeddingAdapter
RerankerAdapter
```

因此后续可替换为 GME/BGE/自研实现。

---

## 1. 百炼环境变量

```bash
export DASHSCOPE_API_KEY="sk-..."
export BAILIAN_WORKSPACE_ID="你的 Workspace ID"
export BAILIAN_REGION="cn-beijing"
```

北京生产推荐 Base URL：

```text
https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1
```

也可以手工覆盖：

```bash
export BAILIAN_BASE_URL="https://xxx/api/v1"
```

---

## 2. 安装

```bash
pip install -r requirements.txt
```

`requirements.txt` 仍包含 Stage 5~8 的 sentence-transformers / OpenCLIP 等依赖；
本层额外需要 `requests`。百炼调用本身不在安装阶段完成，等 API 导入后再跑下面的示例。

---

## 3. 先验证 API

```bash
python examples/01_bailian_smoke_test.py
```

验证：

```text
qwen3-vl-embedding
qwen3-vl-rerank
API Key
Workspace
Region/Base URL
```

都正常。

---

## 4. 再跑 LanceDB

开表走现有 `storage` 路径（`./database/lance`）。本地连接没有 `table_exists`。

```bash
python examples/02_lancedb_demo.py
```

检索语义保持：

```text
Vector Recall + FTS
  → RRF Fusion
  → RerankerAdapter
  → Top K
```

不要把这一路改成 Stage 7 的 `query_type="hybrid"`。Qwen 空间与 ST / OpenCLIP 空间分开。

---

## 5. Embedding Adapter

```python
embedder = BailianQwen3VLEmbeddingAdapter(
    client,
    dimension=1024,
)
```

支持：

```python
MultimodalInput.text("...")
```

以及：

```python
MultimodalInput.mixed(
    texts=["Planner 架构图"],
    images=["./architecture.png"],
)
```

本地图片会被自动编码成 Base64 Data URI。

每个 Memory Unit 都使用：

```text
enable_fusion=true
```

得到一个统一向量。

---

## 6. 为什么保存 embedding_space_id

表中保存：

```text
embedding_space_id
embedding_model
embedding_dimension
```

例如：

```text
aliyun-bailian:qwen3-vl-embedding:fusion:d1024:v1
```

以后切：

```text
Qwen -> GME
```

或者：

```text
1024 -> 2048
```

都应视为新 vector space。

Embedding 替换通常需要重新生成旧 Memory 向量。

Reranker 替换通常不需要。

---

## 7. Reranker Adapter

```python
reranker = BailianQwen3VLRerankerAdapter(
    client
)
```

Pipeline 只看到：

```text
RerankerAdapter
```

以后可以替换：

```text
NoopReranker
RuleBasedReranker
LocalCrossEncoder
自研 Reranker
其他云 API
```

---

## 8. Fusion 和 Rerank 继续分离

```text
Vector + FTS
   ↓
RRF
```

解决多路召回融合。

```text
Candidate Pool
   ↓
Qwen3-VL-Rerank
```

解决 Query-Candidate 精排。

不要把这两个阶段合并成一个概念。

---

## 9. Mixed Memory 的当前百炼限制

`qwen3-vl-embedding` 可以：

```text
text + image + video -> fused vector
```

但百炼 `qwen3-vl-rerank` 当前 HTTP candidate 文档接口，
一条 candidate 使用：

```text
{"text": ...}
{"image": ...}
{"video": ...}
```

之一。

因此 Adapter 对 mixed Memory 做 provider projection：

```text
image > video > text
```

Domain Model 仍保存完整 mixed 内容。

未来换支持真正 mixed-document rerank 的 Provider，
只修改 Reranker Adapter。

---

## 10. 下一步建议

等当前 Pipeline 跑通后，再增加：

```text
Router
  ↓
RetrievalPolicy
  ↓
动态选择：
- vector / FTS 权重
- candidate_k
- rerank_k
- reranker adapter
- embedding space
```

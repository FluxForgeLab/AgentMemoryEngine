# Stage 7 — Hybrid Search

这一包是对 Stage 5 / Stage 6 的增量升级，不是重新设计 Memory System。

## 第一性目标

Stage 7 将：

```text
Retrieval
=
Metadata Constraint
+
Vector Recall
+
Keyword Recall
+
Fusion / Rerank
+
Memory Ranking
```

落到代码。

## 文件

```text
hybrid/
├── types.py       # vector / keyword / hybrid
└── index.py       # FTS index 与 Experience schema migration

memory/
├── retriever.py   # 三路检索
├── scorer.py      # 统一 retrieval relevance + importance + recency
└── manager.py     # search(mode=...)

experience/
├── model.py       # search_text
└── repository.py  # Experience Hybrid Search
```

## 1. 为什么 Experience 增加 search_text

Stage 6：

```text
task
action
result
lesson
```

Stage 7 新增：

```text
search_text =
Task + Lesson
```

因为 Experience Retrieval 的目标是：

```text
Current Task
    ↓
过去类似 Task
+
过去可复用 Lesson
```

因此 Vector 与 FTS 应尽量搜索同一份信息。

## 2. 创建 FTS Index

第一次进入 Stage 7：

```python
from hybrid.index import (
    FTSProfile,
    setup_stage7_indexes,
)

setup_stage7_indexes(
    memory_table=memory_table,
    experience_table=experience_table,
    profile=FTSProfile.MULTILINGUAL_CODE,
)
```

如果之前已经创建过同名 FTS index，不要反复重建。

需要重新构建时：

```python
replace=True
```

## 3. 为什么默认使用 ngram

当前项目同时存在：

- 中文
- 英文
- Python / TypeScript 符号
- 类名、函数名
- GH-1842 等 issue id
- ESP32-S3 等型号
- 文件路径与版本号

简单按空格切词对中文不理想。

因此示例默认：

```text
base_tokenizer = ngram
ngram = 2~4
```

它不需要额外的 Jieba 模型文件。

如果你的环境已经准备 LanceDB 的 Jieba tokenizer 模型，可改为：

```python
FTSProfile.CHINESE_JIEBA
```

## 4. Memory Search

```python
from hybrid.types import SearchMode

results = manager.search(
    "Planner ResearchStageV2 为什么失败",
    mode=SearchMode.HYBRID,
    top_k=5,
)
```

也可以显式比较：

```python
SearchMode.VECTOR
SearchMode.KEYWORD
SearchMode.HYBRID
```

## 5. Experience Search

```python
experiences = repository.search(
    "修复 GH-1842 跨平台路径问题",
    mode=SearchMode.HYBRID,
    min_score=0.5,
    top_k=5,
)
```

Stage 6 的 ExperienceLoop 不需要推倒重写。

它原来的：

```python
repository.search(task, ...)
```

现在默认就是 Hybrid Search。

## 6. 为什么不直接加 BM25 + Cosine + RRF 原始分数

因为三种分数不在同一个 score space：

```text
cosine distance
BM25 score
RRF score
```

本实现把 Retriever 的最终顺序统一转成：

```text
retrieval_score = 1 / rank
```

然后再进入 Memory Scorer：

```text
Final Memory Score
=
retrieval relevance
+
importance
+
recency
```

这样 Retrieval 层与 Memory Value 层职责是分开的。

## 7. LanceDB API

本实现按照当前 Python API 的显式 Hybrid 模式：

```python
table.search(
    query_type="hybrid",
    vector_column_name="vector",
    fts_columns="content",
)\
.vector(query_vector)\
.text(query_text)\
.rerank(RRFReranker(), normalize="rank")
```

并保留：

```python
.where(..., prefilter=True)
```

因此 Metadata Filter 同时约束 Vector 和 FTS 两侧候选空间。

## 8. 运行

把本包对应目录覆盖/合并到 Stage 6 项目：

```text
agent-memory-engine/
├── embedding/
├── memory/
├── experience/
├── hybrid/
└── ...
```

安装：

```bash
pip install -r requirements.txt
```

运行：

```bash
python examples/stage7_demo.py
```

测试：

```bash
pytest tests/
```

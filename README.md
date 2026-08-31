# Stage 6 - Experience Loop

对应 Agent Memory Engine 第六阶段：

```text
Task
 ↓
Retrieve Past Experience
 ↓
Execute
 ↓
Result
 ↓
Reflection
 ↓
Lesson
 ↓
Admission Gate
 ↓
Store Experience
```

## Files

- `experience/model.py`: Experience、Reflection、ExecutionOutcome 数据模型
- `experience/reflector.py`: Reflector 接口、CallableReflector、LLMReflector
- `experience/repository.py`: Experience Table 的存储和向量检索
- `experience/loop.py`: before_task / after_task / run 完整闭环
- `examples/stage6_demo.py`: 两轮任务演示
- `tests/test_experience_loop.py`: 最小单元测试

## Integration

本阶段依赖第五阶段已有的：

```text
embedding/embedder.py
memory/manager.py   # 可选，通过 memory_publisher 同步 Reflection Memory
```

Experience 表的核心字段保持设计文档：

```text
task
action
result
lesson
score
```

额外加入：`id / success / created_at / vector`，用于工程化存储与检索。

# Docker 深度学习实践教程：容器化 Agent Memory Engine

> 学习目标：不是“背 Docker 命令”，而是从第一性原理理解 Docker，并最终把现有 **Agent Memory Engine** 完整容器化，使其具备可复现运行、数据持久化、环境隔离、可观测、可升级和可部署能力。

---

# 0. 项目背景

我们已经有一条 Agent Memory 的学习主线：

```text
LanceDB CRUD
    ↓
Embedding
    ↓
Vector Search
    ↓
Metadata Filter
    ↓
Agent Memory
    ↓
Experience Loop
    ↓
Hybrid Search / RAG / 更高级 Memory
```

Agent Memory Engine 的核心技术栈：

```text
Python 3.11
FastAPI
sentence-transformers
LanceDB
SQLite
OpenAI / DeepSeek API
```

核心模块可以抽象为：

```text
User / Agent
     |
     v
MemoryManager
     |
     +-------------------+
     |                   |
     v                   v
Retriever             SQLite
     |               deterministic state
     v
Embedder
     |
     v
LanceDB
semantic memory
```

典型的数据流：

```text
Query
  ↓
Embedding
  ↓
Metadata Filter
  ↓
Vector Search
  ↓
Scoring
  ↓
Top-K Memory
  ↓
Agent Context
```

Experience Loop：

```text
Task
 ↓
Execute
 ↓
Result
 ↓
Reflection
 ↓
Store Experience
 ↓
Next Task Retrieval
```

现在引入 Docker。

Docker 的目标不是改变 Memory Engine 的业务架构。

Docker 要解决的是：

> 如何保证这套系统在任何机器上，都能够以几乎一致的环境运行，并且程序升级、容器删除之后，记忆仍然存在？

这正是 Docker 最适合解决的问题。

---

# 1. 第一性原理：为什么需要 Docker

先不讨论 Docker。

假设现在直接运行：

```bash
python api/server.py
```

程序依赖：

```text
Python 3.11
lancedb
sentence-transformers
fastapi
uvicorn
sqlite
模型文件
环境变量
系统动态库
```

换一台机器可能出现：

```text
Python 版本不同
依赖版本不同
操作系统不同
环境变量缺失
模型缓存路径不同
文件权限不同
LanceDB 数据目录不同
```

于是出现经典问题：

```text
在我电脑上能跑。
```

Docker 试图解决：

```text
应用
+
运行环境
+
依赖
+
启动方式
```

统一封装。

最终：

```text
Source Code
    ↓
Dockerfile
    ↓
Image
    ↓
Container
```

其中：

```text
Image = 可复制的运行模板

Container = Image 的一次运行实例
```

---

# 2. Docker 最核心的五个概念

整个 Docker 学习过程中，首先只需要真正理解五件事：

```text
Image
Container
Volume
Network
Environment
```

这五个概念几乎可以解释日常 Docker 开发中的绝大多数问题。

---

## 2.1 Image

Image 是：

> 一个只读的应用运行模板。

可以把它理解成：

```text
Linux 用户空间
+
Python
+
Python Dependencies
+
Agent Memory Source Code
+
启动命令
```

例如：

```text
agent-memory-engine:v1
```

它描述：

```text
这个应用应该如何运行。
```

而不是：

```text
这个应用当前运行到了哪里。
```

---

## 2.2 Container

Container 是：

> Image 的运行实例。

例如：

```text
agent-memory-engine:v1
```

可以启动：

```text
Container A
Container B
Container C
```

就像：

```text
Class
  ↓
Object
```

对应：

```text
Image
  ↓
Container
```

这不是完全等价的实现关系，但作为初始心智模型非常有效。

---

## 2.3 Volume

Volume 是本项目最关键的 Docker 概念。

Container 默认有自己的文件系统。

假设：

```text
Container
└── /app/data/lancedb
```

程序向里面写入 Agent Memory。

如果随后：

```bash
docker rm container
```

Container 被删除。

如果数据只存在 Container 文件系统里，那么：

```text
Agent Memory
=
一起删除
```

这是绝对不可接受的。

Memory 系统必须满足：

```text
Container 生命周期
        ≠
Memory 生命周期
```

因此必须把数据从 Container 中分离：

```text
Container
    |
    | mount
    v
Volume
```

最终：

```text
Container 删除
      ↓
Volume 仍然存在
      ↓
新 Container
      ↓
重新挂载 Volume
      ↓
Memory 恢复
```

这就是 Volume 的本质。

---

## 2.4 Network

如果只有一个 Agent Memory Container：

```text
Client
  ↓
localhost:8000
  ↓
FastAPI Container
```

只需要端口映射。

以后如果增加：

```text
Agent Service
Memory Service
Redis
PostgreSQL
Ollama
Observability
```

则需要：

```text
Docker Network
```

Docker Compose 默认会为服务建立内部网络。

例如：

```text
agent
  |
  | http://memory:8000
  v
memory
```

注意：

Docker 内部通常不是访问：

```text
localhost:8000
```

而是：

```text
http://memory:8000
```

因为：

```text
localhost
=
当前 Container 自己
```

---

## 2.5 Environment

程序中不能硬编码：

```python
OPENAI_API_KEY = "sk-xxxx"
```

正确结构：

```text
Image
    +
Runtime Config
```

例如：

```text
OPENAI_API_KEY
DEEPSEEK_API_KEY
LANCEDB_PATH
SQLITE_PATH
EMBEDDING_MODEL
```

Docker 负责把运行时配置注入 Container。

---

# 3. Docker 对 Agent Memory Engine 的真正价值

把项目拆成四种东西：

```text
1. Code
2. Dependency
3. Configuration
4. State
```

它们应该分别处理。

| 类型 | 示例 | Docker 处理方式 |
|---|---|---|
| Code | `memory/manager.py` | Image |
| Dependency | LanceDB、FastAPI | Image |
| Configuration | API Key、模型名 | Environment |
| State | SQLite、LanceDB 数据 | Volume |

这是整个教程最重要的一张表。

任何 Docker 架构问题，都可以先问：

> 这个东西到底属于 Code、Dependency、Configuration 还是 State？

---

# 4. 最终目标架构

完成本教程以后，我们希望得到：

```text
                         Host
                          |
                    localhost:8000
                          |
                          v
              +-----------------------+
              | Agent Memory Container|
              |                       |
              | FastAPI               |
              | MemoryManager         |
              | Retriever             |
              | Embedder              |
              | LanceDB Client        |
              | SQLite Client         |
              +----------+------------+
                         |
           +-------------+-------------+
           |                           |
           v                           v
     LanceDB Volume              SQLite Volume
      semantic data              structured state

           |
           v
    Model Cache Volume
 sentence-transformers
```

注意：

```text
LanceDB
```

在这里不是一个独立数据库服务器。

它是：

```text
Python Process
    ↓
LanceDB Library
    ↓
本地数据目录
```

所以第一阶段完全没必要创建：

```text
lancedb:
  image: xxx
```

这种独立服务。

---

# 5. 学习路线

Docker 学习按照以下顺序：

```text
Phase 0  本地基线
   ↓
Phase 1  Image / Container
   ↓
Phase 2  Dockerfile
   ↓
Phase 3  Volume
   ↓
Phase 4  Environment
   ↓
Phase 5  Port / Network
   ↓
Phase 6  Docker Compose
   ↓
Phase 7  Debug / Log / Exec
   ↓
Phase 8  Build Cache
   ↓
Phase 9  Healthcheck / Restart
   ↓
Phase 10 Security
   ↓
Phase 11 Backup / Upgrade
   ↓
Phase 12 Production Mental Model
```

每一阶段都直接作用于 Agent Memory Engine。

---

# 6. Phase 0：建立本地运行基线

Docker 化之前必须先确认：

> 项目在宿主机上是可以正常运行的。

否则以后出现错误时无法判断：

```text
业务代码问题
or
Docker 问题
```

---

## 6.1 推荐目录

```text
agent-memory-engine/
│
├── api/
│   ├── __init__.py
│   └── server.py
│
├── database/
│   ├── __init__.py
│   ├── lance.py
│   └── sqlite.py
│
├── embedding/
│   ├── __init__.py
│   └── embedder.py
│
├── memory/
│   ├── __init__.py
│   ├── manager.py
│   ├── retriever.py
│   └── scorer.py
│
├── data/
│   ├── lancedb/
│   └── memory.db
│
├── tests/
│
├── requirements.txt
├── .env
└── README.md
```

---

## 6.2 requirements.txt

示例：

```text
fastapi
uvicorn[standard]
lancedb
sentence-transformers
pydantic
python-dotenv
```

学习阶段可以先不固定版本。

进入稳定构建以后再执行：

```bash
pip freeze > requirements.lock.txt
```

或者改用更严格的依赖管理方案。

---

## 6.3 FastAPI 最小服务

`api/server.py`

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/")
def root():
    return {
        "service": "agent-memory-engine"
    }
```

运行：

```bash
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

浏览器访问：

```text
http://localhost:8000/health
```

得到：

```json
{
  "status": "ok"
}
```

---

## Phase 0 验收

必须能够解释：

```text
为什么 Docker 化之前要先建立本地运行基线？
```

答案：

```text
为了把应用问题和容器环境问题分离。
```

---

# 7. Phase 1：真正理解 Image 和 Container

先不要 Dockerfile。

直接启动官方 Python Image：

```bash
docker run --rm python:3.11-slim python --version
```

发生了什么？

```text
docker run
   ↓
本地查找 python:3.11-slim
   ↓
不存在 → Pull
   ↓
创建 Container
   ↓
执行 python --version
   ↓
Process Exit
   ↓
--rm 删除 Container
```

---

## 7.1 Container 本质是什么

一个很重要的认知：

> Container 不是虚拟机。

从程序视角，可以近似理解为：

```text
被 Namespace 隔离
+
被 Cgroups 管理
+
拥有独立文件系统视图
```

的 Linux Process。

因此：

```text
Docker Container
```

最终仍然是：

```text
Process
```

而不是完整的 Guest OS。

---

## 7.2 做实验

进入 Python Container：

```bash
docker run -it --rm python:3.11-slim bash
```

然后：

```bash
python --version
pwd
ls
cat /etc/os-release
```

退出：

```bash
exit
```

---

## 7.3 第一性原理理解

虚拟机：

```text
Hardware
 ↓
Host OS
 ↓
Hypervisor
 ↓
Guest OS
 ↓
Application
```

Container：

```text
Hardware
 ↓
Host Kernel
 ↓
Container Runtime
 ↓
Isolated Process
```

所以 Container 通常：

```text
启动更快
占用更小
环境更容易复制
```

---

# 8. Phase 2：给 Agent Memory Engine 写 Dockerfile

现在正式创建：

```text
Dockerfile
```

---

## 8.1 第一版 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD [
    "uvicorn",
    "api.server:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000"
]
```

注意：

Dockerfile 实际使用时 JSON 数组必须写在一行或合法的 Dockerfile continuation 中。

推荐实际文件：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

# 9. 逐句理解 Dockerfile

不要背语法。

理解每一条指令改变了什么。

---

## 9.1 FROM

```dockerfile
FROM python:3.11-slim
```

意思：

```text
我的 Image
建立在
python:3.11-slim Image
之上
```

基础 Image 已包含：

```text
Linux 用户空间
Python 3.11
pip
```

---

## 9.2 WORKDIR

```dockerfile
WORKDIR /app
```

相当于后面的命令默认：

```bash
cd /app
```

---

## 9.3 COPY

```dockerfile
COPY requirements.txt .
```

Host：

```text
./requirements.txt
```

复制到 Image：

```text
/app/requirements.txt
```

---

## 9.4 RUN

```dockerfile
RUN pip install -r requirements.txt
```

注意：

```text
RUN
```

发生在：

```text
docker build
```

阶段。

不是 Container 启动阶段。

这点非常重要。

---

## 9.5 CMD

```dockerfile
CMD ["uvicorn", ...]
```

发生在：

```text
docker run
```

之后。

所以：

```text
RUN = Build Time
CMD = Runtime
```

---

# 10. Build 第一版 Image

执行：

```bash
docker build -t agent-memory-engine:v1 .
```

拆解：

```text
docker build
```

构建 Image。

```text
-t agent-memory-engine:v1
```

给 Image 命名。

```text
.
```

当前目录作为 Build Context。

---

## 10.1 查看 Image

```bash
docker images
```

看到：

```text
agent-memory-engine   v1
```

---

## 10.2 启动 Container

```bash
docker run \
  --name agent-memory \
  -p 8000:8000 \
  agent-memory-engine:v1
```

访问：

```text
http://localhost:8000/health
```

---

# 11. Port Mapping：为什么需要 `-p`

Container 有自己的网络空间。

FastAPI 在 Container 内监听：

```text
0.0.0.0:8000
```

但 Host 默认访问不到。

因此：

```bash
-p 8000:8000
```

表示：

```text
Host:8000
    ↓
Container:8000
```

完整结构：

```text
Browser
  |
  | localhost:8000
  v
Host Port 8000
  |
  | Docker NAT
  v
Container Port 8000
  |
  v
Uvicorn
```

---

## 11.1 为什么不能监听 127.0.0.1

如果 Container 中运行：

```bash
uvicorn api.server:app --host 127.0.0.1
```

服务只绑定 Container 自己的 loopback。

宿主机的端口映射可能无法正常访问。

因此 Container Web 服务通常监听：

```text
0.0.0.0
```

---

# 12. Phase 3：Volume——本项目最重要的一章

假设代码：

```python
import lancedb

db = lancedb.connect("./data/lancedb")
```

Container 中：

```text
/app/data/lancedb
```

Memory 写进去。

然后：

```bash
docker rm -f agent-memory
```

重新创建。

数据可能消失。

为什么？

因为：

```text
Container Filesystem
```

的生命周期属于 Container。

---

# 13. State 与 Compute 分离

Agent Memory Engine 应该拆成：

```text
Compute
+
State
```

Compute：

```text
Python
FastAPI
Embedding
Retriever
MemoryManager
```

State：

```text
LanceDB
SQLite
```

Docker Container 应该尽可能是：

```text
Disposable Compute
```

而 Memory 应该是：

```text
Persistent State
```

因此：

```text
Container
可以删

Memory
不能删
```

---

# 14. 使用 Bind Mount 学习 Volume

开发阶段先使用 Bind Mount。

启动：

```bash
docker run \
  --name agent-memory \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  agent-memory-engine:v1
```

Windows PowerShell 可以使用：

```powershell
docker run `
  --name agent-memory `
  -p 8000:8000 `
  -v "${PWD}/data:/app/data" `
  agent-memory-engine:v1
```

含义：

```text
Host:
./data

       mount

Container:
/app/data
```

于是：

```text
/app/data/lancedb
```

实际上写入：

```text
Host ./data/lancedb
```

---

# 15. Named Volume

生产思维下通常更推荐 Docker 管理的 Named Volume。

创建：

```bash
docker volume create agent-memory-data
```

启动：

```bash
docker run \
  --name agent-memory \
  -p 8000:8000 \
  -v agent-memory-data:/app/data \
  agent-memory-engine:v1
```

查看：

```bash
docker volume ls
```

---

## Bind Mount vs Named Volume

| 特征 | Bind Mount | Named Volume |
|---|---|---|
| Host 路径直接可见 | 是 | 通常不直接管理 |
| 开发方便 | 很方便 | 一般 |
| Docker 管理 | 否 | 是 |
| 迁移/生产 | 一般 | 更规范 |
| 适合源码热更新 | 是 | 否 |
| 适合数据库状态 | 可以 | 很适合 |

本项目建议：

```text
开发：
Bind Mount

部署：
Named Volume
```

---

# 16. 关键实验：证明 Container 删除后 Memory 仍然存在

你必须亲手做这个实验。

### Step 1

运行 Container：

```bash
docker run \
  --name memory-test \
  -v agent-memory-data:/app/data \
  agent-memory-engine:v1
```

### Step 2

写入一条 Memory。

例如：

```text
Docker Volume 用于持久化 Agent Memory
```

### Step 3

删除：

```bash
docker rm -f memory-test
```

### Step 4

重新创建：

```bash
docker run \
  --name memory-test-2 \
  -v agent-memory-data:/app/data \
  agent-memory-engine:v1
```

### Step 5

重新查询 Memory。

如果仍然存在：

```text
你真正理解了 Volume。
```

---

# 17. SQLite 和 LanceDB 应该如何挂载

推荐统一：

```text
/app/data/
├── lancedb/
└── memory.db
```

代码不要硬编码路径。

例如：

```python
import os

DATA_DIR = os.getenv("DATA_DIR", "./data")

LANCEDB_PATH = os.path.join(DATA_DIR, "lancedb")
SQLITE_PATH = os.path.join(DATA_DIR, "memory.db")
```

Container：

```text
/app/data
```

整体挂载 Volume。

结构：

```text
Volume
└── data/
    ├── lancedb/
    └── memory.db
```

---

# 18. Phase 4：Environment——配置与代码分离

创建：

```text
.env
```

例如：

```env
DATA_DIR=/app/data

EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

OPENAI_API_KEY=

DEEPSEEK_API_KEY=
```

注意：

```text
.env
```

绝对不要提交真实 API Key。

`.gitignore`：

```gitignore
.env
data/
__pycache__/
*.pyc
```

---

## 18.1 Python 读取环境变量

```python
import os

data_dir = os.getenv(
    "DATA_DIR",
    "./data"
)

model_name = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
```

---

## 18.2 Docker 注入

```bash
docker run \
  --env-file .env \
  -p 8000:8000 \
  -v agent-memory-data:/app/data \
  agent-memory-engine:v1
```

---

# 19. 为什么不能把 API Key COPY 进 Image

错误：

```dockerfile
COPY .env .
```

问题：

```text
Image
可能上传 Registry

Image Layer
可能永久留下 Secret
```

即使后面：

```dockerfile
RUN rm .env
```

也不代表之前 Layer 中的数据消失。

正确原则：

```text
Secret
必须 Runtime Inject
```

而不是：

```text
Build Into Image
```

---

# 20. Phase 5：Docker Network

当前：

```text
Client
 ↓
FastAPI Container
```

暂时不需要复杂网络。

但是理解 Network 非常重要。

以后可能拆成：

```text
Agent API
   |
   v
Memory Service
   |
   +----> Redis
   |
   +----> Model Service
```

Docker Compose 中：

```text
memory
```

本身就是一个 DNS 名。

例如：

```python
MEMORY_URL = "http://memory:8000"
```

---

# 21. localhost 的经典陷阱

假设有：

```text
Container A
Container B
```

在 A 中：

```text
localhost
```

表示：

```text
Container A
```

不是：

```text
Host
```

也不是：

```text
Container B
```

因此：

```text
Container A
  |
  | http://memory:8000
  v
Container B
```

才是典型服务访问方式。

---

# 22. Phase 6：Docker Compose

到这里开始解决：

```text
docker run 参数越来越长
```

例如：

```bash
docker run \
  --name agent-memory \
  --env-file .env \
  -p 8000:8000 \
  -v agent-memory-data:/app/data \
  agent-memory-engine:v1
```

Compose 本质上是：

> 把 Container 的运行配置写成声明式文件。

---

# 23. 第一版 compose.yaml

```yaml
services:
  memory:
    build:
      context: .
    container_name: agent-memory
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - agent-memory-data:/app/data

volumes:
  agent-memory-data:
```

运行：

```bash
docker compose up
```

后台：

```bash
docker compose up -d
```

停止：

```bash
docker compose down
```

---

# 24. `down` 为什么通常不会删除 Memory

执行：

```bash
docker compose down
```

通常删除：

```text
Container
Network
```

但不会删除 Named Volume。

如果执行：

```bash
docker compose down -v
```

才会删除 Volume。

对于 Agent Memory 项目：

```text
docker compose down -v
```

要非常谨慎。

因为这可能等价于：

```text
删除长期记忆。
```

---

# 25. Compose 的第一性原理

Compose 描述：

```text
Desired Runtime Topology
```

例如：

```yaml
services:
```

表示：

```text
我要哪些运行单元？
```

```yaml
volumes:
```

表示：

```text
哪些状态要持久存在？
```

```yaml
networks:
```

表示：

```text
哪些服务之间能够通信？
```

---

# 26. 推荐项目结构

Docker 化后：

```text
agent-memory-engine/
│
├── api/
│   └── server.py
│
├── database/
│   ├── lance.py
│   └── sqlite.py
│
├── embedding/
│   └── embedder.py
│
├── memory/
│   ├── manager.py
│   ├── retriever.py
│   └── scorer.py
│
├── tests/
│
├── data/
│
├── Dockerfile
├── compose.yaml
├── .dockerignore
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

# 27. `.dockerignore`

创建：

```text
.git
.gitignore
.env
__pycache__
*.pyc
.pytest_cache
.venv
venv
data
*.db
*.log
```

为什么？

因为：

```text
docker build .
```

最后的：

```text
.
```

表示 Build Context。

Docker 需要把 Context 发送给 Build Engine。

如果里面存在：

```text
data/lancedb
模型
日志
.git
venv
```

可能让 Build Context 极其庞大。

---

# 28. Build Context 的第一性原理

执行：

```bash
docker build .
```

不是简单说：

```text
在这个目录构建。
```

更准确地说：

```text
把这个目录作为构建输入上下文。
```

因此 Dockerfile 中：

```dockerfile
COPY . .
```

只能访问：

```text
Build Context
```

范围内的文件。

---

# 29. Phase 7：Docker Debugging

Docker 学习中非常重要的一部分不是：

```text
如何启动
```

而是：

```text
出问题以后如何定位
```

建议形成固定 Debug Flow。

---

# 30. 第一步：看 Container

```bash
docker ps
```

包括停止的：

```bash
docker ps -a
```

问题：

```text
Container 根本没启动？
还是启动以后立即退出？
```

---

# 31. 第二步：看 Log

```bash
docker logs agent-memory
```

持续：

```bash
docker logs -f agent-memory
```

Compose：

```bash
docker compose logs
```

单服务：

```bash
docker compose logs -f memory
```

---

# 32. 第三步：进入 Container

```bash
docker exec -it agent-memory bash
```

查看：

```bash
pwd
ls
ls /app
ls /app/data
env
python --version
pip list
```

这是定位问题极其重要的能力。

---

# 33. 第四步：验证数据目录

Container 内：

```bash
ls -lah /app/data
```

检查：

```text
LanceDB 文件是否存在
SQLite 文件是否存在
```

然后：

```bash
mount
```

或者：

```bash
docker inspect agent-memory
```

确认 Volume 挂载。

---

# 34. 第五步：验证配置

Container 内：

```bash
env | grep DATA
```

不要打印真实 Secret 到公开日志。

可以只检查：

```python
bool(os.getenv("OPENAI_API_KEY"))
```

而不是输出 Key 内容。

---

# 35. 第六步：验证 Network

如果有多个服务：

```bash
docker compose exec agent curl http://memory:8000/health
```

或者用 Python：

```bash
python -c "import urllib.request; print(urllib.request.urlopen('http://memory:8000/health').read())"
```

---

# 36. 建立固定故障模型

Docker 问题最好按照层级判断：

```text
Application
   ↑
Dependency
   ↑
Filesystem
   ↑
Environment
   ↑
Network
   ↑
Container
   ↑
Image
```

问题定位时从底向上排查。

例如：

```text
API 请求失败
```

不要第一时间修改业务代码。

先问：

```text
Container 活着吗？
Port 对吗？
Process 启动了吗？
Environment 对吗？
Volume 对吗？
最后才是业务代码。
```

---

# 37. Phase 8：理解 Docker Layer 和 Build Cache

Dockerfile：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .
```

为什么不写：

```dockerfile
COPY . .

RUN pip install -r requirements.txt
```

原因：

```text
Docker Build Cache
```

---

# 38. Layer 心智模型

粗略理解：

```text
FROM
  ↓
Layer 1

WORKDIR
  ↓
Layer 2

COPY requirements
  ↓
Layer 3

RUN pip install
  ↓
Layer 4

COPY source
  ↓
Layer 5
```

如果只修改：

```text
memory/manager.py
```

那么：

```text
requirements.txt
```

没有变化。

Docker 可以复用：

```text
pip install
```

对应的缓存。

否则每次改一行代码都重新安装：

```text
torch
sentence-transformers
lancedb
```

构建会非常慢。

---

# 39. Agent Memory 项目的特殊问题：Embedding Model

`sentence-transformers` 第一次加载模型时通常需要下载模型文件。

例如：

```python
SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2"
)
```

第一次可能比较慢。

这里有两种策略。

---

## Strategy A：运行时下载

优点：

```text
Image 小
构建简单
```

缺点：

```text
第一次启动慢
需要网络
模型版本变化风险
```

---

## Strategy B：Build 时下载

优点：

```text
运行可预测
无需首次启动下载
```

缺点：

```text
Image 变大
Build 变慢
模型更新需要重新 Build
```

学习阶段推荐：

```text
Strategy A
+
Model Cache Volume
```

---

# 40. 模型缓存 Volume

Hugging Face 默认缓存目录可以通过环境变量控制。

`.env`：

```env
HF_HOME=/app/model-cache
```

Compose：

```yaml
services:
  memory:
    build: .
    volumes:
      - agent-memory-data:/app/data
      - model-cache:/app/model-cache

volumes:
  agent-memory-data:
  model-cache:
```

这样：

```text
Container 删除
```

以后：

```text
模型缓存仍然存在
```

避免重复下载。

---

# 41. State 分类进一步细化

现在系统实际上有三种持久化数据：

```text
Business State
Cache
Secret
```

Business State：

```text
LanceDB
SQLite
```

Cache：

```text
Embedding Model Cache
```

Secret：

```text
OpenAI API Key
DeepSeek API Key
```

三者不能混淆。

| 类型 | 删除后影响 |
|---|---|
| Business State | 可能造成数据丢失 |
| Cache | 可以重新生成 |
| Secret | 必须安全重新注入 |

---

# 42. Phase 9：Healthcheck

Container 在运行：

```text
不等于
服务可用
```

例如：

```text
Python Process 仍存在
```

但：

```text
Memory 初始化失败
LanceDB 无法访问
Embedding 初始化失败
```

因此需要 Healthcheck。

---

# 43. FastAPI Health Endpoint

简单版：

```python
@app.get("/health")
def health():
    return {
        "status": "ok"
    }
```

更好的版本：

```python
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "agent-memory-engine",
    }
```

进一步可以拆：

```text
/liveness
/readiness
```

---

# 44. Liveness vs Readiness

Liveness：

```text
Process 还活着吗？
```

Readiness：

```text
现在能接收真实请求吗？
```

例如：

```text
FastAPI 已经启动
但 Embedding Model 仍未加载
```

则：

```text
alive = true
ready = false
```

这是生产系统的重要概念。

---

# 45. Compose Healthcheck

如果 Image 里有 curl：

```yaml
services:
  memory:
    build: .
    healthcheck:
      test:
        [
          "CMD",
          "curl",
          "-f",
          "http://localhost:8000/health"
        ]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s
```

但是：

```text
python:3.11-slim
```

不一定默认安装 curl。

因此也可以使用 Python 自己：

```yaml
healthcheck:
  test:
    [
      "CMD",
      "python",
      "-c",
      "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
    ]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 30s
```

---

# 46. Restart Policy

Compose：

```yaml
restart: unless-stopped
```

意思近似：

```text
异常退出以后自动重启
但用户明确停止后不要自动启动
```

注意：

```text
Restart
```

不能替代：

```text
修复 Crash
```

它只是运行时恢复策略。

---

# 47. Phase 10：Security

Docker 不是天然安全。

最基本的安全原则：

```text
1. 不把 Secret 写进 Image
2. 尽量不用 root
3. Image 尽量小
4. 只开放必要 Port
5. 只挂载必要目录
6. 固定关键依赖版本
7. 定期更新 Base Image
```

---

# 48. 使用非 root 用户

改进 Dockerfile：

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home appuser \
    && mkdir -p /app/data /app/model-cache \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

不过注意：

Volume 挂载以后仍可能涉及：

```text
Host UID/GID
```

权限问题。

所以遇到：

```text
Permission denied
```

要优先检查：

```text
Container User
Volume Ownership
Host Filesystem Permission
```

---

# 49. 为什么 `PYTHONUNBUFFERED=1`

Container 中：

```python
print(...)
```

如果 stdout buffering 导致日志不能及时刷新，会影响：

```bash
docker logs
```

因此：

```dockerfile
ENV PYTHONUNBUFFERED=1
```

可以让日志更及时输出。

---

# 50. 为什么 `PYTHONDONTWRITEBYTECODE=1`

避免 Python 在 Container 中大量生成：

```text
__pycache__
*.pyc
```

它不是必须配置，但通常适合容器运行环境。

---

# 51. Phase 11：Backup

Volume 解决：

```text
Container 删除
```

但 Volume 不等于 Backup。

这是非常重要的区别。

```text
Volume
=
持久化

Backup
=
额外的数据副本
```

如果：

```text
Host 硬盘损坏
Volume 被误删
数据文件损坏
```

Volume 本身救不了你。

---

# 52. Agent Memory Backup 的第一原则

你的长期 Memory 至少包含：

```text
SQLite
LanceDB
```

应该明确：

```text
哪些是 Source of Truth
哪些可以重建
```

如果采用：

```text
SQLite = deterministic state
LanceDB = semantic index
```

那么一个更强的设计是：

```text
Canonical Data
     ↓
SQLite / Markdown / Raw Memory
     ↓
Embedding
     ↓
LanceDB Index
```

这样 LanceDB 理论上可以：

```text
Rebuild
```

而不是把向量索引视作唯一真相来源。

---

# 53. Backup 实验

开发环境可以直接：

```bash
docker compose stop memory
```

然后备份数据目录或 Volume。

如果使用 Bind Mount：

```text
./data
```

可以压缩：

```bash
tar -czf agent-memory-backup.tar.gz data/
```

Windows 也可以使用常规压缩工具或 PowerShell。

更正式的数据库备份，需要考虑：

```text
写入一致性
文件锁
快照时间点
恢复验证
```

---

# 54. Restore 才是 Backup 的验收标准

很多人只做：

```text
Backup
```

却从不：

```text
Restore
```

真正的备份闭环应该是：

```text
Backup
 ↓
Delete Test Environment
 ↓
Restore
 ↓
Start Service
 ↓
Query Known Memory
 ↓
Verify
```

没有 Restore Test：

```text
不能证明备份有效。
```

---

# 55. Phase 12：升级 Image，而不是修改 Container

错误思维：

```bash
docker exec -it agent-memory bash

pip install xxx

vim memory/manager.py
```

然后继续长期运行。

问题：

```text
Container 已经变成不可复现状态。
```

正确流程：

```text
Source Code Change
    ↓
Dockerfile / Dependency Change
    ↓
docker build
    ↓
New Image
    ↓
Replace Container
    ↓
Reuse Same Volume
```

例如：

```text
agent-memory-engine:v1
        ↓
agent-memory-engine:v2
```

Memory Volume：

```text
保持不变
```

---

# 56. Immutable Infrastructure 思维

容器应尽量：

```text
不可变
```

意思不是文件绝对不能写。

而是：

```text
应用版本不要靠进入 Container 手工修改。
```

应用版本应该通过：

```text
Image Version
```

表达。

例如：

```text
agent-memory-engine:0.1.0
agent-memory-engine:0.2.0
agent-memory-engine:0.3.0
```

---

# 57. Agent Memory Engine 的推荐 Dockerfile

学习完成后可以使用：

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home appuser \
    && mkdir -p /app/data /app/model-cache \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

# 58. 推荐 `.env.example`

```env
DATA_DIR=/app/data

HF_HOME=/app/model-cache

EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

OPENAI_API_KEY=

DEEPSEEK_API_KEY=
```

开发者执行：

```bash
cp .env.example .env
```

然后填写自己的 Secret。

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

---

# 59. 推荐 compose.yaml

```yaml
services:
  memory:
    build:
      context: .
    container_name: agent-memory
    env_file:
      - .env
    ports:
      - "8000:8000"
    volumes:
      - agent-memory-data:/app/data
      - model-cache:/app/model-cache
    restart: unless-stopped
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
        ]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s

volumes:
  agent-memory-data:
  model-cache:
```

---

# 60. 推荐 `.dockerignore`

```text
.git
.gitignore

.env

__pycache__
*.pyc
.pytest_cache

.venv
venv

data

*.db
*.log

.idea
.vscode
```

是否忽略 `.vscode` 可以根据你的项目需要自行决定。

---

# 61. 推荐 `.gitignore`

```text
.env

data/

__pycache__/
*.pyc

.pytest_cache/

.venv/
venv/

*.log
```

---

# 62. Docker Compose 完整运行流程

第一次：

```bash
docker compose build
```

启动：

```bash
docker compose up -d
```

查看：

```bash
docker compose ps
```

日志：

```bash
docker compose logs -f memory
```

健康状态：

```bash
docker inspect agent-memory
```

停止：

```bash
docker compose stop
```

再次启动：

```bash
docker compose start
```

删除 Container：

```bash
docker compose down
```

重新创建：

```bash
docker compose up -d
```

Memory 应该仍然存在。

---

# 63. 开发模式：源码热更新

开发时不希望：

```text
改一行 Python
↓
重新 build
```

可以挂载源码。

开发专用：

```yaml
services:
  memory:
    build: .
    command:
      [
        "uvicorn",
        "api.server:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload"
      ]
    volumes:
      - .:/app
      - agent-memory-data:/app/data
      - model-cache:/app/model-cache
```

但注意：

```text
开发 Compose
```

和：

```text
部署 Compose
```

应该逐渐分开。

因为生产环境通常不应该：

```text
-v .:/app
```

直接挂源码。

---

# 64. 开发与生产的边界

开发：

```text
Source Bind Mount
Reload
Debug
```

生产：

```text
Immutable Image
No Source Mount
Fixed Version
Healthcheck
Restart Policy
Persistent Volume
```

这两个目标不同。

---

# 65. 把 Docker 学习嵌入 Memory 生命周期

现在把 Docker 与 Agent Memory 的核心机制对应起来。

---

## 65.1 store()

调用：

```python
memory_manager.store(...)
```

最终：

```text
Container Process
     ↓
LanceDB / SQLite
     ↓
/app/data
     ↓
Persistent Volume
```

因此：

```text
store()
```

是否真正可靠，不只取决于 Python 代码。

还取决于：

```text
Storage Mount
```

是否正确。

---

## 65.2 search()

流程：

```text
Request
 ↓
FastAPI
 ↓
MemoryManager
 ↓
Retriever
 ↓
Embedder
 ↓
LanceDB
 ↓
Top-K
```

Docker 问题可能发生在：

```text
Embedding model cache
LanceDB path
Environment
Memory Volume
```

---

## 65.3 update()

你之前的 Memory 设计中，有一个非常重要的不变量：

```text
vector = Embedding(content)
```

如果：

```text
content
```

更新，那么：

```text
vector
```

必须同步更新。

Docker 并不负责维持这个业务不变量。

Docker 只保证：

```text
运行环境
+
State 持久化
```

因此要明确：

```text
Container Reliability
≠
Business Correctness
```

---

## 65.4 Experience Loop

```text
Task
 ↓
Execute
 ↓
Result
 ↓
Reflection
 ↓
Experience
 ↓
Persistent Volume
```

如果 Experience 只存在 Container 临时文件系统：

```text
Container Update
=
Agent Forgetting
```

所以对 Agent 系统而言：

> Volume 不只是 Docker 的“磁盘功能”，它实际上属于 Memory Architecture 的一部分。

---

# 66. Docker 与 Memory 架构之间的边界

推荐明确三层：

```text
Agent Layer

Memory Semantic Layer

Persistence Layer
```

再加 Docker：

```text
+-----------------------------------+
|            Container              |
|                                   |
| Agent                             |
|  ↓                                |
| MemoryManager                     |
|  ↓                                |
| Retriever / Scorer / Embedder     |
|  ↓                                |
| LanceDB / SQLite Client           |
+----------------+------------------+
                 |
                 v
+-----------------------------------+
|          Persistent Volume        |
|                                   |
| LanceDB                           |
| SQLite                            |
+-----------------------------------+
```

---

# 67. 一个更完整的未来架构

以后你把 Agent Memory Engine 发展成独立服务，可以变成：

```text
                     Client
                       |
                       v
                Agent Service
                       |
                       v
                Memory API
                       |
        +--------------+-------------+
        |                            |
        v                            v
   Memory Engine                 Model API
        |
   +----+----+
   |         |
   v         v
SQLite    LanceDB
```

Container 结构：

```text
agent-service
memory-service
model-service
```

但是：

> 当前学习阶段不要为了“微服务”而微服务。

因为当前核心目标仍然是：

```text
理解 Docker 的运行模型。
```

---

# 68. 为什么暂时不拆 LanceDB Container

这是一个容易犯的错误。

看到：

```text
SQLite
LanceDB
```

就认为：

```text
它们都应该作为 Database Container。
```

这是错误的抽象。

PostgreSQL：

```text
Client
 ↓
Network
 ↓
PostgreSQL Server Process
```

而当前 LanceDB：

```text
Python Process
 ↓
LanceDB Library
 ↓
Local Files
```

两者运行模型不同。

Docker 架构应该遵从软件真实运行模型。

而不是：

```text
看到 Database 三个字就创建一个 Container。
```

---

# 69. Docker 学习实验一：Container 是可删除的

目标：

```text
打破“Container 就是服务器”的错误认知。
```

操作：

```bash
docker compose up -d
```

写入 Memory：

```text
Docker Container 是 disposable compute
```

然后：

```bash
docker compose down
```

再次：

```bash
docker compose up -d
```

查询 Memory。

结果：

```text
仍然存在。
```

结论：

```text
Container
≠
Data
```

---

# 70. Docker 学习实验二：Image 是可复制环境

在电脑 A：

```bash
docker build -t agent-memory-engine:v1 .
```

在另一台机器：

```text
同样 Dockerfile
同样 Source
同样 Dependency Lock
```

应该构建出行为高度一致的运行环境。

你要理解：

Docker 提供的不是：

```text
绝对完全相同
```

而是显著降低：

```text
Environment Entropy
```

---

# 71. Docker 学习实验三：Environment 不进入 Image

执行：

```bash
docker inspect agent-memory-engine:v1
```

检查 Image。

目标：

```text
不应该在 Image 里发现真实 API Key。
```

---

# 72. Docker 学习实验四：模型缓存

第一次启动：

```text
Embedding Model Download
```

记录时间。

删除 Container：

```bash
docker compose down
```

保留：

```text
model-cache Volume
```

再次启动。

观察：

```text
模型不再完整重新下载。
```

---

# 73. Docker 学习实验五：错误 Volume

故意把：

```yaml
volumes:
  - wrong-volume:/wrong-path
```

然后写 Memory。

删除 Container。

重新创建。

Memory 丢失。

再检查：

```text
代码实际写入哪里？
Volume 实际挂载哪里？
```

这个实验会真正建立：

```text
Path Mapping
```

思维。

---

# 74. Docker 学习实验六：错误 Environment

故意：

```env
DATA_DIR=/wrong/path
```

查看：

```bash
docker compose logs
```

然后：

```bash
docker compose exec memory bash
```

确认程序实际目录。

目标：

```text
学习从 Runtime State 反推配置错误。
```

---

# 75. Docker 学习实验七：Process Crash

故意：

```python
raise RuntimeError("test crash")
```

观察：

```bash
docker compose ps
docker compose logs
```

理解：

```text
Container Lifecycle
```

以及：

```text
restart policy
```

行为。

---

# 76. Docker 学习实验八：Image Upgrade

构建：

```text
v1
```

写入 Memory：

```text
版本 v1 创建的长期经验
```

修改代码。

构建：

```text
v2
```

使用同一个：

```text
agent-memory-data
```

启动 v2。

查询旧 Memory。

如果可以找到：

```text
理解 Image 和 State 的分离。
```

---

# 77. 数据 Schema 升级问题

当代码 v2 改变：

```text
SQLite Schema
LanceDB Schema
```

可能发生：

```text
新 Image
+
旧 Data
=
不兼容
```

这就是：

```text
Data Migration
```

问题。

Docker 本身不会自动替你解决。

所以真实系统需要：

```text
Application Version
+
Schema Version
+
Migration
```

这是后面非常重要的工程能力。

---

# 78. Agent Memory Engine 的 Schema Version

建议以后加入：

```text
schema_version
```

或者迁移脚本：

```text
migrations/
```

例如：

```text
001_init.sql
002_add_memory_type.sql
003_add_importance.sql
```

LanceDB 的 Schema 变化也需要对应迁移策略。

---

# 79. Docker 不是部署系统

要明确：

```text
Docker
```

解决：

```text
Packaging
Isolation
Runtime
```

但不等于：

```text
完整 Production Platform
```

生产部署还需要考虑：

```text
Host
Registry
TLS
Reverse Proxy
Monitoring
Backup
Secret Management
Upgrade
Rollback
Resource Limit
Security
```

---

# 80. CPU / Memory Resource

Embedding 模型可能占用明显内存。

运行：

```bash
docker stats
```

观察：

```text
CPU
Memory
Network
IO
```

这对 Agent 系统很重要。

因为：

```text
LLM
Embedding
Vector Search
```

都有资源消耗。

---

# 81. Resource Limit 思维

Docker Compose 可以限制资源。

但不同 Compose / Docker Runtime 场景的字段支持需要注意。

更重要的是先理解：

```text
Container
不是无限资源
```

Embedding 模型如果需要：

```text
1 GB RAM
```

而 Container 实际只有：

```text
512 MB
```

就可能：

```text
OOM
```

甚至直接被系统 Kill。

---

# 82. OOM 调试

症状：

```text
Container 突然退出
```

Log 可能没有明确 Python Exception。

检查：

```bash
docker inspect agent-memory
```

关注：

```text
OOMKilled
```

以及：

```bash
docker stats
```

---

# 83. Logging 原则

Container 应该优先把日志写：

```text
stdout
stderr
```

而不是：

```text
/app/logs/app.log
```

原因：

Docker 可以直接：

```bash
docker logs
```

统一收集。

应用：

```python
import logging

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

logger.info("memory service started")
```

---

# 84. Memory 可观测性

建议以后增加：

```text
memory_store_total
memory_search_total
memory_search_latency
embedding_latency
retrieval_top_k
lancedb_error_total
sqlite_error_total
```

Docker 提供的是：

```text
运行载体
```

真正的 Agent Reliability 需要：

```text
Application Metrics
```

---

# 85. Agent Memory 的三类 Health

后面可以把 Health 扩展为：

```text
Process Health
Storage Health
Model Health
```

例如：

```json
{
  "status": "ok",
  "storage": {
    "sqlite": "ok",
    "lancedb": "ok"
  },
  "embedding": {
    "status": "ready"
  }
}
```

---

# 86. 测试也放进 Docker 思维

你应该保证：

```text
Docker Build
```

后的 Image 中应用能够通过核心测试。

例如：

```bash
docker run --rm agent-memory-engine:v1 pytest
```

或者创建：

```text
test target
```

以后再进一步学习：

```text
Multi-stage Build
```

---

# 87. Multi-stage Build 是什么

第一性原理：

```text
Build Environment
```

和：

```text
Runtime Environment
```

可能并不相同。

例如：

```text
Build:
compiler
dev dependency
test tools

Runtime:
只需要应用运行依赖
```

Multi-stage Build 可以：

```text
Stage A
构建

Stage B
只复制最终结果
```

对纯 Python 项目不是必须立刻引入。

如果未来有：

```text
Rust Extension
C++ Library
Frontend Build
```

价值会明显增加。

---

# 88. Docker Registry

Image 本地存在：

```text
Developer PC
```

无法直接让：

```text
ECS
```

使用。

通常流程：

```text
Source
 ↓
Build Image
 ↓
Registry
 ↓
ECS Pull Image
 ↓
Run Container
```

Registry 可以是：

```text
Docker Hub
GitHub Container Registry
Cloud Registry
企业私有 Registry
```

---

# 89. Tag 不应该只用 latest

开发可以：

```text
latest
```

但部署最好：

```text
0.1.0
0.1.1
git-sha
```

因为你需要：

```text
Rollback
```

例如：

```text
0.2.0 有 bug
↓
重新部署 0.1.1
```

---

# 90. ECS 上的最终最小形态

未来部署到 ECS：

```text
Internet
   |
   v
Reverse Proxy / HTTPS
   |
   v
Agent Memory Container
   |
   +------ Named Volume
   |
   +------ Model Cache
```

对于学习项目：

```text
单机 Docker Compose
```

已经足够理解大量生产系统基础。

暂时没有必要直接上 Kubernetes。

---

# 91. 为什么此阶段不推荐 Kubernetes

因为 Kubernetes 在解决：

```text
多机器
调度
滚动更新
服务发现
自愈
弹性
配置
Secret
```

如果 Docker 基础边界没有真正理解：

```text
Pod
Volume
Service
ConfigMap
Deployment
```

只会变成新的术语堆积。

正确顺序：

```text
Linux Process
 ↓
Docker
 ↓
Compose
 ↓
Production Container
 ↓
Kubernetes
```

---

# 92. Docker 与 Harness Engineering 的联系

Docker 对 Agent/Harness 项目尤其重要。

Harness 最大的问题之一是：

```text
执行环境不确定性
```

例如 Agent 调用工具：

```text
Python
git
compiler
test runner
filesystem
```

如果环境不可控：

```text
同一个任务
不同环境
不同结果
```

Container 可以减少：

```text
Environment Variance
```

于是：

```text
Agent Harness
+
Container Sandbox
```

成为非常自然的组合。

---

# 93. Memory + Harness + Docker

可以得到：

```text
Agent
  |
  +---- Harness
  |       |
  |       +---- Tool Control
  |       +---- Execution Policy
  |       +---- Validation
  |
  +---- Memory Engine
  |       |
  |       +---- Retrieval
  |       +---- Experience
  |
  +---- Docker Runtime
          |
          +---- Environment Isolation
          +---- Reproducibility
          +---- Resource Boundary
```

这三个东西解决的是不同维度的问题：

```text
Harness
=
行为边界

Memory
=
历史经验

Docker
=
执行环境边界
```

---

# 94. 从第一性原理看三者

一个 Agent 输出不稳定，可能来自：

```text
Model Uncertainty
Context Uncertainty
Environment Uncertainty
Tool Uncertainty
State Uncertainty
```

对应：

```text
Memory
降低历史信息缺失

Harness
降低工具与流程不确定性

Docker
降低运行环境不确定性
```

因此 Docker 并不是和 Agent Memory 无关的 DevOps 知识。

它直接影响：

```text
Agent System Reproducibility
```

---

# 95. 推荐最终练习项目

项目名称：

```text
Dockerized Agent Memory Lab
```

目标：

> 构建一个可通过 Docker Compose 一键启动的 Agent Memory Engine，并证明其在 Container 删除、Image 升级、程序重启之后仍然保持长期记忆。

---

# 96. 最终功能要求

API：

```text
POST /memories
GET  /memories/search
PUT  /memories/{id}
DELETE /memories/{id}

GET /health
```

Memory：

```text
id
content
vector
type
importance
created_at
```

Experience：

```text
task
action
result
lesson
score
```

---

# 97. 最终工程要求

必须具备：

```text
Dockerfile
compose.yaml
.dockerignore
.env.example
Persistent Volume
Model Cache
Healthcheck
Container Log
Versioned Image
Backup / Restore Test
```

---

# 98. 最终验证场景

---

## Test 1：Build

```bash
docker compose build
```

要求：

```text
无错误
```

---

## Test 2：Start

```bash
docker compose up -d
```

要求：

```text
/health = 200
```

---

## Test 3：Store

保存：

```text
Docker Volume 可以保证 Agent Memory 跨 Container 生命周期存在
```

---

## Test 4：Search

查询：

```text
容器删除之后记忆怎么办？
```

要求：

```text
向量搜索可以召回刚才的 Memory。
```

---

## Test 5：Destroy Container

```bash
docker compose down
```

然后：

```bash
docker compose up -d
```

再次 Search。

要求：

```text
Memory 仍然存在。
```

---

## Test 6：New Image

修改：

```text
API version
```

重新：

```bash
docker compose build
docker compose up -d
```

要求：

```text
旧 Memory 仍然存在。
```

---

## Test 7：Model Cache

删除 Container。

保留：

```text
model-cache
```

再次启动。

验证模型不需要完整重新下载。

---

## Test 8：Backup

备份 Memory。

然后在测试环境删除原数据。

---

## Test 9：Restore

恢复 Backup。

查询已知 Memory。

要求：

```text
成功恢复。
```

---

# 99. 你真正需要掌握的 Docker 命令

不用一开始记几十条。

优先掌握：

```bash
docker build
docker images

docker run

docker ps
docker ps -a

docker logs

docker exec

docker stop
docker rm

docker volume ls
docker volume inspect

docker inspect

docker stats

docker compose build
docker compose up
docker compose down
docker compose ps
docker compose logs
docker compose exec
```

这些已经足够完成绝大多数当前学习任务。

---

# 100. Docker 命令的统一心智模型

不要背：

```text
docker xxx
```

而是先判断对象。

如果操作：

```text
Image
```

思考：

```bash
docker build
docker images
```

如果操作：

```text
Container
```

思考：

```bash
docker run
docker ps
docker logs
docker exec
docker rm
```

如果操作：

```text
State
```

思考：

```bash
docker volume
```

如果操作：

```text
Multi-container Runtime
```

思考：

```bash
docker compose
```

---

# 101. 常见错误清单

## 错误 1

```text
把 LanceDB 当 PostgreSQL 独立 Container。
```

当前项目里没有必要。

---

## 错误 2

把数据只写：

```text
/app/data
```

却没有 Volume。

Container 删除后存在数据丢失风险。

---

## 错误 3

把：

```text
.env
```

COPY 进 Image。

可能泄露 Secret。

---

## 错误 4

在 Container 里手工修改代码。

造成运行环境不可复现。

---

## 错误 5

所有问题都用：

```bash
docker compose down -v
```

这会删除 Volume。

Agent Memory 项目尤其危险。

---

## 错误 6

遇到错误只重新 Build。

应该先判断：

```text
Image
Container
Network
Environment
Volume
Application
```

是哪一层。

---

## 错误 7

以为：

```text
Container Running
=
Application Healthy
```

不成立。

---

## 错误 8

认为 Volume 就是 Backup。

不成立。

---

# 102. Docker 学习完成标准

如果你能够不用查教程，解释以下问题，说明基础已经真正建立。

### Q1

Image 和 Container 有什么区别？

### Q2

为什么 Agent Memory 必须放 Volume？

### Q3

为什么 Container 可以随时删除？

### Q4

为什么 API Key 不应该写入 Image？

### Q5

为什么 Container A 不能用 `localhost` 访问 Container B？

### Q6

为什么 `COPY requirements.txt` 应该放在 `COPY . .` 前面？

### Q7

为什么 `docker compose down -v` 对 Memory 系统危险？

### Q8

LanceDB 为什么不一定需要独立 Container？

### Q9

为什么模型缓存和业务 Memory 应该使用不同 Volume？

### Q10

为什么 Healthcheck 不等于简单检查 Process 是否存在？

### Q11

为什么新版本程序应该 Build 新 Image，而不是修改旧 Container？

### Q12

为什么持久化不等于 Backup？

如果这 12 个问题能从原理解释，而不是背答案：

```text
Docker 基础已经基本掌握。
```

---

# 103. 推荐学习节奏

不要按照：

```text
一天背完所有命令
```

学习。

建议真正动手：

```text
Day 1
Image / Container

Day 2
Dockerfile / Build

Day 3
Volume

Day 4
Environment / Port

Day 5
Compose

Day 6
Debug / Logs / Exec

Day 7
Cache / Healthcheck / Restart

Day 8
Security / Backup / Upgrade

Day 9
完整重构 Agent Memory Engine

Day 10
故障注入 + Restore 验证
```

重点不是日期。

重点是：

```text
每学一个概念
必须在 Agent Memory Engine 上做一次实验。
```

---

# 104. 最终认知模型

Docker 最终可以压缩成：

```text
                    Docker
                      |
       +--------------+--------------+
       |              |              |
       v              v              v
     Image        Container        Volume
       |              |              |
       |              |              |
   Application      Process         State
   Environment      Runtime         Persistence
```

对于 Agent Memory Engine：

```text
Image
=
Agent Memory 程序 + Python + Dependencies

Container
=
正在运行的 Agent Memory Process

Volume
=
Agent 真正长期保存的记忆
```

进一步：

```text
Environment
=
Runtime Configuration

Network
=
Service Communication

Compose
=
Runtime Topology
```

---

# 105. 把所有知识重新组合

最后系统变成：

```text
                    User
                      |
                      v
                 FastAPI
                      |
                      v
                MemoryManager
                      |
          +-----------+-----------+
          |                       |
          v                       v
      Retriever                SQLite
          |
          v
       Embedder
          |
          v
       LanceDB

============== Container Boundary ==============

             /app/data
                 |
                 v
       Persistent Docker Volume

============== Persistence Boundary ============

Container 可以被：

delete
restart
replace
upgrade

但 Memory：

continues to exist
```

这就是本教程最核心的目标。

---

# 106. 下一阶段：Docker 与 Agent Harness

当上述内容真正掌握以后，可以继续做：

```text
Agent Execution Sandbox
```

例如：

```text
Agent
 ↓
Harness
 ↓
Docker Sandbox
 ↓
Execute Tool
 ↓
Collect Result
 ↓
Validator
 ↓
Experience Memory
```

这时 Docker 不再只是：

```text
部署工具
```

而会成为：

```text
Agent Harness Runtime
```

你后续研究：

```text
Planner
Research
Tool Execution
Validation
RSI
Experience Loop
```

都会和它产生直接关系。

---

# 107. 最终项目交付物

完成整个学习项目后，仓库至少应该包含：

```text
agent-memory-engine/
│
├── api/
├── database/
├── embedding/
├── memory/
├── tests/
│
├── Dockerfile
├── compose.yaml
├── .dockerignore
├── .env.example
├── requirements.txt
│
├── scripts/
│   ├── backup.sh
│   └── restore.sh
│
└── docs/
    └── docker-architecture.md
```

并且 README 中必须能够做到：

```bash
git clone ...
cd agent-memory-engine
cp .env.example .env
docker compose up -d
```

然后：

```text
服务启动
Memory 可写
Memory 可搜索
Container 可替换
Memory 不丢失
```

当你做到这一点时，你掌握的就已经不是“Docker 基础命令”，而是：

> 如何把一个真实的、有状态的 Agent 系统放进可复现、可替换、可持续运行的容器环境中。

---

# 108. 一句话收束

对于你的 Agent Memory Engine，可以把 Docker 的本质记成：

```text
Image 保存“系统应该是什么样”
Container 表示“系统现在正在运行”
Volume 保存“Agent 曾经经历过什么”
```

而 Harness、Memory 与 Docker 三者进一步形成：

```text
Harness
=
控制 Agent 如何行动

Memory
=
保存 Agent 学到了什么

Docker
=
控制 Agent 在什么环境中行动
```

这三个边界建立清楚以后，再进入更复杂的 Agent Runtime、Sandbox、CI/CD、Kubernetes 或 RSI 系统，才不会只是堆积工具和术语。

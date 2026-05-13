# 多智能体框架 (Multi-Agent Framework)

基于LangGraph的多智能体协作框架，支持前后端分离、多会话管理、记忆存储、意图识别和工具调用。

## 功能特性

### 核心功能
- **多智能体编排**：基于LangGraph的智能体工作流协调
- **记忆管理系统**：Redis短期记忆 + MySQL长期记忆 + Milvus向量记忆
- **意图识别**：BERT快速分类 + LLM高精度分类，支持意图重定向
- **工具调用**：支持重试、降级、熔断机制的工具调用系统
- **实时通信**：SSE流式传输，自动心跳检测和重连
- **人工干预**：支持人工审批和操作干预

### 智能体范式
- Plan-and-Execute：规划-执行范式，生成可存储的待办列表
- ReAct：思考-行动范式，交替思考和工具调用
- 专用智能体：研究智能体、编程智能体等

## 技术栈

### 后端
- **框架**：FastAPI (Python 3.10+)
- **智能体框架**：LangGraph + LangChain
- **数据库**：MySQL (长期记忆)，Redis (短期缓存)，Milvus (向量存储)
- **机器学习**：Transformers (BERT)，SentenceTransformers
- **LLM支持**：多供应商 (OpenAI, Anthropic, Ollama本地模型)

### 前端
- **框架**：React 18 + TypeScript
- **状态管理**：Zustand
- **UI组件**：Material-UI / Ant Design
- **实时通信**：EventSource API (SSE)，WebSocket

### 部署
- **容器化**：Docker + Docker Compose
- **监控**：Prometheus + Grafana
- **日志**：结构化日志，ELK Stack

## 项目结构

```
multi-agent/
├── backend/           # Python后端
├── frontend/          # React前端
├── docs/             # 文档
├── scripts/          # 部署脚本
├── docker/           # Docker配置
├── .env.example      # 环境变量示例
└── docker-compose.yml # 容器编排
```

## 快速开始

### 1. 环境准备
```bash
# 克隆项目
git clone <repository-url>
cd multi-agent

# 复制环境变量
cp .env.example .env
# 编辑 .env 文件，配置数据库连接和API密钥
```

### 2. 使用Docker启动（推荐）
```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 3. 手动启动

#### 后端
```bash
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端
```bash
cd frontend
npm install
npm run dev
```

### 4. 访问应用
- 前端界面：http://localhost:5173
- API文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 开发指南

### 添加新智能体
1. 在 `backend/src/agents/` 创建新智能体类，继承 `BaseAgent`
2. 在 `backend/src/agents/registry.py` 中注册智能体
3. 在 `backend/src/graph/workflows/` 中创建工作流（可选）

### 添加新工具
1. 在 `backend/src/tools/implementations/` 创建工具类
2. 使用 `@tool` 装饰器注册工具
3. 在 `backend/src/tools/registry.py` 中注册工具

### 配置意图识别
1. 在 `backend/src/intent/models/` 训练或配置意图模型
2. 在 `backend/src/intent/intent_categories.py` 中定义意图类别和阈值

## 部署

### 生产环境
```bash
# 构建Docker镜像
docker-compose -f docker-compose.prod.yml build

# 启动服务
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes部署
参考 `kubernetes/` 目录下的配置文件。

## 监控和日志

### 指标监控
- Prometheus端点：http://localhost:8000/metrics
- Grafana仪表板：http://localhost:3000

### 日志查询
```bash
# 查看应用日志
docker-compose logs backend

# 查看结构化日志文件
tail -f logs/app.log
```

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。
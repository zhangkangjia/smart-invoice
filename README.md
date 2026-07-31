# Smart Invoice — 智能开票平台

纯网页端、多租户、AI智能开票平台，面向代账公司及集中开票服务团队。

## 技术栈

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Pinia |
| 后端 | Python 3.12 + FastAPI + Pydantic + SQLAlchemy 2.0 |
| 数据库 | PostgreSQL 16 |
| 缓存 | Redis 7 |
| 消息队列 | RabbitMQ 3.13 |
| 文件存储 | MinIO (S3兼容) |
| OCR | PaddleOCR (P1阶段) |
| AI | 可替换的文本/多模态模型适配层 (P1阶段) |

## 快速启动

```bash
# 1. 复制环境变量
cp .env.example .env

# 2. 启动所有服务
docker-compose up -d

# 3. 初始化数据库
docker-compose exec backend python -m app.db.init_db

# 4. 创建初始管理员
docker-compose exec backend python -m app.scripts.create_admin

# 5. 访问
# 前端: http://localhost:3000
# 后端API文档: http://localhost:8000/docs
# RabbitMQ管理: http://localhost:15672
# MinIO控制台: http://localhost:9001
```

## 本地开发

### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 项目结构

```
smart-invoice/
├── docs/                    # 设计文档
├── frontend/                # Vue 3 前端
│   ├── src/
│   │   ├── api/             # API请求
│   │   ├── components/       # 公共组件
│   │   ├── layouts/          # 布局
│   │   ├── router/           # 路由
│   │   ├── stores/           # Pinia状态管理
│   │   ├── types/            # TypeScript类型
│   │   ├── utils/            # 工具函数
│   │   └── views/            # 页面
│   └── ...
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/           # API路由
│   │   ├── core/             # 核心配置、安全
│   │   ├── db/               # 数据库
│   │   ├── models/           # SQLAlchemy模型
│   │   ├── schemas/          # Pydantic模型
│   │   ├── services/         # 业务逻辑
│   │   ├── tasks/            # 异步任务
│   │   └── utils/            # 工具函数
│   └── ...
├── docker-compose.yml
└── .env.example
```

## 实施阶段

- **P0**: 确定性闭环与模拟开票（当前）
- **P1**: AI智能识别
- **P2**: 真实通道与生产试点
- **P3**: 千企规模化与多通道

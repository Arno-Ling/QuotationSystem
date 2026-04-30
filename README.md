# 模具委外采购管理系统

基于 **Agent + Harness + Skills + RAG** 架构的智能模具委外采购管理系统,通过AI技术优化采购流程,并在关键决策点引入人机交互(HITL)机制。

## 📋 项目概述

本系统旨在解决模具制造企业在委外采购过程中的痛点:
- ✅ 自动化询价、报价、订单生成流程
- ✅ AI辅助委外决策和供应商选择
- ✅ 智能异常检测和定责
- ✅ 人机协同的关键决策机制
- ✅ 完整的流程追溯和数据分析

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (React)                          │
│  看板系统 | 人机交互界面 | 项目管理 | 供应商管理        │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              FastAPI 接口网关                            │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              Harness 调度器                              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              Agent 编排层                                │
│  流程编排 | 状态管理 | 人机交互处理                     │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              Skills 技能层                               │
│  数据检索 | 委外决策 | 供应商管理 | 询价报价            │
│  任务管理 | 进度跟踪 | 异常处理 | 人机交互 | RAG检索   │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│         数据层 (MySQL + RAG知识库)                       │
└─────────────────────────────────────────────────────────┘
```

## 🚀 技术栈

### 后端
- **语言**: Python 3.9+
- **Web框架**: FastAPI
- **ORM**: SQLAlchemy
- **数据库**: MySQL 8.0+
- **AI框架**: LangChain
- **向量数据库**: ChromaDB / FAISS
- **认证**: JWT

### 前端
- **框架**: React 18
- **构建工具**: Vite
- **状态管理**: Redux Toolkit
- **UI组件**: Ant Design 5
- **样式**: Tailwind CSS
- **路由**: React Router v6

### 基础设施
- **容器化**: Docker + Docker Compose
- **缓存**: Redis
- **Web服务器**: Nginx

## 📦 快速开始

### 前置要求

- Python 3.9+
- Node.js 18+
- MySQL 8.0+
- Docker (可选)

### 方式一: Docker Compose (推荐)

```bash
# 1. 克隆项目
git clone <repository-url>
cd mold-procurement-system

# 2. 配置环境变量
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# 编辑.env文件,填入实际配置

# 3. 启动所有服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 访问应用
# 前端: http://localhost:3000
# 后端API文档: http://localhost:8000/docs
```

### 方式二: 本地开发

#### 后端启动

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑.env文件

# 初始化数据库
mysql -u root -p < database/init.sql

# 启动服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 配置环境变量
cp .env.example .env

# 启动开发服务器
npm run dev
```

## 📚 项目结构

```
mold-procurement-system/
├── backend/                 # 后端代码
│   ├── core/               # 核心模块(Harness, Agent)
│   ├── skills/             # 技能模块
│   ├── api/                # API接口
│   ├── database/           # 数据库相关
│   ├── services/           # 服务层
│   ├── utils/              # 工具函数
│   ├── tests/              # 测试
│   ├── main.py             # 应用入口
│   ├── config.py           # 配置管理
│   └── requirements.txt    # Python依赖
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── components/     # 组件
│   │   ├── pages/          # 页面
│   │   ├── store/          # Redux状态
│   │   ├── services/       # API服务
│   │   └── utils/          # 工具函数
│   ├── public/             # 静态资源
│   └── package.json        # Node依赖
├── docker-compose.yml      # Docker编排
├── .gitignore
├── README.md
├── 项目理解.md              # 项目详细说明
└── 开发任务清单.md          # 开发任务列表
```

## 🎯 核心功能

### 1. 智能委外决策
- 基于成本、产能、MOQ的自动决策
- AI辅助分析和建议
- 人工审核确认机制

### 2. 供应商智能匹配
- 能力匹配算法
- 地理位置优化
- 历史评级参考

### 3. 自动化询价报价
- 批量询价单生成
- 邮件自动发送
- OCR报价单解析
- 人工审核和谈判

### 4. 可视化看板管理
- 拖拽式任务管理
- 实时状态更新
- 待审核任务高亮
- 进度统计分析

### 5. 智能异常处理
- 自动异常检测
- AI辅助定责分析
- 历史案例参考
- 解决方案推荐
- 临时让步接收流程

### 6. 人机交互(HITL)
- 委外决策确认
- 报价审核
- 异常处理确认
- 灵活的审批流程

## 🔑 默认账号

系统初始化后会创建以下测试账号:

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员 |
| manager1 | manager123 | 项目经理 |
| buyer1 | buyer123 | 采购员 |
| qc1 | qc123 | 质检主管 |

⚠️ **生产环境请务必修改默认密码!**

## 📖 文档

- [项目理解文档](./项目理解.md) - 详细的项目说明和架构设计
- [开发任务清单](./开发任务清单.md) - 完整的开发任务列表
- [后端README](./backend/README.md) - 后端开发指南
- [前端README](./frontend/README.md) - 前端开发指南
- [API文档](http://localhost:8000/docs) - FastAPI自动生成的API文档

## 🧪 测试

### 后端测试
```bash
cd backend
pytest
pytest --cov=. --cov-report=html
```

### 前端测试
```bash
cd frontend
npm run test
npm run test:coverage
```

## 🚢 部署

### 生产环境部署清单

- [ ] 修改所有默认密码和密钥
- [ ] 配置HTTPS证书
- [ ] 设置DEBUG=False
- [ ] 配置生产数据库
- [ ] 配置Redis缓存
- [ ] 设置日志收集
- [ ] 配置监控和告警
- [ ] 配置备份策略
- [ ] 配置防火墙规则
- [ ] 性能测试和优化

详细部署文档请参考各模块的README。

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📝 开发进度

- [x] 基础设施搭建
- [ ] 后端核心开发
- [ ] 前端开发
- [ ] 测试和优化
- [ ] 部署和运维
- [ ] 功能增强

详细进度请查看 [开发任务清单](./开发任务清单.md)

## 📄 许可证

MIT License

## 👥 联系方式

如有问题或建议,请提交Issue或联系项目维护者。

---

**注意**: 本项目目前处于开发阶段,部分功能使用Mock数据。生产环境使用前请确保完成所有真实实现的替换和安全加固。

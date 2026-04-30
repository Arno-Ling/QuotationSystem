# 模具委外采购系统 - 后端

基于 Agent + Harness + Skills + RAG 架构的智能模具委外采购管理系统后端服务。

## 技术栈

- **Web框架**: FastAPI
- **数据库**: MySQL 8.0+ (SQLAlchemy ORM)
- **AI框架**: LangChain
- **向量数据库**: ChromaDB / FAISS
- **认证**: JWT
- **Python版本**: 3.9+

## 项目结构

```
backend/
├── config.py              # 配置管理
├── main.py               # FastAPI应用入口
├── requirements.txt      # Python依赖
├── .env.example         # 环境变量示例
├── .env                 # 环境变量(不提交到Git)
├── database/
│   ├── init.sql         # 数据库初始化脚本
│   ├── connection.py    # 数据库连接
│   └── models.py        # SQLAlchemy模型
├── core/
│   ├── harness.py       # Harness调度器
│   ├── agent.py         # Agent核心逻辑
│   └── base_skill.py    # Skill基类
├── skills/
│   ├── data_retrieval.py          # 数据检索
│   ├── outsourcing_decision.py    # 委外决策
│   ├── supplier_management.py     # 供应商管理
│   ├── inquiry_quotation.py       # 询价报价
│   ├── task_management.py         # 任务管理
│   ├── progress_tracking.py       # 进度跟踪
│   ├── exception_handling.py      # 异常处理
│   ├── human_interaction.py       # 人机交互
│   └── rag_skill.py              # RAG检索
├── api/
│   ├── routes/          # API路由
│   ├── schemas/         # Pydantic模型
│   └── dependencies.py  # 依赖注入
├── services/
│   ├── auth.py          # 认证服务
│   ├── ocr.py           # OCR服务
│   ├── email.py         # 邮件服务
│   └── ai_model.py      # AI模型服务
├── utils/
│   ├── logger.py        # 日志工具
│   └── helpers.py       # 辅助函数
└── tests/
    ├── test_skills.py
    ├── test_agent.py
    └── test_api.py
```

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑.env文件,填入实际配置
```

### 3. 初始化数据库

```bash
# 登录MySQL
mysql -u root -p

# 执行初始化脚本
source database/init.sql
```

### 4. 运行开发服务器

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/docs 查看API文档

## 核心概念

### Harness (调度器)
- 管理所有Skills和Agent的注册
- 提供统一的请求入口
- 负责Skills和Agent的生命周期管理

### Agent (智能代理)
- 编排业务流程
- 调用Skills完成具体任务
- 处理人机交互反馈
- 维护执行状态

### Skills (技能模块)
- 独立的业务功能单元
- 可插拔设计
- 通过Harness注册和调用

### RAG (检索增强生成)
- 从知识库检索相关信息
- 辅助AI决策
- 提供历史案例参考

## API接口

### 核心接口
- `POST /api/skill/{skill_name}` - 调用特定技能
- `POST /api/human_in_the_loop` - 处理人工反馈
- `GET /api/agent/state` - 获取Agent状态

### 认证接口
- `POST /api/auth/login` - 用户登录
- `POST /api/auth/register` - 用户注册
- `GET /api/auth/me` - 获取当前用户信息

## 开发指南

### 添加新的Skill

1. 在`skills/`目录创建新文件
2. 继承`BaseSkill`类
3. 实现`execute()`方法
4. 在`main.py`中注册Skill

```python
from core.base_skill import BaseSkill

class MyNewSkill(BaseSkill):
    def __init__(self):
        super().__init__(
            name="MyNewSkill",
            description="我的新技能"
        )
    
    def execute(self, **kwargs):
        # 实现业务逻辑
        return {"status": "success", "data": {}}
```

### 测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_skills.py

# 生成覆盖率报告
pytest --cov=. --cov-report=html
```

## 部署

### Docker部署

```bash
# 构建镜像
docker build -t mold-procurement-backend .

# 运行容器
docker run -d -p 8000:8000 --env-file .env mold-procurement-backend
```

### 生产环境配置

1. 设置`DEBUG=False`
2. 使用强密码和密钥
3. 配置HTTPS
4. 启用日志收集
5. 配置监控和告警

## 许可证

MIT License

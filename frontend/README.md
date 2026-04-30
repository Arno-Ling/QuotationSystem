# 模具委外采购系统 - 前端

基于 React + Redux + Ant Design 的现代化前端应用。

## 技术栈

- **框架**: React 18
- **构建工具**: Vite
- **状态管理**: Redux Toolkit
- **UI组件库**: Ant Design 5
- **样式**: Tailwind CSS
- **路由**: React Router v6
- **HTTP客户端**: Axios
- **拖拽**: react-beautiful-dnd

## 项目结构

```
frontend/
├── public/              # 静态资源
├── src/
│   ├── main.jsx        # 应用入口
│   ├── App.jsx         # 根组件
│   ├── assets/         # 资源文件
│   ├── components/     # 通用组件
│   │   ├── Layout/     # 布局组件
│   │   ├── Kanban/     # 看板组件
│   │   └── Common/     # 公共组件
│   ├── pages/          # 页面组件
│   │   ├── Login/
│   │   ├── Dashboard/
│   │   ├── Projects/
│   │   ├── Suppliers/
│   │   └── Exceptions/
│   ├── store/          # Redux状态管理
│   │   ├── index.js
│   │   ├── slices/
│   │   └── thunks/
│   ├── services/       # API服务
│   │   ├── api.js
│   │   ├── auth.js
│   │   └── kanban.js
│   ├── hooks/          # 自定义Hooks
│   ├── utils/          # 工具函数
│   ├── constants/      # 常量定义
│   └── styles/         # 全局样式
├── index.html
├── vite.config.js
├── tailwind.config.js
├── package.json
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
# 使用 npm
npm install

# 或使用 yarn
yarn install

# 或使用 pnpm
pnpm install
```

### 2. 配置环境变量

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑.env文件,配置API地址等
```

### 3. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3000

### 4. 构建生产版本

```bash
npm run build
```

构建产物在 `dist/` 目录

## 核心功能

### 1. 看板系统
- 可视化任务流转
- 拖拽式任务管理
- 实时状态更新
- 待审核任务高亮

### 2. 人机交互
- 委外决策审核
- 报价审核
- 异常处理审核
- 实时反馈机制

### 3. 项目管理
- 项目列表和详情
- 模具和零件管理
- 进度跟踪
- 数据统计

### 4. 供应商管理
- 供应商信息维护
- 能力评估
- 历史记录查询

### 5. 异常管理
- 异常报告
- AI辅助定责
- 解决方案跟踪
- 证据包管理

## 开发指南

### 组件开发规范

```jsx
// 使用函数组件和Hooks
import React, { useState, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';

function MyComponent({ prop1, prop2 }) {
  const [state, setState] = useState(null);
  const dispatch = useDispatch();
  const data = useSelector(state => state.myData);

  useEffect(() => {
    // 副作用逻辑
  }, []);

  return (
    <div className="my-component">
      {/* JSX */}
    </div>
  );
}

export default MyComponent;
```

### 状态管理

```javascript
// 使用 Redux Toolkit
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

export const fetchData = createAsyncThunk(
  'feature/fetchData',
  async (params) => {
    const response = await api.getData(params);
    return response.data;
  }
);

const featureSlice = createSlice({
  name: 'feature',
  initialState: { data: [], loading: false },
  reducers: {
    setData: (state, action) => {
      state.data = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchData.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchData.fulfilled, (state, action) => {
        state.data = action.payload;
        state.loading = false;
      });
  },
});

export const { setData } = featureSlice.actions;
export default featureSlice.reducer;
```

### API调用

```javascript
// 使用封装的axios实例
import api from '@/services/api';

// GET请求
const data = await api.get('/endpoint', { params: { id: 1 } });

// POST请求
const result = await api.post('/endpoint', { data: {} });
```

## 样式指南

### 使用Tailwind CSS

```jsx
<div className="flex items-center justify-between p-4 bg-white rounded-lg shadow">
  <h2 className="text-xl font-bold text-gray-800">标题</h2>
  <button className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
    按钮
  </button>
</div>
```

### 使用Ant Design组件

```jsx
import { Button, Table, Modal } from 'antd';

<Button type="primary" onClick={handleClick}>
  主要按钮
</Button>

<Table 
  dataSource={data} 
  columns={columns}
  pagination={{ pageSize: 10 }}
/>
```

## 测试

```bash
# 运行测试
npm run test

# 生成覆盖率报告
npm run test:coverage
```

## 部署

### Docker部署

```bash
# 构建镜像
docker build -t mold-procurement-frontend .

# 运行容器
docker run -d -p 80:80 mold-procurement-frontend
```

### Nginx配置

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 性能优化

1. **代码分割**: 使用动态import和React.lazy
2. **图片优化**: 使用WebP格式,懒加载
3. **缓存策略**: 合理使用浏览器缓存
4. **打包优化**: 配置Vite的rollup选项

## 浏览器支持

- Chrome >= 90
- Firefox >= 88
- Safari >= 14
- Edge >= 90

## 许可证

MIT License

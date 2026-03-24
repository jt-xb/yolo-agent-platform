# 后端测试

## 运行测试

### 安装测试依赖
```bash
cd backend
pip install pytest pytest-asyncio httpx
```

### 运行所有测试
```bash
cd backend
pytest -v
```

### 运行特定测试文件
```bash
pytest tests/test_llm_tools.py -v
pytest tests/test_training_loop.py -v
pytest tests/test_api_routes.py -v
```

### 运行带覆盖率的测试
```bash
pytest --cov=. --cov-report=html
```

## 测试结构

- `conftest.py` - pytest fixtures 和测试配置
- `test_llm_tools.py` - LLM Agent 工具函数测试
- `test_training_loop.py` - 训练循环测试
- `test_api_routes.py` - API 路由测试

## 测试数据库

测试使用独立的 SQLite 数据库 (`test.db`)，每个测试函数使用独立的数据库会话，测试结束后自动清理数据。

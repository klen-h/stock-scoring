
# 使用官方 Python 镜像作为基础
FROM python:3.9-slim-buster

# 设置工作目录
WORKDIR /app/backend

# 复制依赖文件并安装依赖
COPY ./backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制整个应用代码
COPY ./backend .

# 暴露应用端口
EXPOSE 8000

# 启动 Uvicorn 服务器
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

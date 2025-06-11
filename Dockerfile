# VPS Monitor Bot - Docker Configuration
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN groupadd -r vpsmonitor && useradd -r -g vpsmonitor vpsmonitor

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY monitor.py .
COPY config.json.example .

# 创建数据目录
RUN mkdir -p /app/data /app/logs && \
    chown -R vpsmonitor:vpsmonitor /app

# 切换到非root用户
USER vpsmonitor

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import json; config=json.load(open('config.json')); exit(0)" || exit 1

# 默认启动命令
CMD ["python3", "monitor.py"]

# 标签信息
LABEL maintainer="jinqian <email@example.com>"
LABEL version="2.1.0"
LABEL description="VPS库存监控机器人"

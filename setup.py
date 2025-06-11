#!/usr/bin/env python3
"""
VPS监控系统 v1.0 - 安装配置文件
作者: kure29
网站: https://kure29.com
"""

from setuptools import setup, find_packages
import os

# 读取README文件
def read_readme():
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "VPS库存监控系统 - 实时监控VPS库存状态的Telegram机器人"

# 读取requirements文件
def read_requirements():
    try:
        with open("requirements.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        return [
            "python-telegram-bot==20.7",
            "cloudscraper==1.2.71",
            "requests>=2.31.0",
            "aiohttp>=3.9.1",
            "brotli>=1.1.0",
            "aiofiles>=23.2.0",
            "pydantic>=2.0.0",
            "tenacity>=8.2.0",
            "jsonschema>=4.17.0",
            "python-decouple>=3.8",
            "structlog>=23.1.0",
            "ratelimit>=2.2.1",
            "validators>=0.20.0",
            "pytz>=2023.3",
            "tqdm>=4.65.0"
        ]

setup(
    name="vps-monitor-bot",
    version="1.0.0",
    description="VPS库存监控系统 - 实时监控VPS库存状态的Telegram机器人",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="kure29",
    author_email="contact@kure29.com",
    url="https://github.com/kure29/VPSMonitorBot",
    license="MIT",
    packages=find_packages(),
    package_dir={"": "src"},
    py_modules=["monitor"],
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0"
        ]
    },
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Chat",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: System :: Monitoring",
        "Topic :: Utilities"
    ],
    keywords=[
        "vps", "monitor", "telegram", "bot", "stock", "inventory", 
        "notification", "web-scraping", "automation", "alerting"
    ],
    entry_points={
        "console_scripts": [
            "vps-monitor=monitor:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.txt", "*.md", "*.json", "*.yml", "*.yaml"],
    },
    data_files=[
        ("config", ["config/config.json.example"]),
        ("scripts", [
            "scripts/menu.sh",
            "scripts/install.sh", 
            "scripts/deploy.sh",
            "scripts/backup.sh"
        ]),
        ("web", ["web/index.html"]),
        ("web/static", ["web/static/style.css", "web/static/script.js"]),
    ],
    project_urls={
        "Documentation": "https://github.com/kure29/VPSMonitorBot/wiki",
        "Source": "https://github.com/kure29/VPSMonitorBot",
        "Tracker": "https://github.com/kure29/VPSMonitorBot/issues",
        "Homepage": "https://kure29.com",
    }
)

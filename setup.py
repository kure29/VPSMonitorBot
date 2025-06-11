#!/usr/bin/env python3
"""
VPSMonitorBot 安装脚本
"""

from setuptools import setup, find_packages
import os

# 读取README文件
def read_file(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return file.read()

# 读取requirements文件
def read_requirements(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file if line.strip() and not line.startswith('#')]

setup(
    name="vps-monitor-bot",
    version="2.1.0",
    author="jinqian",
    author_email="contact@kure29.com",
    description="VPS库存监控机器人 - 实时监控VPS商家库存状态",
    long_description=read_file("README.md"),
    long_description_content_type="text/markdown",
    url="https://github.com/kure29/VPSMonitorBot",
    project_urls={
        "Bug Reports": "https://github.com/kure29/VPSMonitorBot/issues",
        "Source": "https://github.com/kure29/VPSMonitorBot",
        "Documentation": "https://github.com/kure29/VPSMonitorBot/wiki",
        "Demo Bot": "https://t.me/JQ_VPSMonitorBot",
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
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
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: System :: Monitoring",
        "Topic :: Communications :: Chat",
    ],
    python_requires=">=3.7",
    install_requires=read_requirements("requirements.txt"),
    extras_require={
        "dev": read_requirements("dev-requirements.txt"),
        "web": ["flask>=2.0.0", "flask-cors>=4.0.0"],
        "postgres": ["psycopg2-binary>=2.9.0"],
        "mysql": ["PyMySQL>=1.0.0"],
    },
    entry_points={
        "console_scripts": [
            "vps-monitor=monitor:main",
            "vps-monitor-web=web.api:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.yml", "*.yaml", "*.json", "*.html", "*.css", "*.js"],
    },
    data_files=[
        ("etc/systemd/system", ["config/vps-monitor.service"]),
        ("etc/nginx/sites-available", ["config/nginx.conf.example"]),
    ],
    zip_safe=False,
    keywords="vps monitoring telegram bot stock checker automation",
    license="MIT",
)

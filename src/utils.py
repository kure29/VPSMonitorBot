#!/usr/bin/env python3
"""
工具函数模块
VPS监控系统 v3.1
"""

import os
import sys
import urllib.parse
import shutil
from pathlib import Path
from typing import Tuple
from database_manager import MonitorItem


def setup_project_paths():
    """自动检测并设置项目路径"""
    current_file = Path(__file__).resolve()
    
    if current_file.parent.name == 'src':
        project_root = current_file.parent.parent
        print(f"🔍 检测到在src目录运行，项目根目录: {project_root}")
    else:
        project_root = current_file.parent
        print(f"🔍 检测到在项目根目录运行: {project_root}")
    
    os.chdir(project_root)
    print(f"📁 当前工作目录: {os.getcwd()}")
    
    # 检查必需文件
    required_files = ['config.json', 'requirements.txt']
    missing_files = []
    
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ 缺少必需文件: {missing_files}")
        
        if 'config.json' in missing_files and Path('config.json.example').exists():
            shutil.copy('config.json.example', 'config.json')
            print("✅ 已从示例创建config.json，请编辑配置信息")
            missing_files.remove('config.json')
        
        if missing_files:
            print(f"❌ 仍缺少文件: {missing_files}")
            sys.exit(1)
    
    print("✅ 项目路径设置完成")
    return project_root


def is_valid_url(url: str) -> Tuple[bool, str]:
    """验证URL格式"""
    if not url:
        return False, "URL不能为空"
    
    if not url.startswith(('http://', 'https://')):
        return False, "URL必须以 http:// 或 https:// 开头"
    
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.netloc:
            return False, "URL格式无效，缺少域名"
        
        invalid_domains = ['localhost', '127.0.0.1', '0.0.0.0']
        if parsed.netloc.lower() in invalid_domains:
            return False, "不支持本地地址"
            
        return True, ""
    except Exception:
        return False, "URL格式无效"


def calculate_success_rate(item: MonitorItem) -> str:
    """计算成功率"""
    total = item.success_count + item.failure_count
    if total == 0:
        return "暂无数据"
    
    rate = (item.success_count / total) * 100
    return f"{rate:.1f}%"


def calculate_global_success_rate(stats: dict) -> str:
    """计算全局成功率"""
    checks = stats.get('checks', {})
    total = checks.get('total', 0)
    successful = checks.get('successful', 0)
    
    if total == 0:
        return "暂无数据"
    
    rate = (successful / total) * 100
    return f"{rate:.1f}%"


def escape_markdown(text: str) -> str:
    """转义Markdown特殊字符"""
    if not text:
        return text
    
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


def check_dependencies():
    """检查依赖库是否可用"""
    dependencies = {}
    
    # 检查selenium
    try:
        from selenium import webdriver
        dependencies['selenium'] = True
        print("✅ Selenium可用，支持DOM监控")
    except ImportError:
        dependencies['selenium'] = False
        print("⚠️ Selenium未安装，将使用基础监控模式")
    
    # 检查服务商优化模块
    try:
        from vendor_optimization import VendorOptimizer
        dependencies['vendor_optimization'] = True
        print("✅ 服务商优化模块可用")
    except ImportError:
        dependencies['vendor_optimization'] = False
        print("⚠️ 服务商优化模块未找到，使用通用检测")
    
    return dependencies

#!/usr/bin/env python3
"""
VPS监控系统 v3.1 源码包
多用户智能监控版

作者: kure29
网站: https://kure29.com
"""

__version__ = "3.1.0"
__author__ = "kure29"
__email__ = "contact@kure29.com"
__description__ = "VPS监控系统 - 多用户智能监控版"

# 导出主要类
from .config import Config, ConfigManager
from .database_manager import DatabaseManager
from .telegram_bot import TelegramBot
from .main_monitor import VPSMonitor
from .monitors import (
    PageFingerprintMonitor,
    DOMElementMonitor,
    APIMonitor,
    SmartComboMonitor
)

__all__ = [
    'Config',
    'ConfigManager',
    'DatabaseManager', 
    'TelegramBot',
    'VPSMonitor',
    'PageFingerprintMonitor',
    'DOMElementMonitor',
    'APIMonitor',
    'SmartComboMonitor'
]

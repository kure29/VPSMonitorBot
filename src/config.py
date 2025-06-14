#!/usr/bin/env python3
"""
配置管理模块
VPS监控系统 v3.1
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Config:
    """配置数据类"""
    bot_token: str
    chat_id: str
    channel_id: Optional[str] = None
    check_interval: int = 180
    notification_aggregation_interval: int = 180
    notification_cooldown: int = 600
    request_timeout: int = 30
    retry_delay: int = 60
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    proxy: Optional[str] = None
    debug: bool = False
    log_level: str = "INFO"
    admin_ids: List[str] = None
    items_per_page: int = 10
    # 新增配置项
    enable_selenium: bool = True
    enable_api_discovery: bool = True
    enable_visual_comparison: bool = False
    confidence_threshold: float = 0.6
    chromium_path: Optional[str] = None
    daily_add_limit: int = 50
    enable_vendor_optimization: bool = True
    
    # 用户通知配置
    user_notification_enabled: bool = True
    default_user_cooldown: int = 3600
    default_daily_limit: int = 10
    default_quiet_hours_start: int = 23
    default_quiet_hours_end: int = 7
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.bot_token or self.bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
            raise ValueError("请配置正确的Telegram Bot Token")
        
        if not self.chat_id or self.chat_id == "YOUR_TELEGRAM_CHAT_ID":
            raise ValueError("请配置正确的Telegram Chat ID")
        
        if self.admin_ids is None:
            self.admin_ids = []


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self._config = None
        self.logger = logging.getLogger(__name__)
    
    def load_config(self) -> Config:
        """加载配置"""
        try:
            if not self.config_file.exists():
                self.logger.error(f"配置文件 {self.config_file} 不存在")
                raise FileNotFoundError(f"配置文件 {self.config_file} 不存在")
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                required_fields = ['bot_token', 'chat_id']
                missing_fields = [field for field in required_fields if not data.get(field)]
                
                if missing_fields:
                    raise ValueError(f"配置文件缺少必需字段: {missing_fields}")
                
                valid_fields = {field.name for field in Config.__dataclass_fields__.values()}
                filtered_data = {k: v for k, v in data.items() if k in valid_fields}
                
                extra_fields = set(data.keys()) - valid_fields
                if extra_fields:
                    self.logger.warning(f"配置文件中包含未知字段，已忽略: {extra_fields}")
                
                self._config = Config(**filtered_data)
                self.logger.info("配置文件加载成功")
                return self._config
                
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            raise
    
    @property
    def config(self) -> Config:
        """获取当前配置"""
        if self._config is None:
            self._config = self.load_config()
        return self._config

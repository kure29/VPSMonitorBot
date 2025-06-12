#!/usr/bin/env python3
"""
VPS监控系统 v1.0 - 主程序（优化版）
作者: kure29
网站: https://kure29.com
描述: VPS库存监控机器人，自动路径检测版本
"""

import os
import sys
from pathlib import Path

# ====== 路径自动检测和修复 ======
def setup_project_paths():
    """自动检测并设置项目路径"""
    current_file = Path(__file__).resolve()
    
    # 检测项目根目录
    if current_file.parent.name == 'src':
        # 在src目录下运行
        project_root = current_file.parent.parent
        print(f"🔍 检测到在src目录运行，项目根目录: {project_root}")
    else:
        # 在项目根目录运行
        project_root = current_file.parent
        print(f"🔍 检测到在项目根目录运行: {project_root}")
    
    # 切换到项目根目录
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
        
        # 尝试从示例创建配置文件
        if 'config.json' in missing_files and Path('config/config.json.example').exists():
            import shutil
            shutil.copy('config/config.json.example', 'config.json')
            print("✅ 已从示例创建config.json，请编辑配置信息")
            missing_files.remove('config.json')
        
        if missing_files:
            print(f"❌ 仍缺少文件: {missing_files}")
            sys.exit(1)
    
    print("✅ 项目路径设置完成")
    return project_root

# 设置项目路径
if __name__ == '__main__':
    PROJECT_ROOT = setup_project_paths()

# ====== 主程序导入 ======
import asyncio
import cloudscraper
import time
import logging
import json
import random
import urllib.parse
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
import aiofiles

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# ====== 数据类定义 ======
@dataclass
class MonitorItem:
    """监控项数据类"""
    id: str
    name: str
    url: str
    config: str = ""
    price: str = ""  # 价格信息
    network: str = ""  # 线路信息
    created_at: str = ""
    last_checked: str = ""
    last_notified: str = ""  # 最后通知时间
    status: Optional[bool] = None
    notification_count: int = 0
    stock_info: str = ""  # 库存信息

@dataclass
class Config:
    """配置数据类 - 支持所有可能的配置字段"""
    bot_token: str
    chat_id: str
    check_interval: int = 180  # 检查间隔3分钟
    notification_aggregation_interval: int = 180  # 聚合间隔3分钟
    notification_cooldown: int = 600  # 单个商品通知冷却时间10分钟
    request_timeout: int = 30
    retry_delay: int = 60
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    proxy: Optional[str] = None
    debug: bool = False
    log_level: str = "INFO"
    admin_ids: List[str] = None  # 管理员ID列表
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保必要字段不为空
        if not self.bot_token or self.bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
            raise ValueError("请配置正确的Telegram Bot Token")
        
        if not self.chat_id or self.chat_id == "YOUR_TELEGRAM_CHAT_ID":
            raise ValueError("请配置正确的Telegram Chat ID")
        
        # 如果没有配置管理员，则所有人都可以操作
        if self.admin_ids is None:
            self.admin_ids = []

# ====== 配置管理器 ======
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
                print(f"\n❌ 配置文件不存在: {self.config_file}")
                print("📝 请确保config.json文件存在并包含正确的配置信息")
                print("\n配置文件格式示例:")
                print('''{
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID",
    "admin_ids": ["123456789"],
    "check_interval": 180,
    "notification_aggregation_interval": 180,
    "notification_cooldown": 600
}''')
                raise FileNotFoundError(f"配置文件 {self.config_file} 不存在")
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 验证必需字段
                required_fields = ['bot_token', 'chat_id']
                missing_fields = [field for field in required_fields if not data.get(field)]
                
                if missing_fields:
                    raise ValueError(f"配置文件缺少必需字段: {missing_fields}")
                
                # 过滤掉不支持的字段，但保留所有定义的字段
                valid_fields = {field.name for field in Config.__dataclass_fields__.values()}
                filtered_data = {k: v for k, v in data.items() if k in valid_fields}
                
                # 如果有额外字段，记录警告
                extra_fields = set(data.keys()) - valid_fields
                if extra_fields:
                    self.logger.warning(f"配置文件中包含未知字段，已忽略: {extra_fields}")
                    print(f"⚠️ 配置文件中包含未知字段，已忽略: {extra_fields}")
                
                self._config = Config(**filtered_data)
                self.logger.info("配置文件加载成功")
                print("✅ 配置文件加载成功")
                return self._config
                
        except json.JSONDecodeError as e:
            self.logger.error(f"配置文件JSON格式错误: {e}")
            print(f"❌ 配置文件JSON格式错误: {e}")
            raise
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            print(f"❌ 加载配置文件失败: {e}")
            raise
    
    def save_config(self, config: Config) -> None:
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(config), f, ensure_ascii=False, indent=4)
            self._config = config
            self.logger.info("配置文件保存成功")
        except Exception as e:
            self.logger.error(f"保存配置文件失败: {e}")
            raise
    
    @property
    def config(self) -> Config:
        """获取当前配置"""
        if self._config is None:
            self._config = self.load_config()
        return self._config

# ====== 数据管理器 ======
class DataManager:
    """数据管理器"""
    
    def __init__(self, data_file: str = "urls.json"):
        self.data_file = Path(data_file)
        self._monitor_items = {}
        self.logger = logging.getLogger(__name__)
        self._ensure_data_file()
    
    def _ensure_data_file(self) -> None:
        """确保数据文件存在"""
        if not self.data_file.exists():
            self.data_file.write_text('{}', encoding='utf-8')
            self.logger.info(f"创建数据文件: {self.data_file}")
    
    async def load_monitor_items(self) -> Dict[str, MonitorItem]:
        """异步加载监控项"""
        try:
            async with aiofiles.open(self.data_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content) if content.strip() else {}
                
                self._monitor_items = {}
                for item_id, item_data in data.items():
                    self._monitor_items[item_id] = MonitorItem(
                        id=item_id,
                        name=item_data.get('名称', ''),
                        url=item_data.get('URL', ''),
                        config=item_data.get('配置', ''),
                        price=item_data.get('价格', ''),
                        network=item_data.get('线路', ''),
                        created_at=item_data.get('created_at', ''),
                        last_checked=item_data.get('last_checked', ''),
                        last_notified=item_data.get('last_notified', ''),
                        status=item_data.get('status'),
                        notification_count=item_data.get('notification_count', 0),
                        stock_info=item_data.get('stock_info', '')
                    )
                
                self.logger.info(f"成功加载 {len(self._monitor_items)} 个监控项")
                return self._monitor_items
        except Exception as e:
            self.logger.error(f"加载数据文件失败: {e}")
            return {}
    
    async def save_monitor_items(self) -> None:
        """异步保存监控项"""
        try:
            data = {}
            for item_id, item in self._monitor_items.items():
                data[item_id] = {
                    '名称': item.name,
                    'URL': item.url,
                    '配置': item.config,
                    '价格': item.price,
                    '线路': item.network,
                    'created_at': item.created_at,
                    'last_checked': item.last_checked,
                    'last_notified': item.last_notified,
                    'status': item.status,
                    'notification_count': item.notification_count,
                    'stock_info': item.stock_info
                }
            
            async with aiofiles.open(self.data_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=4))
        except Exception as e:
            self.logger.error(f"保存数据文件失败: {e}")
            raise
    
    def add_monitor_item(self, name: str, url: str, config: str = "", price: str = "", network: str = "") -> str:
        """添加监控项"""
        item_id = str(int(time.time()))
        item = MonitorItem(
            id=item_id,
            name=name,
            url=url,
            config=config,
            price=price,
            network=network,
            created_at=datetime.now().isoformat()
        )
        self._monitor_items[item_id] = item
        self.logger.info(f"添加监控项: {name} - {url}")
        return item_id
    
    def remove_monitor_item(self, url: str) -> bool:
        """删除监控项"""
        for item_id, item in list(self._monitor_items.items()):
            if item.url == url:
                del self._monitor_items[item_id]
                self.logger.info(f"删除监控项: {url}")
                return True
        return False
    
    def get_monitor_item_by_url(self, url: str) -> Optional[MonitorItem]:
        """根据URL获取监控项"""
        for item in self._monitor_items.values():
            if item.url == url:
                return item
        return None
    
    def update_monitor_item_status(self, url: str, status: bool, notification_count: int = None) -> None:
        """更新监控项状态"""
        item = self.get_monitor_item_by_url(url)
        if item:
            item.status = status
            item.last_checked = datetime.now().isoformat()
            if notification_count is not None:
                item.notification_count = notification_count
    
    @property
    def monitor_items(self) -> Dict[str, MonitorItem]:
        """获取所有监控项"""
        return self._monitor_items

# ====== 库存检查器 ======
class StockChecker:
    """库存检查器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.scraper = self._create_scraper()
        self.logger = logging.getLogger(__name__)
    
    def _create_scraper(self):
        """创建爬虫实例"""
        return cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False,
                'custom': self.config.user_agent
            },
            debug=self.config.debug
        )
    
    def _clean_url(self, url: str) -> str:
        """清理URL，移除不必要的参数"""
        try:
            parsed = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed.query)
            
            # 移除Cloudflare相关参数
            cf_params = ['__cf_chl_rt_tk', '__cf_chl_f_tk', '__cf_chl_tk', 'cf_chl_seq_tk']
            for param in cf_params:
                query_params.pop(param, None)
            
            clean_query = urllib.parse.urlencode(query_params, doseq=True)
            return urllib.parse.urlunparse((
                parsed.scheme, parsed.netloc, parsed.path,
                parsed.params, clean_query, ''
            ))
        except Exception as e:
            self.logger.error(f"清理URL失败: {e}")
            return url
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            'User-Agent': self.config.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN,zh;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive'
        }
    
    def _analyze_content(self, content: str) -> Tuple[bool, Optional[str]]:
        """分析页面内容判断库存状态"""
        content_lower = content.lower()
        
        # 检查是否为Cloudflare验证页面
        cf_indicators = ['just a moment', 'checking if the site connection is secure', 'ray id']
        if any(indicator in content_lower for indicator in cf_indicators):
            return None, "遇到Cloudflare验证，将在下次检查时重试"
        
        # 检查页面长度
        if len(content.strip()) < 100:
            return None, "页面内容过短，可能加载不完整"
        
        # 缺货关键词
        out_of_stock_keywords = [
            'sold out', 'out of stock', '缺货', '售罄', '补货中',
            'currently unavailable', 'not available', '暂时缺货',
            'temporarily out of stock', '已售完', '库存不足',
            'out-of-stock', 'unavailable', '无货', '断货',
            'not in stock', 'no stock', '无库存', 'stock: 0'
        ]
        
        # 有货关键词
        in_stock_keywords = [
            'add to cart', 'buy now', '立即购买', '加入购物车',
            'in stock', '有货', '现货', 'available', 'order now',
            'purchase', 'checkout', '订购', '下单', '继续', '繼續',
            'configure', 'select options', 'configure now', 'continue'
        ]
        
        # 订单表单指示器
        order_indicators = [
            'form', 'price', 'quantity', 'payment', 'checkout',
            'cart', 'billing', '价格', '数量', '支付', 'order form'
        ]
        
        is_out_of_stock = any(keyword in content_lower for keyword in out_of_stock_keywords)
        is_in_stock = any(keyword in content_lower for keyword in in_stock_keywords)
        has_order_form = any(indicator in content_lower for indicator in order_indicators)
        
        # 判断逻辑
        if is_out_of_stock:
            return False, None
        elif is_in_stock or (has_order_form and len(content) > 1000):
            return True, None
        else:
            return False, "无法确定库存状态"
    
    async def check_stock(self, url: str) -> Tuple[Optional[bool], Optional[str]]:
        """检查单个URL的库存状态"""
        try:
            # 添加随机延迟防止被封
            await asyncio.sleep(random.uniform(2, 5))
            
            clean_url = self._clean_url(url)
            headers = self._get_headers()
            
            # 使用异步方式执行同步请求
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.scraper.get(clean_url, headers=headers, timeout=self.config.request_timeout)
            )
            
            if not response or response.status_code != 200:
                return None, f"请求失败 (HTTP {response.status_code if response else 'No response'})"
            
            # 处理内容编码
            try:
                content = response.text
            except UnicodeDecodeError:
                encodings = ['utf-8', 'latin1', 'gbk', 'gb2312']
                content = None
                for encoding in encodings:
                    try:
                        content = response.content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if content is None:
                    return None, "无法解码页面内容"
            
            return self._analyze_content(content)
            
        except Exception as e:
            self.logger.error(f"检查库存失败 {url}: {e}")
            return None, f"检查失败: {str(e)}"

# ====== Telegram机器人（优化版） ======
class TelegramBot:
    """Telegram机器人（优化版）"""
    
    def __init__(self, config: Config, data_manager: DataManager):
        self.config = config
        self.data_manager = data_manager
        self.app = None
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self) -> None:
        """初始化机器人"""
        try:
            self.app = Application.builder().token(self.config.bot_token).build()
            await self.app.initialize()
            bot_info = await self.app.bot.get_me()
            self.logger.info(f"Telegram Bot 初始化成功: @{bot_info.username}")
            print(f"✅ Telegram Bot连接成功: @{bot_info.username}")
            
            self._setup_handlers()
            await self.app.start()
            await self.app.updater.start_polling()
            
        except Exception as e:
            self.logger.error(f"Telegram Bot 初始化失败: {e}")
            print(f"❌ Telegram Bot初始化失败: {e}")
            print("💡 请检查bot_token是否正确")
            raise
    
    def _setup_handlers(self) -> None:
        """设置命令处理器"""
        handlers = [
            CommandHandler("start", self._start_command),
            CommandHandler("help", self._help_command),
            CommandHandler("list", self._list_command),
            CommandHandler("add", self._add_command),
            CommandHandler("status", self._status_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message),
            CallbackQueryHandler(self._handle_callback)
        ]
        
        for handler in handlers:
            self.app.add_handler(handler)
    
    def _escape_markdown(self, text: str) -> str:
        """转义Markdown特殊字符"""
        if not text:
            return text
        
        # Telegram Markdown特殊字符
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    def _check_admin_permission(self, user_id: str) -> bool:
        """检查管理员权限"""
        # 如果没有配置管理员，则所有人都可以操作
        if not self.config.admin_ids:
            return True
        return user_id in self.config.admin_ids
    
    def _is_url_link(self, text: str) -> bool:
        """检测文本是否是URL链接"""
        if not text:
            return False
        
        text = text.strip()
        return (text.startswith(('http://', 'https://')) and 
                len(text) > 10 and 
                '.' in text)
    
    async def _handle_url_share(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
        """处理分享的URL链接（智能添加功能）"""
        user_id = str(update.effective_user.id)
        if not self._check_admin_permission(user_id):
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "❌ 抱歉，只有管理员才能添加监控项目",
                reply_markup=reply_markup
            )
            return
        
        # 验证URL
        is_valid, error_msg = self._is_valid_url(url)
        if not is_valid:
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"❌ {error_msg}", reply_markup=reply_markup)
            return
        
        # 检查是否已存在
        if self.data_manager.get_monitor_item_by_url(url):
            keyboard = [
                [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')],
                [InlineKeyboardButton("📝 查看列表", callback_data='list_items')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "❌ 该URL已在监控列表中！",
                reply_markup=reply_markup
            )
            return
        
        processing_msg = await update.message.reply_text("🔍 正在分析链接，获取商品信息...")
        
        try:
            # 获取页面信息
            page_info = await self._extract_page_info(url)
            
            # 设置上下文数据
            context.user_data.clear()
            context.user_data['smart_add'] = True
            context.user_data['url'] = url
            context.user_data['page_info'] = page_info
            context.user_data['edit_data'] = {
                'name': page_info.get('title', '未知商品'),
                'config': page_info.get('description', ''),
                'price': page_info.get('price', ''),
                'network': '',
                'url': url
            }
            
            await self._show_smart_add_preview(processing_msg, context)
            
        except Exception as e:
            self.logger.error(f"智能添加失败: {e}")
            keyboard = [
                [InlineKeyboardButton("📝 手动添加", callback_data='add_item')],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await processing_msg.edit_text(
                f"❌ 自动获取信息失败: {str(e)}\n\n"
                "💡 您可以选择手动添加",
                reply_markup=reply_markup
            )
    
    async def _extract_page_info(self, url: str) -> Dict[str, str]:
        """从页面提取信息"""
        try:
            # 使用cloudscraper获取页面内容
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False,
                    'custom': self.config.user_agent
                },
                debug=self.config.debug
            )
            
            headers = {
                'User-Agent': self.config.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,zh-CN,zh;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cache-Control': 'max-age=0'
            }
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: scraper.get(url, headers=headers, timeout=15)
            )
            
            if not response or response.status_code != 200:
                raise Exception(f"无法访问页面 (HTTP {response.status_code if response else 'No response'})")
            
            content = response.text
            info = {}
            
            # 提取标题
            title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
                # 清理标题
                title = re.sub(r'\s+', ' ', title)
                title = title.replace(' | ', ' - ').replace(' – ', ' - ')
                if len(title) > 100:
                    title = title[:100] + "..."
                info['title'] = title
            else:
                info['title'] = "未知商品"
            
            # 提取价格信息
            price_patterns = [
                r'\$\d+(?:\.\d{2})?(?:\s*/\s*(?:month|year|mo|yr|年|月))?',
                r'¥\d+(?:\.\d{2})?(?:\s*/\s*(?:month|year|mo|yr|年|月))?',
                r'€\d+(?:\.\d{2})?(?:\s*/\s*(?:month|year|mo|yr|年|月))?',
                r'£\d+(?:\.\d{2})?(?:\s*/\s*(?:month|year|mo|yr|年|月))?',
                r'\d+(?:\.\d{2})?\s*(?:USD|CNY|EUR|GBP)(?:\s*/\s*(?:month|year|mo|yr|年|月))?'
            ]
            
            for pattern in price_patterns:
                price_matches = re.findall(pattern, content, re.IGNORECASE)
                if price_matches:
                    # 取第一个匹配的价格
                    info['price'] = price_matches[0]
                    break
            
            if 'price' not in info:
                info['price'] = ""
            
            # 提取描述信息（尝试从meta description）
            desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', content, re.IGNORECASE)
            if desc_match:
                description = desc_match.group(1).strip()
                if len(description) > 200:
                    description = description[:200] + "..."
                info['description'] = description
            else:
                info['description'] = ""
            
            return info
            
        except Exception as e:
            self.logger.error(f"提取页面信息失败: {e}")
            raise Exception(f"页面信息提取失败: {str(e)}")
    
    async def _show_smart_add_preview(self, message, context: ContextTypes.DEFAULT_TYPE) -> None:
        """显示智能添加预览"""
        edit_data = context.user_data['edit_data']
        url = context.user_data['url']
        
        preview_text = (
            "🤖 **智能识别结果**\n\n"
            f"📦 **商品名称**：{self._escape_markdown(edit_data['name'])}\n"
            f"💰 **价格信息**：{self._escape_markdown(edit_data['price']) if edit_data['price'] else '未识别'}\n"
            f"📝 **商品描述**：{self._escape_markdown(edit_data['config'][:100] + '...' if len(edit_data['config']) > 100 else edit_data['config']) if edit_data['config'] else '未识别'}\n"
            f"📡 **线路信息**：{self._escape_markdown(edit_data['network']) if edit_data['network'] else '待补充'}\n"
            f"🔗 **URL**：{url[:50]}{'...' if len(url) > 50 else ''}\n\n"
            "💡 信息准确吗？您可以编辑或直接添加"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ 直接添加", callback_data='confirm_smart_add'),
                InlineKeyboardButton("✏️ 编辑信息", callback_data='edit_smart_add')
            ],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel_add')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.edit_text(preview_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _show_edit_preview(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """显示编辑预览"""
        edit_data = context.user_data['edit_data']
        
        # 清除步骤状态
        context.user_data['step'] = None
        
        preview_text = (
            "✅ **信息已更新**\n\n"
            f"📦 **商品名称**：{self._escape_markdown(edit_data['name'])}\n"
            f"🖥️ **配置信息**：{self._escape_markdown(edit_data['config'])}\n"
            f"💰 **价格信息**：{self._escape_markdown(edit_data['price'])}\n"
            f"📡 **线路信息**：{self._escape_markdown(edit_data['network'])}\n\n"
            "继续编辑其他项目或确认添加："
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📦 编辑名称", callback_data='edit_field_name'),
                InlineKeyboardButton("🖥️ 编辑配置", callback_data='edit_field_config')
            ],
            [
                InlineKeyboardButton("💰 编辑价格", callback_data='edit_field_price'),
                InlineKeyboardButton("📡 编辑线路", callback_data='edit_field_network')
            ],
            [
                InlineKeyboardButton("✅ 确认添加", callback_data='confirm_smart_add'),
                InlineKeyboardButton("❌ 取消", callback_data='cancel_add')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 发送新消息而不是编辑现有消息
        await update.message.reply_text(preview_text, reply_markup=reply_markup, parse_mode='Markdown')
        """转义Markdown特殊字符"""
        if not text:
            return text
        
        # Telegram Markdown特殊字符
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /start 命令"""
        user_id = str(update.effective_user.id)
        await self._show_main_menu(update.message, user_id, edit_message=False)
    
    async def _show_main_menu(self, message_or_query, user_id: str, edit_message: bool = False) -> None:
        """显示主菜单（通用方法）"""
        is_admin = self._check_admin_permission(user_id)
        
        # 根据权限显示不同的按钮
        if is_admin:
            keyboard = [
                [
                    InlineKeyboardButton("📝 查看监控列表", callback_data='list_items'),
                    InlineKeyboardButton("➕ 添加监控", callback_data='add_item')
                ],
                [
                    InlineKeyboardButton("📊 系统状态", callback_data='status'),
                    InlineKeyboardButton("❓ 帮助", callback_data='help')
                ]
            ]
        else:
            keyboard = [
                [
                    InlineKeyboardButton("📝 查看监控列表", callback_data='list_items'),
                    InlineKeyboardButton("📊 系统状态", callback_data='status')
                ],
                [InlineKeyboardButton("❓ 帮助", callback_data='help')]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            "👋 欢迎使用 VPS 监控机器人！\n\n"
            "🔍 主要功能：\n"
            "• 实时监控VPS库存状态\n"
            "• 智能检测商品上架\n"
            "• 即时通知库存变化\n"
            "• 🆕 智能链接识别添加\n\n"
            "📱 快速操作："
        )
        
        if not is_admin and self.config.admin_ids:
            welcome_text += "\n\n⚠️ 注意：您没有管理员权限，只能查看监控列表和系统状态"
        
        if edit_message:
            # 编辑现有消息（用于回调）
            await message_or_query.edit_message_text(welcome_text, reply_markup=reply_markup)
        else:
            # 发送新消息（用于命令）
            await message_or_query.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /help 命令"""
        user_id = str(update.effective_user.id)
        is_admin = self._check_admin_permission(user_id)
        
        help_text = (
            "🤖 VPS监控机器人使用说明\n\n"
            "📝 主要命令：\n"
            "/start - 显示主菜单\n"
            "/list - 查看监控列表\n"
            "/status - 查看系统状态\n"
            "/help - 显示帮助信息\n"
        )
        
        if is_admin:
            help_text += (
                "/add - 添加监控商品\n\n"
                "🎯 **添加方式**：\n"
                "1️⃣ **智能添加**（推荐）\n"
                "• 直接发送商品链接\n"
                "• 自动识别商品信息\n"
                "• 可编辑识别结果\n\n"
                "2️⃣ **手动添加**\n"
                "• 逐步输入商品信息\n"
                "• 完全自定义内容\n\n"
                "✏️ **编辑功能**：\n"
                "• 智能识别后可编辑任何字段\n"
                "• 支持修改名称、配置、价格、线路\n\n"
            )
        else:
            help_text += "\n"
        
        help_text += (
            "🔄 **监控逻辑**：\n"
            "• 智能检测库存状态变化\n"
            f"• 每{self.config.notification_aggregation_interval//60}分钟聚合补货通知\n"
            f"• 单个商品{self.config.notification_cooldown//60}分钟内最多通知一次\n"
            "• 支持多种电商平台\n\n"
            "🔧 **功能特性**：\n"
            "• 🔄 手动检查单个商品\n"
            "• 📊 系统状态统计\n"
            "• 🛠️ 批量管理操作\n"
            "• 🤖 智能链接识别\n\n"
            "💡 **使用提示**：\n"
            "• 直接发送链接最快捷\n"
            "• 确保URL格式正确\n"
            "• 支持主流VPS提供商"
        )
        
        # 添加返回主菜单按钮
        keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(help_text, reply_markup=reply_markup)
    
    async def _list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /list 命令"""
        await self._show_monitor_list(update.message)
    
    async def _add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /add 命令"""
        user_id = str(update.effective_user.id)
        if not self._check_admin_permission(user_id):
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "❌ 抱歉，只有管理员才能添加监控项目",
                reply_markup=reply_markup
            )
            return
        
        context.user_data.clear()
        context.user_data['adding_item'] = True
        context.user_data['step'] = 'name'
        
        # 添加取消按钮
        keyboard = [[InlineKeyboardButton("❌ 取消添加", callback_data='cancel_add')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📝 添加新的监控商品\n\n"
            "请输入商品名称：\n"
            "（例如：Racknerd 2G VPS）",
            reply_markup=reply_markup
        )
    
    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /status 命令"""
        items = self.data_manager.monitor_items
        total_items = len(items)
        
        if total_items == 0:
            status_text = "📊 系统状态\n\n❌ 当前没有监控的商品"
        else:
            # 统计状态
            in_stock = sum(1 for item in items.values() if item.status is True)
            out_of_stock = sum(1 for item in items.values() if item.status is False)
            unknown = sum(1 for item in items.values() if item.status is None)
            
            # 最近检查时间
            recent_checks = []
            for item in items.values():
                if item.last_checked:
                    try:
                        check_time = datetime.fromisoformat(item.last_checked)
                        recent_checks.append(check_time)
                    except:
                        pass
            
            last_check_text = "无"
            if recent_checks:
                latest_check = max(recent_checks)
                last_check_text = latest_check.strftime('%m-%d %H:%M')
            
            status_text = (
                "📊 系统状态\n\n"
                f"📦 监控商品：{total_items} 个\n"
                f"🟢 有货：{in_stock} 个\n"
                f"🔴 无货：{out_of_stock} 个\n"
                f"⚪ 未知：{unknown} 个\n\n"
                f"🕐 最后检查：{last_check_text}\n"
                f"⏱️ 检查间隔：{self.config.check_interval}秒\n"
                f"🔔 通知间隔：{self.config.notification_aggregation_interval}秒"
            )
        
        # 添加返回主菜单按钮
        keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(status_text, reply_markup=reply_markup)
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理文本消息"""
        text = update.message.text.strip()
        user_id = update.effective_user.id
        
        # 记录消息处理信息
        self.logger.info(f"处理消息 - 用户: {user_id}, 内容: {text[:50]}{'...' if len(text) > 50 else ''}")
        self.logger.info(f"用户状态 - adding_item: {context.user_data.get('adding_item')}, step: {context.user_data.get('step')}, smart_add: {context.user_data.get('smart_add')}")
        
        # 检查是否是URL链接（智能添加功能）
        if self._is_url_link(text) and not context.user_data.get('adding_item'):
            await self._handle_url_share(update, context, text)
            return
        
        # 如果不是在添加流程中，显示帮助信息
        if not context.user_data.get('adding_item') and not context.user_data.get('step'):
            keyboard = [
                [InlineKeyboardButton("🏠 主菜单", callback_data='main_menu')],
                [InlineKeyboardButton("➕ 添加监控", callback_data='add_item')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "💡 **智能识别功能**\n\n"
                "🔗 直接发送链接：自动获取商品信息\n"
                "📝 手动添加：点击下方按钮\n\n"
                "或使用 /start 查看主菜单",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        step = context.user_data.get('step')
        
        # 添加取消按钮到每个步骤（确保使用正确的回调数据）
        cancel_keyboard = [[InlineKeyboardButton("❌ 取消添加", callback_data='cancel_add')]]
        cancel_markup = InlineKeyboardMarkup(cancel_keyboard)
        
        # 手动添加流程
        if context.user_data.get('adding_item'):
            if step == 'name':
                context.user_data['name'] = text
                context.user_data['step'] = 'config'
                await update.message.reply_text(
                    f"✅ 商品名称：{text}\n\n"
                    "请输入配置信息：\n"
                    "（例如：2GB RAM, 20GB SSD, 1TB/月）",
                    reply_markup=cancel_markup
                )
            
            elif step == 'config':
                context.user_data['config'] = text
                context.user_data['step'] = 'price'
                await update.message.reply_text(
                    f"✅ 配置信息：{text}\n\n"
                    "请输入价格信息：\n"
                    "（例如：$36.00 / 年付）",
                    reply_markup=cancel_markup
                )
            
            elif step == 'price':
                context.user_data['price'] = text
                context.user_data['step'] = 'network'
                await update.message.reply_text(
                    f"✅ 价格信息：{text}\n\n"
                    "请输入线路信息：\n"
                    "（例如：优化线路 #9929 & #CMIN2）",
                    reply_markup=cancel_markup
                )
            
            elif step == 'network':
                context.user_data['network'] = text
                context.user_data['step'] = 'url'
                await update.message.reply_text(
                    f"✅ 线路信息：{text}\n\n"
                    "请输入监控URL：\n"
                    "（必须以 http:// 或 https:// 开头）",
                    reply_markup=cancel_markup
                )
            
            elif step == 'url':
                await self._process_new_monitor_item(update, context, text)
        
        # 编辑模式处理
        elif context.user_data.get('smart_add') and step and step.startswith('edit_'):
            field_name = step.replace('edit_', '')
            if field_name in ['name', 'config', 'price', 'network']:
                context.user_data['edit_data'][field_name] = text
                await self._show_edit_preview(update, context)
            else:
                self.logger.warning(f"未知的编辑字段: {field_name}")
        
        else:
            # 未知状态，提供帮助
            self.logger.warning(f"用户 {user_id} 处于未知状态 - {context.user_data}")
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "❓ 状态异常，请重新开始\n\n"
                "使用 /start 返回主菜单",
                reply_markup=reply_markup
            )
    
    def _is_valid_url(self, url: str) -> Tuple[bool, str]:
        """验证URL格式"""
        if not url:
            return False, "URL不能为空"
        
        if not url.startswith(('http://', 'https://')):
            return False, "URL必须以 http:// 或 https:// 开头"
        
        # 基本的URL格式验证
        try:
            parsed = urllib.parse.urlparse(url)
            if not parsed.netloc:
                return False, "URL格式无效，缺少域名"
            
            # 检查是否为常见的无效URL
            invalid_domains = ['localhost', '127.0.0.1', '0.0.0.0']
            if parsed.netloc.lower() in invalid_domains:
                return False, "不支持本地地址"
                
            return True, ""
        except Exception:
            return False, "URL格式无效"
    
    async def _process_new_monitor_item(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
        """处理新的监控项"""
        # 验证URL
        is_valid, error_msg = self._is_valid_url(url)
        if not is_valid:
            cancel_keyboard = [[InlineKeyboardButton("❌ 取消添加", callback_data='cancel_add')]]
            cancel_markup = InlineKeyboardMarkup(cancel_keyboard)
            await update.message.reply_text(
                f"❌ {error_msg}",
                reply_markup=cancel_markup
            )
            return
        
        name = context.user_data['name']
        config = context.user_data.get('config', '')
        price = context.user_data.get('price', '')
        network = context.user_data.get('network', '')
        
        # 检查是否已存在
        if self.data_manager.get_monitor_item_by_url(url):
            keyboard = [
                [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')],
                [InlineKeyboardButton("➕ 重新添加", callback_data='add_item')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "❌ 该URL已在监控列表中！",
                reply_markup=reply_markup
            )
            context.user_data.clear()
            return
        
        processing_msg = await update.message.reply_text("⏳ 正在添加并检查状态...")
        
        try:
            # 添加到数据库
            item_id = self.data_manager.add_monitor_item(name, url, config, price, network)
            await self.data_manager.save_monitor_items()
            
            # 立即检查状态
            # 直接创建 StockChecker 实例
            stock_checker = StockChecker(self.config)
            stock_available, error = await stock_checker.check_stock(url)
            
            if error:
                status_text = f"❗ 检查状态时出错: {error}"
            else:
                status = "🟢 有货" if stock_available else "🔴 无货"
                status_text = f"📊 当前状态: {status}"
                self.data_manager.update_monitor_item_status(url, stock_available, 0)
                await self.data_manager.save_monitor_items()
            
            success_text = (
                f"✅ 已添加监控商品\n\n"
                f"📦 名称：{name}\n"
                f"💰 价格：{price}\n"
                f"🖥️ 配置：{config}\n"
                f"📡 线路：{network}\n"
                f"🔗 URL：{url}\n"
                f"\n{status_text}"
            )
            
            # 添加操作按钮
            keyboard = [
                [InlineKeyboardButton("📝 查看列表", callback_data='list_items')],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await processing_msg.edit_text(success_text, reply_markup=reply_markup)
            
        except Exception as e:
            keyboard = [
                [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')],
                [InlineKeyboardButton("➕ 重新添加", callback_data='add_item')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await processing_msg.edit_text(
                f"❌ 添加失败: {str(e)}",
                reply_markup=reply_markup
            )
            self.logger.error(f"添加监控项失败: {e}")
        
        finally:
            context.user_data.clear()
    
    async def _handle_confirm_smart_add_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理确认智能添加回调"""
        try:
            edit_data = context.user_data.get('edit_data', {})
            url = context.user_data.get('url', '')
            
            if not edit_data or not url:
                raise Exception("数据丢失，请重新添加")
            
            # 更新处理状态
            await update.callback_query.edit_message_text("⏳ 正在添加并检查状态...")
            
            # 添加到数据库
            item_id = self.data_manager.add_monitor_item(
                name=edit_data['name'],
                url=url,
                config=edit_data['config'],
                price=edit_data['price'],
                network=edit_data['network']
            )
            await self.data_manager.save_monitor_items()
            
            # 立即检查状态
            # 直接创建 StockChecker 实例
            stock_checker = StockChecker(self.config)
            stock_available, error = await stock_checker.check_stock(url)
            
            if error:
                status_text = f"❗ 检查状态时出错: {error}"
            else:
                status = "🟢 有货" if stock_available else "🔴 无货"
                status_text = f"📊 当前状态: {status}"
                self.data_manager.update_monitor_item_status(url, stock_available, 0)
                await self.data_manager.save_monitor_items()
            
            success_text = (
                f"✅ **智能添加成功**\n\n"
                f"📦 名称：{self._escape_markdown(edit_data['name'])}\n"
                f"💰 价格：{self._escape_markdown(edit_data['price'])}\n"
                f"🖥️ 配置：{self._escape_markdown(edit_data['config'])}\n"
                f"📡 线路：{self._escape_markdown(edit_data['network'])}\n"
                f"🔗 URL：{url[:50]}{'...' if len(url) > 50 else ''}\n"
                f"\n{status_text}"
            )
            
            keyboard = [
                [InlineKeyboardButton("📝 查看列表", callback_data='list_items')],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                success_text, 
                reply_markup=reply_markup, 
                parse_mode='Markdown'
            )
            
        except Exception as e:
            self.logger.error(f"智能添加失败: {e}")
            keyboard = [
                [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')],
                [InlineKeyboardButton("➕ 重新添加", callback_data='add_item')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                f"❌ 添加失败: {str(e)}",
                reply_markup=reply_markup
            )
        finally:
            context.user_data.clear()
    
    async def _handle_edit_smart_add_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理编辑智能添加回调"""
        edit_data = context.user_data.get('edit_data', {})
        
        if not edit_data:
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                "❌ 数据丢失，请重新添加",
                reply_markup=reply_markup
            )
            return
        
        preview_text = (
            "✏️ **编辑商品信息**\n\n"
            f"📦 **商品名称**：{self._escape_markdown(edit_data['name'])}\n"
            f"🖥️ **配置信息**：{self._escape_markdown(edit_data['config'])}\n"
            f"💰 **价格信息**：{self._escape_markdown(edit_data['price'])}\n"
            f"📡 **线路信息**：{self._escape_markdown(edit_data['network'])}\n\n"
            "请选择要编辑的项目："
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📦 编辑名称", callback_data='edit_field_name'),
                InlineKeyboardButton("🖥️ 编辑配置", callback_data='edit_field_config')
            ],
            [
                InlineKeyboardButton("💰 编辑价格", callback_data='edit_field_price'),
                InlineKeyboardButton("📡 编辑线路", callback_data='edit_field_network')
            ],
            [
                InlineKeyboardButton("✅ 确认添加", callback_data='confirm_smart_add'),
                InlineKeyboardButton("❌ 取消", callback_data='cancel_add')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            preview_text, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )
    
    async def _handle_edit_field_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, field_name: str) -> None:
        """处理编辑字段回调"""
        field_names = {
            'name': ('商品名称', '📦', '例如：Racknerd 2G VPS'),
            'config': ('配置信息', '🖥️', '例如：2GB RAM, 20GB SSD, 1TB/月'),
            'price': ('价格信息', '💰', '例如：$36.00 / 年付'),
            'network': ('线路信息', '📡', '例如：优化线路 #9929 & #CMIN2')
        }
        
        if field_name not in field_names:
            await update.callback_query.answer("❌ 无效的字段")
            return
        
        display_name, emoji, example = field_names[field_name]
        
        # 设置编辑状态
        context.user_data['step'] = f'edit_{field_name}'
        
        # 获取当前值
        current_value = context.user_data.get('edit_data', {}).get(field_name, '')
        current_text = f"\n\n当前值：{current_value}" if current_value else ""
        
        edit_text = (
            f"✏️ **编辑{display_name}**\n\n"
            f"{emoji} 请输入新的{display_name}：\n"
            f"💡 {example}{current_text}"
        )
        
        keyboard = [[InlineKeyboardButton("❌ 取消编辑", callback_data='edit_smart_add')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            edit_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理回调查询（优化版）"""
        query = update.callback_query
        
        try:
            # 先回答回调查询，防止按钮卡住
            await query.answer()
            
            # 记录回调数据用于调试
            self.logger.info(f"处理回调: {query.data} - 用户: {update.effective_user.id}")
            
            # 创建一个临时的消息对象用于统一接口
            message = query.message
            
            # 处理各种回调
            if query.data == 'main_menu':
                await self._handle_main_menu_callback(update, context)
            elif query.data == 'list_items':
                await self._show_monitor_list(message)
            elif query.data == 'add_item':
                await self._handle_add_item_callback(update, context)
            elif query.data == 'manual_add':
                await self._handle_manual_add_callback(update, context)
            elif query.data == 'help':
                await self._handle_help_callback(update, context)
            elif query.data == 'status':
                await self._handle_status_callback(update, context)
            elif query.data == 'cancel_add':
                # 确保清除添加状态
                context.user_data.clear()
                await self._handle_cancel_add_callback(update, context)
            elif query.data == 'confirm_smart_add':
                await self._handle_confirm_smart_add_callback(update, context)
            elif query.data == 'edit_smart_add':
                # 返回到编辑预览，不清除数据
                await self._handle_edit_smart_add_callback(update, context)
            elif query.data.startswith('edit_field_'):
                field_name = query.data.replace('edit_field_', '')
                await self._handle_edit_field_callback(update, context, field_name)
            elif query.data == 'check_all':
                await self._handle_check_all_callback(update, context)
            elif query.data == 'manage_items':
                await self._handle_manage_items_callback(update, context)
            elif query.data == 'bulk_delete':
                await self._handle_bulk_delete_callback(update, context)
            elif query.data in ['delete_no_stock', 'delete_unknown', 'delete_all_confirm']:
                await self._handle_bulk_delete_action(update, context, query.data)
            elif query.data.startswith('delete_'):
                url = query.data[7:]
                await self._delete_monitor_item(message, url)
            elif query.data.startswith('check_'):
                url = query.data[6:]
                await self._manual_check_item(message, url)
            else:
                self.logger.warning(f"未处理的回调: {query.data}")
                await query.message.reply_text("❌ 未知的操作，请重试或返回主菜单")
                
        except Exception as e:
            self.logger.error(f"处理回调失败: {query.data} - {e}", exc_info=True)
            
            # 提供更详细的错误信息和恢复选项
            if "has no attribute" in str(e):
                error_text = f"❌ 系统错误: 缺少处理方法\n\n💡 请联系管理员或重启程序"
            elif "Markdown" in str(e):
                error_text = f"❌ 消息格式错误\n\n💡 请重试操作"
            elif "timeout" in str(e).lower():
                error_text = f"❌ 网络超时\n\n💡 请稍后重试"
            elif "permission" in str(e).lower() or "forbidden" in str(e).lower():
                error_text = f"❌ 权限不足\n\n💡 请检查机器人权限"
            else:
                error_text = f"❌ 操作失败: {str(e)}\n\n💡 请重试或联系管理员"
            
            keyboard = [
                [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')],
                [InlineKeyboardButton("📊 系统状态", callback_data='status')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.message.reply_text(error_text, reply_markup=reply_markup)
            except Exception as e2:
                # 如果连发送错误消息都失败了，至少记录日志
                self.logger.error(f"发送错误消息也失败了: {e2}")
                try:
                    await query.answer("❌ 操作失败，请重试")
                except:
                    pass
    
    async def _handle_main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理返回主菜单回调"""
        # 清除用户数据
        context.user_data.clear()
        
        user_id = str(update.effective_user.id)
        await self._show_main_menu(update.callback_query, user_id, edit_message=True)
    
    async def _handle_add_item_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理添加商品回调"""
        user_id = str(update.effective_user.id)
        if not self._check_admin_permission(user_id):
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                "❌ 抱歉，只有管理员才能添加监控项目",
                reply_markup=reply_markup
            )
            return
        
        context.user_data.clear()
        context.user_data['adding_item'] = True
        context.user_data['step'] = 'name'
        
        keyboard = [[InlineKeyboardButton("❌ 取消添加", callback_data='cancel_add')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "📝 添加新的监控商品\n\n"
            "请输入商品名称：\n"
            "（例如：Racknerd 2G VPS）",
            reply_markup=reply_markup
        )
    
    async def _handle_help_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理帮助回调"""
        user_id = str(update.effective_user.id)
        is_admin = self._check_admin_permission(user_id)
        
        help_text = (
            "🤖 VPS监控机器人使用说明\n\n"
            "📝 主要命令：\n"
            "/start - 显示主菜单\n"
            "/list - 查看监控列表\n"
            "/status - 查看系统状态\n"
            "/help - 显示帮助信息\n"
        )
        
        if is_admin:
            help_text += (
                "/add - 添加监控商品\n\n"
                "➕ 添加流程：\n"
                "1. 输入商品名称\n"
                "2. 输入配置信息\n"
                "3. 输入价格信息\n"
                "4. 输入线路信息\n"
                "5. 输入监控URL\n\n"
            )
        else:
            help_text += "\n"
        
        help_text += (
            "🔄 监控逻辑：\n"
            "• 智能检测库存状态变化\n"
            f"• 每{self.config.notification_aggregation_interval//60}分钟聚合补货通知\n"
            f"• 单个商品{self.config.notification_cooldown//60}分钟内最多通知一次\n"
            "• 支持多种电商平台\n\n"
            "💡 提示：确保URL格式正确（包含http://或https://）"
        )
        
        keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(help_text, reply_markup=reply_markup)
    
    async def _handle_status_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理状态查询回调"""
        items = self.data_manager.monitor_items
        total_items = len(items)
        
        if total_items == 0:
            status_text = "📊 系统状态\n\n❌ 当前没有监控的商品"
        else:
            # 统计状态
            in_stock = sum(1 for item in items.values() if item.status is True)
            out_of_stock = sum(1 for item in items.values() if item.status is False)
            unknown = sum(1 for item in items.values() if item.status is None)
            
            # 最近检查时间
            recent_checks = []
            for item in items.values():
                if item.last_checked:
                    try:
                        check_time = datetime.fromisoformat(item.last_checked)
                        recent_checks.append(check_time)
                    except:
                        pass
            
            last_check_text = "无"
            if recent_checks:
                latest_check = max(recent_checks)
                last_check_text = latest_check.strftime('%m-%d %H:%M')
            
            status_text = (
                "📊 系统状态\n\n"
                f"📦 监控商品：{total_items} 个\n"
                f"🟢 有货：{in_stock} 个\n"
                f"🔴 无货：{out_of_stock} 个\n"
                f"⚪ 未知：{unknown} 个\n\n"
                f"🕐 最后检查：{last_check_text}\n"
                f"⏱️ 检查间隔：{self.config.check_interval}秒\n"
                f"🔔 通知间隔：{self.config.notification_aggregation_interval}秒"
            )
        
        keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(status_text, reply_markup=reply_markup)
    
    async def _handle_cancel_add_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理取消添加回调"""
        context.user_data.clear()
        
        keyboard = [
            [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')],
            [InlineKeyboardButton("➕ 重新添加", callback_data='add_item')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
    
    async def _handle_check_all_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理全部检查回调"""
        items = self.data_manager.monitor_items
        if not items:
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                "❌ 没有监控商品需要检查",
                reply_markup=reply_markup
            )
            return
        
        # 显示检查进度
        progress_text = f"🔄 开始检查 {len(items)} 个商品...\n\n进度：0/{len(items)}"
        await update.callback_query.edit_message_text(progress_text)
        
        checked_count = 0
        results = []
        
        for item in items.values():
            try:
                # 更新进度
                checked_count += 1
                progress_text = f"🔄 正在检查商品...\n\n进度：{checked_count}/{len(items)}\n当前：{item.name}"
                await update.callback_query.edit_message_text(progress_text)
                
                # 执行检查
                # 直接创建 StockChecker 实例  
                stock_checker = StockChecker(self.config)
                stock_available, error = await stock_checker.check_stock(item.url)
                
                if error:
                    results.append(f"❗ {item.name}: {error}")
                else:
                    status_emoji = "🟢" if stock_available else "🔴"
                    status_text = "有货" if stock_available else "无货"
                    results.append(f"{status_emoji} {item.name}: {status_text}")
                    
                    # 更新数据库
                    self.data_manager.update_monitor_item_status(item.url, stock_available)
                
            except Exception as e:
                results.append(f"❌ {item.name}: 检查失败")
                self.logger.error(f"批量检查失败 {item.url}: {e}")
        
        # 保存数据
        await self.data_manager.save_monitor_items()
        
        # 显示结果
        result_text = "✅ **批量检查完成**\n\n"
        result_text += "\n".join(results[:10])  # 最多显示10个结果
        
        if len(results) > 10:
            result_text += f"\n\n... 还有 {len(results) - 10} 个结果"
        
        keyboard = [
            [InlineKeyboardButton("📝 查看列表", callback_data='list_items')],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            result_text, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )
    
    async def _handle_manage_items_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理管理商品回调"""
        user_id = str(update.effective_user.id)
        if not self._check_admin_permission(user_id):
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                "❌ 只有管理员才能管理商品",
                reply_markup=reply_markup
            )
            return
        
        items = self.data_manager.monitor_items
        if not items:
            keyboard = [
                [InlineKeyboardButton("➕ 添加商品", callback_data='add_item')],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                "📝 当前没有监控商品\n\n"
                "💡 直接发送链接即可智能添加",
                reply_markup=reply_markup
            )
            return
        
        # 显示商品管理界面
        manage_text = f"🛠️ **商品管理** ({len(items)} 个)\n\n"
        
        # 列出所有商品（简化显示）
        for i, item in enumerate(items.values(), 1):
            status_emoji = "⚪" if item.status is None else ("🟢" if item.status else "🔴")
            manage_text += f"{i}\\. {status_emoji} {self._escape_markdown(item.name)}\n"
            if len(manage_text) > 3000:  # 避免消息过长
                manage_text += "\\.\\.\\.\n"
                break
        
        manage_text += "\n💡 选择操作："
        
        keyboard = [
            [InlineKeyboardButton("➕ 添加商品", callback_data='add_item')],
            [InlineKeyboardButton("🗑️ 批量删除", callback_data='bulk_delete')],
            [InlineKeyboardButton("📝 查看详情", callback_data='list_items')],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            manage_text, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )
    
    async def _handle_bulk_delete_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理批量删除回调"""
        user_id = str(update.effective_user.id)
        if not self._check_admin_permission(user_id):
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                "❌ 只有管理员才能删除商品",
                reply_markup=reply_markup
            )
            return
        
        items = self.data_manager.monitor_items
        if not items:
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                "❌ 没有商品可以删除",
                reply_markup=reply_markup
            )
            return
        
        # 按状态分类显示
        no_stock_items = [item for item in items.values() if item.status is False]
        unknown_items = [item for item in items.values() if item.status is None]
        
        delete_text = f"🗑️ **批量删除** ({len(items)} 个商品)\n\n"
        delete_text += "⚠️ **危险操作**：删除后无法恢复！\n\n"
        delete_text += "选择要删除的类型："
        
        keyboard = []
        
        if no_stock_items:
            keyboard.append([InlineKeyboardButton(f"🔴 删除无货商品 ({len(no_stock_items)}个)", callback_data='delete_no_stock')])
        
        if unknown_items:
            keyboard.append([InlineKeyboardButton(f"⚪ 删除未知状态 ({len(unknown_items)}个)", callback_data='delete_unknown')])
        
        keyboard.extend([
            [InlineKeyboardButton("❌ 删除全部商品", callback_data='delete_all_confirm')],
            [InlineKeyboardButton("↩️ 返回管理", callback_data='manage_items')],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(
            delete_text, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )
    
    async def _handle_bulk_delete_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
        """处理批量删除操作"""
        user_id = str(update.effective_user.id)
        if not self._check_admin_permission(user_id):
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                "❌ 只有管理员才能删除商品",
                reply_markup=reply_markup
            )
            return
        
        items = self.data_manager.monitor_items
        deleted_count = 0
        deleted_names = []
        
        try:
            if action == 'delete_no_stock':
                # 删除无货商品
                to_delete = [item for item in items.values() if item.status is False]
                for item in to_delete:
                    if self.data_manager.remove_monitor_item(item.url):
                        deleted_count += 1
                        deleted_names.append(item.name)
                result_text = f"✅ 已删除 {deleted_count} 个无货商品"
                
            elif action == 'delete_unknown':
                # 删除状态未知商品
                to_delete = [item for item in items.values() if item.status is None]
                for item in to_delete:
                    if self.data_manager.remove_monitor_item(item.url):
                        deleted_count += 1
                        deleted_names.append(item.name)
                result_text = f"✅ 已删除 {deleted_count} 个状态未知商品"
                
            elif action == 'delete_all_confirm':
                # 删除所有商品
                to_delete = list(items.values())
                for item in to_delete:
                    if self.data_manager.remove_monitor_item(item.url):
                        deleted_count += 1
                        deleted_names.append(item.name)
                result_text = f"✅ 已删除全部 {deleted_count} 个商品"
            
            # 保存更改
            await self.data_manager.save_monitor_items()
            
            if deleted_names:
                result_text += f"\n\n删除的商品：\n"
                result_text += "\n".join([f"• {self._escape_markdown(name)}" for name in deleted_names[:10]])
                if len(deleted_names) > 10:
                    result_text += f"\n\\.\\.\\. 还有 {len(deleted_names) - 10} 个"
            
        except Exception as e:
            self.logger.error(f"批量删除失败: {e}")
            result_text = f"❌ 批量删除失败: {str(e)}"
        
        keyboard = [
            [InlineKeyboardButton("📝 查看列表", callback_data='list_items')],
            [InlineKeyboardButton("🛠️ 继续管理", callback_data='manage_items')],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            result_text,
            reply_markup=reply_markup
        )
    
    async def _show_monitor_list(self, message) -> None:
        """显示监控列表（优化版）"""
        items = self.data_manager.monitor_items
        if not items:
            if not self.config.admin_ids or str(message.chat.id) in self.config.admin_ids:
                help_text = (
                    "📝 当前没有监控的商品\n\n"
                    "🎯 **添加方式**：\n"
                    "🔗 直接发送链接（智能识别）\n"
                    "📝 手动添加（完全自定义）"
                )
                keyboard = [
                    [InlineKeyboardButton("➕ 添加商品", callback_data='add_item')],
                    [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
                ]
            else:
                help_text = "📝 当前没有监控的商品"
                keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(help_text, reply_markup=reply_markup)
            return
        
        # 如果商品数量较少（<=3个），分别显示详细信息
        if len(items) <= 3:
            await self._show_detailed_list(message, items)
        else:
            # 商品数量较多时，显示简化列表
            await self._show_compact_list(message, items)
    
    async def _show_detailed_list(self, message, items: Dict[str, MonitorItem]) -> None:
        """显示详细的监控列表（商品较少时）"""
        # 发送总览信息
        overview_text = f"📝 当前监控 {len(items)} 个商品："
        keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(overview_text, reply_markup=reply_markup)
        
        # 分别发送每个商品的详细信息
        for item in items.values():
            # 创建每个商品的操作按钮
            buttons = []
            
            # 检查按钮（所有用户都可以使用）
            buttons.append(InlineKeyboardButton("🔄 检查", callback_data=f'check_{item.url}'))
            
            # 删除按钮（仅管理员可用）
            if not self.config.admin_ids or str(message.chat.id) in self.config.admin_ids:
                buttons.append(InlineKeyboardButton("🗑️ 删除", callback_data=f'delete_{item.url}'))
            
            # 按钮布局 - 添加返回主菜单按钮
            keyboard = [buttons]
            keyboard.append([InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # 构建状态显示
            status_emoji = "⚪" if item.status is None else ("🟢" if item.status else "🔴")
            status_text = "未检查" if item.status is None else ("有货" if item.status else "无货")
            
            item_text = f"📦 **{self._escape_markdown(item.name)}**\n📊 状态：{status_emoji} {status_text}"
            
            if item.config:
                item_text += f"\n⚙️ 配置：{self._escape_markdown(item.config)}"
            if item.price:
                item_text += f"\n💰 价格：{self._escape_markdown(item.price)}"
            if item.network:
                item_text += f"\n📡 线路：{self._escape_markdown(item.network)}"
            
            if item.last_checked:
                try:
                    check_time = datetime.fromisoformat(item.last_checked)
                    item_text += f"\n🕒 最后检查：{check_time.strftime('%m-%d %H:%M')}"
                except:
                    pass
            
            item_text += f"\n🔗 {item.url[:50]}{'...' if len(item.url) > 50 else ''}"
            
            await message.reply_text(item_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _show_compact_list(self, message, items: Dict[str, MonitorItem]) -> None:
        """显示紧凑的监控列表（商品较多时）"""
        # 统计信息
        in_stock = sum(1 for item in items.values() if item.status is True)
        out_of_stock = sum(1 for item in items.values() if item.status is False)
        unknown = sum(1 for item in items.values() if item.status is None)
        
        # 构建列表文本
        list_text = (
            f"📝 **监控列表** ({len(items)} 个商品)\n\n"
            f"📊 **统计**：🟢 {in_stock} 有货 | 🔴 {out_of_stock} 无货 | ⚪ {unknown} 未知\n\n"
        )
        
        # 按状态分组显示
        has_stock_items = [item for item in items.values() if item.status is True]
        no_stock_items = [item for item in items.values() if item.status is False]
        unknown_items = [item for item in items.values() if item.status is None]
        
        if has_stock_items:
            list_text += "🟢 **有货商品**：\n"
            for item in has_stock_items:
                list_text += f"• {self._escape_markdown(item.name)}"
                if item.price:
                    list_text += f" ({self._escape_markdown(item.price)})"
                list_text += "\n"
            list_text += "\n"
        
        if no_stock_items:
            list_text += "🔴 **无货商品**：\n"
            for item in no_stock_items:
                list_text += f"• {self._escape_markdown(item.name)}"
                if item.price:
                    list_text += f" ({self._escape_markdown(item.price)})"
                list_text += "\n"
            list_text += "\n"
        
        if unknown_items:
            list_text += "⚪ **状态未知**：\n"
            for item in unknown_items:
                list_text += f"• {self._escape_markdown(item.name)}"
                if item.price:
                    list_text += f" ({self._escape_markdown(item.price)})"
                list_text += "\n"
            list_text += "\n"
        
        list_text += "💡 使用下方按钮进行详细操作"
        
        # 创建操作按钮
        keyboard = [
            [InlineKeyboardButton("🔄 全部检查", callback_data='check_all')],
            [InlineKeyboardButton("📊 系统状态", callback_data='status')],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
        ]
        
        # 如果是管理员，添加管理按钮
        if not self.config.admin_ids or str(message.chat.id) in self.config.admin_ids:
            keyboard.insert(1, [InlineKeyboardButton("🛠️ 管理商品", callback_data='manage_items')])
            keyboard.insert(1, [InlineKeyboardButton("➕ 添加商品", callback_data='add_item')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(list_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _delete_monitor_item(self, message, url: str) -> None:
        """删除监控项（优化版）"""
        try:
            item = self.data_manager.get_monitor_item_by_url(url)
            if not item:
                keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await message.reply_text(
                    "❌ 未找到该监控项",
                    reply_markup=reply_markup
                )
                return
            
            if self.data_manager.remove_monitor_item(url):
                await self.data_manager.save_monitor_items()
                keyboard = [
                    [InlineKeyboardButton("📝 查看列表", callback_data='list_items')],
                    [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await message.reply_text(
                    f"✅ 已删除监控：{item.name}",
                    reply_markup=reply_markup
                )
            else:
                keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await message.reply_text(
                    "❌ 删除失败",
                    reply_markup=reply_markup
                )
        except Exception as e:
            self.logger.error(f"删除监控项失败: {e}")
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(
                "❌ 删除失败",
                reply_markup=reply_markup
            )
    
    async def _manual_check_item(self, message, url: str) -> None:
        """手动检查单个商品（新功能）"""
        try:
            item = self.data_manager.get_monitor_item_by_url(url)
            if not item:
                keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await message.reply_text(
                    "❌ 未找到该监控项",
                    reply_markup=reply_markup
                )
                return
            
            # 发送检查中的消息
            checking_msg = await message.reply_text(f"🔄 正在检查 {item.name}...")
            
            # 执行检查
            # 直接创建 StockChecker 实例
            stock_checker = StockChecker(self.config)
            stock_available, error = await stock_checker.check_stock(url)
            
            if error:
                result_text = f"❗ 检查失败: {error}"
                status_emoji = "⚠️"
            else:
                status_emoji = "🟢" if stock_available else "🔴"
                status_text = "有货" if stock_available else "无货"
                result_text = f"📊 当前状态: {status_emoji} {status_text}"
                
                # 更新数据库
                self.data_manager.update_monitor_item_status(url, stock_available)
                await self.data_manager.save_monitor_items()
            
            final_text = (
                f"📦 {item.name}\n"
                f"🔗 {url}\n"
                f"{result_text}\n"
                f"🕒 检查时间: {datetime.now().strftime('%m-%d %H:%M:%S')}"
            )
            
            keyboard = [
                [InlineKeyboardButton("🔄 再次检查", callback_data=f'check_{url}')],
                [InlineKeyboardButton("📝 查看列表", callback_data='list_items')],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await checking_msg.edit_text(final_text, reply_markup=reply_markup)
            
        except Exception as e:
            self.logger.error(f"手动检查失败: {e}")
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(
                f"❌ 检查失败: {str(e)}",
                reply_markup=reply_markup
            )
    
    async def send_notification(self, message: str, parse_mode: str = None) -> None:
        """发送通知"""
        try:
            if self.app and self.app.bot:
                await self.app.bot.send_message(
                    chat_id=self.config.chat_id, 
                    text=message,
                    parse_mode=parse_mode,
                    disable_web_page_preview=False  # 允许链接预览
                )
                self.logger.info("Telegram通知发送成功")
        except Exception as e:
            self.logger.error(f"发送通知失败: {e}")
    
    async def shutdown(self) -> None:
        """关闭机器人"""
        try:
            if self.app:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
                self.logger.info("Telegram Bot已关闭")
        except Exception as e:
            self.logger.error(f"关闭机器人失败: {e}")

# ====== 主监控类 ======
class VPSMonitor:
    """主监控类"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.data_manager = DataManager()
        self.stock_checker = None
        self.telegram_bot = None
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._pending_notifications = []  # 待发送的通知
        self._last_aggregation_time = datetime.now()
    
    async def initialize(self) -> None:
        """初始化监控器"""
        try:
            print("🔧 初始化监控器...")
            
            # 加载配置和数据
            config = self.config_manager.load_config()
            print("✅ 配置文件加载成功")
            
            await self.data_manager.load_monitor_items()
            print("✅ 监控数据加载成功")
            
            # 初始化组件
            self.stock_checker = StockChecker(config)
            self.telegram_bot = TelegramBot(config, self.data_manager)
            
            # 初始化Telegram Bot
            await self.telegram_bot.initialize()
            
            self.logger.info("监控器初始化完成")
            print("✅ 监控器初始化完成")
            
        except Exception as e:
            self.logger.error(f"监控器初始化失败: {e}")
            print(f"❌ 监控器初始化失败: {e}")
            raise
    
    async def _perform_startup_check(self) -> None:
        """执行启动检查"""
        items = self.data_manager.monitor_items
        if not items:
            await self.telegram_bot.send_notification("⚠️ 当前没有监控商品，请使用 /add 添加")
            print("⚠️ 当前没有监控商品")
            return
        
        print(f"🔍 开始检查 {len(items)} 个监控项...")
        await self.telegram_bot.send_notification("🔄 正在进行启动检查...")
        
        for item in items.values():
            try:
                print(f"检查: {item.name}")
                stock_available, error = await self.stock_checker.check_stock(item.url)
                
                message = f"📦 {item.name}\n🔗 {item.url}\n"
                if item.config:
                    message += f"⚙️ 配置：{item.config}\n"
                
                if error:
                    message += f"❗ 检查失败: {error}"
                    print(f"  ❌ 检查失败: {error}")
                else:
                    status = "🟢 有货" if stock_available else "🔴 无货"
                    message += f"📊 状态：{status}"
                    print(f"  ✅ 状态：{status}")
                    self.data_manager.update_monitor_item_status(item.url, stock_available, 0)
                
                await self.telegram_bot.send_notification(message)
                
            except Exception as e:
                self.logger.error(f"启动检查失败 {item.url}: {e}")
                print(f"  ❌ 检查异常: {e}")
                continue
        
        await self.data_manager.save_monitor_items()
        await self.telegram_bot.send_notification("✅ 启动检查完成")
        print("✅ 启动检查完成")
    
    async def _monitor_loop(self) -> None:
        """主监控循环"""
        config = self.config_manager.config
        print(f"🔄 开始监控循环，检查间隔: {config.check_interval}秒")
        
        while self._running:
            try:
                items = self.data_manager.monitor_items
                if not items:
                    await asyncio.sleep(config.check_interval)
                    continue
                
                print(f"🔍 执行定期检查 ({len(items)} 个项目)")
                
                for item in items.values():
                    if not self._running:
                        break
                    
                    try:
                        stock_available, error = await self.stock_checker.check_stock(item.url)
                        
                        if error:
                            self.logger.warning(f"检查失败 {item.url}: {error}")
                            continue
                        
                        # 检查状态变化
                        previous_status = item.status
                        
                        if previous_status is None:
                            # 首次检查
                            self.data_manager.update_monitor_item_status(item.url, stock_available, 0)
                            continue
                        
                        if stock_available and not previous_status:
                            # 从无货变为有货
                            self._pending_notifications.append(item)
                            self.data_manager.update_monitor_item_status(item.url, stock_available, 
                                                                      item.notification_count + 1)
                        elif not stock_available and previous_status:
                            # 从有货变为无货
                            await self._send_status_change_notification(item, stock_available)
                            self.data_manager.update_monitor_item_status(item.url, stock_available, 0)
                        
                    except Exception as e:
                        self.logger.error(f"监控循环出错 {item.url}: {e}")
                        continue
                
                # 处理聚合通知
                await self._process_aggregated_notifications()
                
                # 保存状态
                await self.data_manager.save_monitor_items()
                await asyncio.sleep(config.check_interval)
                
            except Exception as e:
                self.logger.error(f"监控循环出错: {e}")
                await asyncio.sleep(config.retry_delay)
    
    async def _send_status_change_notification(self, item: MonitorItem, stock_available: bool) -> None:
        """发送状态变化通知（Markdown格式）"""
        if stock_available:
            # 检查是否在冷却时间内
            if item.last_notified:
                try:
                    last_notified = datetime.fromisoformat(item.last_notified)
                    cooldown_end = last_notified + timedelta(seconds=self.config.notification_cooldown)
                    if datetime.now() < cooldown_end:
                        self.logger.info(f"商品 {item.name} 在冷却时间内，跳过通知")
                        return
                except:
                    pass
            
            # 尝试获取库存信息
            stock_info = "∞ #Available" if item.stock_info else "有货"
            
            message = (
                f"📦 **{item.name}**\n\n"
                f"💰 **{item.price}**\n\n"
                f"🖥️ **配置**\n"
                f"{item.config}\n\n"
                f"📡 **线路**：{item.network}\n"
                f"🔗 [立即抢购]({item.url})\n\n"
                f"🛒 **库存**：{stock_info}"
            )
            
            await self.telegram_bot.send_notification(message, parse_mode='Markdown')
            
            # 更新最后通知时间
            item.last_notified = datetime.now().isoformat()
            
            print(f"🎉 {item.name} 现在有货！")
        else:
            # 缺货通知（简单格式）
            message = f"📦 {item.name}\n📊 状态：🔴 已经无货"
            await self.telegram_bot.send_notification(message)
            print(f"📉 {item.name} 已无货")
    
    async def _process_aggregated_notifications(self) -> None:
        """处理聚合通知"""
        if not self._pending_notifications:
            return
        
        # 检查是否到达聚合时间间隔
        time_since_last = (datetime.now() - self._last_aggregation_time).total_seconds()
        if time_since_last < self.config_manager.config.notification_aggregation_interval:
            return
        
        # 过滤在冷却时间内的商品
        notifications_to_send = []
        for item in self._pending_notifications:
            if item.last_notified:
                try:
                    last_notified = datetime.fromisoformat(item.last_notified)
                    cooldown_end = last_notified + timedelta(seconds=self.config_manager.config.notification_cooldown)
                    if datetime.now() < cooldown_end:
                        continue
                except:
                    pass
            notifications_to_send.append(item)
        
        if notifications_to_send:
            # 发送聚合通知
            message = "🎉 **补货通知** 🎉\n\n"
            for item in notifications_to_send:
                stock_info = "∞ #Available" if item.stock_info else "有货"
                message += (
                    f"📦 **{item.name}**\n"
                    f"💰 {item.price}\n"
                    f"🖥️ {item.config}\n"
                    f"📡 {item.network}\n"
                    f"🔗 [立即抢购]({item.url})\n"
                    f"🛒 库存：{stock_info}\n\n"
                )
                # 更新最后通知时间
                item.last_notified = datetime.now().isoformat()
            
            await self.telegram_bot.send_notification(message, parse_mode='Markdown')
            print(f"📮 发送了 {len(notifications_to_send)} 个商品的聚合通知")
        
        # 清空待发送列表并更新时间
        self._pending_notifications.clear()
        self._last_aggregation_time = datetime.now()
    
    async def start(self) -> None:
        """启动监控"""
        try:
            print("🚀 启动VPS监控系统 v1.0...")
            await self.initialize()
            
            # 发送启动通知
            config = self.config_manager.config
            startup_message = (
                "🚀 VPS监控程序 v1.0 已启动\n"
                f"⏰ 检查间隔：{config.check_interval}秒\n"
                f"📊 聚合间隔：{config.notification_aggregation_interval}秒\n"
                f"🕐 通知冷却：{config.notification_cooldown}秒\n\n"
                "🆕 **新功能**：\n"
                "🤖 智能链接识别和添加\n"
                "✏️ 可编辑识别结果\n"
                "🔄 手动检查功能\n"
                "🛠️ 批量管理操作\n\n"
                "💡 使用 /start 开始操作\n"
                "🔗 直接发送链接即可智能添加\n\n"
                "👨‍💻 作者: kure29 | https://kure29.com"
            )
            await self.telegram_bot.send_notification(startup_message)
            
            # 执行启动检查
            await self._perform_startup_check()
            
            # 开始监控循环
            self._running = True
            print("✅ 监控系统启动成功，按Ctrl+C停止")
            await self._monitor_loop()
            
        except KeyboardInterrupt:
            print("\n🛑 收到停止信号")
            self.logger.info("收到停止信号")
        except Exception as e:
            print(f"❌ 监控运行失败: {e}")
            self.logger.error(f"监控运行失败: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """停止监控"""
        print("🛑 正在停止监控系统...")
        self._running = False
        if self.telegram_bot:
            await self.telegram_bot.shutdown()
        self.logger.info("监控程序已停止")
        print("✅ 监控程序已停止")

# ====== 日志设置 ======
def setup_logging() -> None:
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('monitor.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

# ====== 主函数 ======
async def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    print("🤖 VPS监控系统 v1.0")
    print("👨‍💻 作者: kure29")
    print("🌐 网站: https://kure29.com")
    print("=" * 40)
    
    try:
        monitor = VPSMonitor()
        await monitor.start()
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        print("\n✅ 程序已停止")
    except Exception as e:
        logger.error(f"程序发生错误: {e}")
        print(f"❌ 程序发生错误: {e}")
        print("\n💡 常见解决方案:")
        print("1. 检查config.json文件是否存在且配置正确")
        print("2. 确认Telegram Bot Token和Chat ID有效")
        print("3. 检查网络连接")
        print("4. 查看monitor.log获取详细错误信息")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已停止")
    except Exception as e:
        print(f"程序发生错误: {e}")

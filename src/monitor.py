#!/usr/bin/env python3
"""
VPS监控系统 v2.0 - 数据库优化版
作者: kure29
网站: https://kure29.com
"""

import os
import sys
from pathlib import Path

# ====== 路径自动检测和修复 ======
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
import aiosqlite
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

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# 导入数据库管理器
from database_manager import DatabaseManager, MonitorItem, CheckHistory

# ====== 数据类定义 ======
@dataclass
class Config:
    """配置数据类"""
    bot_token: str
    chat_id: str
    channel_id: Optional[str] = None  # 可选的频道ID用于通知
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
    items_per_page: int = 10  # 列表分页显示数量
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.bot_token or self.bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
            raise ValueError("请配置正确的Telegram Bot Token")
        
        if not self.chat_id or self.chat_id == "YOUR_TELEGRAM_CHAT_ID":
            raise ValueError("请配置正确的Telegram Chat ID")
        
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
        """清理URL"""
        try:
            parsed = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed.query)
            
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
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN,zh;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive'
        }
    
    def _analyze_content(self, content: str) -> Tuple[bool, Optional[str]]:
        """分析页面内容判断库存状态"""
        content_lower = content.lower()
        
        # 检查是否为Cloudflare验证页面
        cf_indicators = ['just a moment', 'checking if the site connection is secure', 'ray id']
        if any(indicator in content_lower for indicator in cf_indicators):
            return None, "遇到Cloudflare验证"
        
        if len(content.strip()) < 100:
            return None, "页面内容过短"
        
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
        
        if is_out_of_stock:
            return False, None
        elif is_in_stock or (has_order_form and len(content) > 1000):
            return True, None
        else:
            return False, "无法确定库存状态"
    
    async def check_stock(self, url: str) -> Tuple[Optional[bool], Optional[str], Dict[str, Any]]:
        """检查单个URL的库存状态"""
        start_time = time.time()
        check_info = {
            'response_time': 0,
            'http_status': 0,
            'content_length': 0
        }
        
        try:
            await asyncio.sleep(random.uniform(2, 5))
            
            clean_url = self._clean_url(url)
            headers = self._get_headers()
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.scraper.get(clean_url, headers=headers, timeout=self.config.request_timeout)
            )
            
            check_info['response_time'] = time.time() - start_time
            check_info['http_status'] = response.status_code if response else 0
            
            if not response or response.status_code != 200:
                return None, f"请求失败 (HTTP {response.status_code if response else 'No response'})", check_info
            
            check_info['content_length'] = len(response.content)
            
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
                    return None, "无法解码页面内容", check_info
            
            status, error = self._analyze_content(content)
            return status, error, check_info
            
        except Exception as e:
            check_info['response_time'] = time.time() - start_time
            self.logger.error(f"检查库存失败 {url}: {e}")
            return None, f"检查失败: {str(e)}", check_info

# ====== Telegram机器人（优化版） ======
class TelegramBot:
    """Telegram机器人（数据库版）"""
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
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
            raise
    
    def _setup_handlers(self) -> None:
        """设置命令处理器"""
        handlers = [
            CommandHandler("start", self._start_command),
            CommandHandler("help", self._help_command),
            CommandHandler("list", self._list_command),
            CommandHandler("add", self._add_command),
            CommandHandler("status", self._status_command),
            CommandHandler("stats", self._stats_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message),
            CallbackQueryHandler(self._handle_callback)
        ]
        
        for handler in handlers:
            self.app.add_handler(handler)
    
    def _escape_markdown(self, text: str) -> str:
        """转义Markdown特殊字符"""
        if not text:
            return text
        
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    def _check_admin_permission(self, user_id: str) -> bool:
        """检查管理员权限"""
        if not self.config.admin_ids:
            return True
        return str(user_id) in self.config.admin_ids
    
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /start 命令"""
        user_id = str(update.effective_user.id)
        await self._show_main_menu(update.message, user_id, edit_message=False)
    
    async def _show_main_menu(self, message_or_query, user_id: str, edit_message: bool = False) -> None:
        """显示主菜单"""
        is_admin = self._check_admin_permission(user_id)
        
        if is_admin:
            keyboard = [
                [
                    InlineKeyboardButton("📝 查看监控列表", callback_data='list_items_page_0'),
                    InlineKeyboardButton("➕ 添加监控", callback_data='add_item')
                ],
                [
                    InlineKeyboardButton("📊 系统状态", callback_data='status'),
                    InlineKeyboardButton("📈 统计信息", callback_data='stats')
                ],
                [InlineKeyboardButton("❓ 帮助", callback_data='help')]
            ]
        else:
            keyboard = [
                [
                    InlineKeyboardButton("📝 查看监控列表", callback_data='list_items_page_0'),
                    InlineKeyboardButton("📊 系统状态", callback_data='status')
                ],
                [InlineKeyboardButton("❓ 帮助", callback_data='help')]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            "👋 欢迎使用 VPS 监控机器人 v2.0！\n\n"
            "🔍 主要功能：\n"
            "• 实时监控VPS库存状态\n"
            "• 智能检测商品上架\n"
            "• 即时通知库存变化\n"
            "• 📊 数据库存储和统计\n\n"
            "📱 快速操作："
        )
        
        if not is_admin and self.config.admin_ids:
            welcome_text += "\n\n⚠️ 注意：您没有管理员权限，只能查看监控列表和系统状态"
        
        if edit_message:
            await message_or_query.edit_message_text(welcome_text, reply_markup=reply_markup)
        else:
            await message_or_query.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /help 命令"""
        user_id = str(update.effective_user.id)
        is_admin = self._check_admin_permission(user_id)
        
        help_text = (
            "🤖 VPS监控机器人 v2.0 使用说明\n\n"
            "📝 主要命令：\n"
            "/start - 显示主菜单\n"
            "/list - 查看监控列表\n"
            "/status - 查看系统状态\n"
            "/stats - 查看统计信息\n"
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
        
        await update.message.reply_text(help_text, reply_markup=reply_markup)
    
    async def _list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /list 命令"""
        await self._show_monitor_list(update.message, page=0)
    
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
        items = await self.db_manager.get_monitor_items()
        total_items = len(items)
        
        if total_items == 0:
            status_text = "📊 系统状态\n\n❌ 当前没有监控的商品"
        else:
            in_stock = sum(1 for item in items.values() if item.status is True)
            out_of_stock = sum(1 for item in items.values() if item.status is False)
            unknown = sum(1 for item in items.values() if item.status is None)
            
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
        
        await update.message.reply_text(status_text, reply_markup=reply_markup)
    
    async def _stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /stats 命令"""
        stats = await self.db_manager.get_statistics(days=7)
        
        stats_text = (
            "📈 统计信息（最近7天）\n\n"
            f"📊 总检查次数：{stats.get('total_checks', 0)}\n"
            f"✅ 成功检查：{stats.get('successful_checks', 0)}\n"
            f"❌ 失败检查：{stats.get('failed_checks', 0)}\n"
            f"⏱️ 平均响应时间：{stats.get('avg_response_time', 0)}秒\n\n"
            f"📦 监控商品总数：{stats.get('total_items', 0)}\n"
            f"🟢 当前有货：{stats.get('items_in_stock', 0)}\n"
            f"🔴 当前无货：{stats.get('items_out_of_stock', 0)}"
        )
        
        keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(stats_text, reply_markup=reply_markup)
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理文本消息"""
        text = update.message.text.strip()
        user_id = str(update.effective_user.id)
        
        # 如果不是在添加流程中，提示使用命令
        if not context.user_data.get('adding_item'):
            keyboard = [[InlineKeyboardButton("🏠 主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "请使用 /start 查看主菜单",
                reply_markup=reply_markup
            )
            return
        
        step = context.user_data.get('step')
        cancel_keyboard = [[InlineKeyboardButton("❌ 取消添加", callback_data='cancel_add')]]
        cancel_markup = InlineKeyboardMarkup(cancel_keyboard)
        
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
    
    def _is_valid_url(self, url: str) -> Tuple[bool, str]:
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
    
    async def _process_new_monitor_item(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
        """处理新的监控项"""
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
        existing = await self.db_manager.get_monitor_item_by_url(url)
        if existing:
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
            # 组合商品信息到config字段
            full_config = f"{config}\n💰 {price}\n📡 {network}".strip()
            
            # 添加到数据库
            item_id = await self.db_manager.add_monitor_item(name, url, full_config)
            
            # 立即检查状态
            stock_checker = StockChecker(self.config)
            stock_available, error, check_info = await stock_checker.check_stock(url)
            
            # 记录检查历史
            await self.db_manager.add_check_history(
                monitor_id=item_id,
                status=stock_available,
                response_time=check_info['response_time'],
                error_message=error or '',
                http_status=check_info['http_status'],
                content_length=check_info['content_length']
            )
            
            if error:
                status_text = f"❗ 检查状态时出错: {error}"
            else:
                status = "🟢 有货" if stock_available else "🔴 无货"
                status_text = f"📊 当前状态: {status}"
                await self.db_manager.update_monitor_item_status(item_id, stock_available, 0)
            
            success_text = (
                f"✅ 已添加监控商品\n\n"
                f"📦 名称：{name}\n"
                f"💰 价格：{price}\n"
                f"🖥️ 配置：{config}\n"
                f"📡 线路：{network}\n"
                f"🔗 URL：{url}\n"
                f"\n{status_text}"
            )
            
            keyboard = [
                [InlineKeyboardButton("📝 查看列表", callback_data='list_items_page_0')],
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
    
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理回调查询"""
        query = update.callback_query
        
        try:
            await query.answer()
            
            self.logger.info(f"处理回调: {query.data} - 用户: {update.effective_user.id}")
            
            if query.data == 'main_menu':
                await self._handle_main_menu_callback(update, context)
            elif query.data.startswith('list_items_page_'):
                page = int(query.data.split('_')[-1])
                await self._show_monitor_list(query.message, page)
            elif query.data == 'add_item':
                await self._handle_add_item_callback(update, context)
            elif query.data == 'help':
                await self._handle_help_callback(update, context)
            elif query.data == 'status':
                await self._handle_status_callback(update, context)
            elif query.data == 'stats':
                await self._handle_stats_callback(update, context)
            elif query.data == 'cancel_add':
                await self._handle_cancel_add_callback(update, context)
            elif query.data == 'check_all':
                await self._handle_check_all_callback(update, context)
            elif query.data == 'manage_items':
                await self._handle_manage_items_callback(update, context)
            elif query.data == 'export_data':
                await self._handle_export_data_callback(update, context)
            elif query.data.startswith('delete_'):
                url = query.data[7:]
                await self._delete_monitor_item(query.message, url)
            elif query.data.startswith('check_'):
                url = query.data[6:]
                await self._manual_check_item(query.message, url)
            else:
                self.logger.warning(f"未处理的回调: {query.data}")
                
        except Exception as e:
            self.logger.error(f"处理回调失败: {query.data} - {e}", exc_info=True)
            
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.message.reply_text(f"❌ 操作失败: {str(e)}", reply_markup=reply_markup)
            except:
                pass
    
    async def _handle_main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理返回主菜单回调"""
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
            "🤖 VPS监控机器人 v2.0 使用说明\n\n"
            "📝 主要命令：\n"
            "/start - 显示主菜单\n"
            "/list - 查看监控列表\n"
            "/status - 查看系统状态\n"
            "/stats - 查看统计信息\n"
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
        
        help_text += (
            "🔄 监控逻辑：\n"
            f"• 每{self.config.check_interval}秒检查一次\n"
            f"• 每{self.config.notification_aggregation_interval//60}分钟聚合通知\n"
            f"• 单商品{self.config.notification_cooldown//60}分钟冷却时间\n\n"
            "📊 新功能：\n"
            "• 数据库存储，更稳定\n"
            "• 统计分析功能\n"
            "• 分页显示列表\n"
            "• 数据导出功能"
        )
        
        keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(help_text, reply_markup=reply_markup)
    
    async def _handle_status_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理状态查询回调"""
        items = await self.db_manager.get_monitor_items()
        total_items = len(items)
        
        if total_items == 0:
            status_text = "📊 系统状态\n\n❌ 当前没有监控的商品"
        else:
            in_stock = sum(1 for item in items.values() if item.status is True)
            out_of_stock = sum(1 for item in items.values() if item.status is False)
            unknown = sum(1 for item in items.values() if item.status is None)
            
            status_text = (
                "📊 系统状态\n\n"
                f"📦 监控商品：{total_items} 个\n"
                f"🟢 有货：{in_stock} 个\n"
                f"🔴 无货：{out_of_stock} 个\n"
                f"⚪ 未知：{unknown} 个\n\n"
                f"⏱️ 检查间隔：{self.config.check_interval}秒\n"
                f"🔔 通知间隔：{self.config.notification_aggregation_interval}秒"
            )
        
        keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(status_text, reply_markup=reply_markup)
    
    async def _handle_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理统计回调"""
        stats = await self.db_manager.get_statistics(days=7)
        
        stats_text = (
            "📈 统计信息（最近7天）\n\n"
            f"📊 总检查次数：{stats.get('total_checks', 0)}\n"
            f"✅ 成功检查：{stats.get('successful_checks', 0)}\n"
            f"❌ 失败检查：{stats.get('failed_checks', 0)}\n"
            f"⏱️ 平均响应时间：{stats.get('avg_response_time', 0)}秒\n\n"
            f"📦 监控商品总数：{stats.get('total_items', 0)}\n"
            f"🟢 当前有货：{stats.get('items_in_stock', 0)}\n"
            f"🔴 当前无货：{stats.get('items_out_of_stock', 0)}"
        )
        
        # 添加每日趋势
        daily_trends = stats.get('daily_trends', [])
        if daily_trends:
            stats_text += "\n\n📊 最近检查趋势："
            for trend in daily_trends[:3]:  # 显示最近3天
                stats_text += f"\n{trend['date']}: {trend['checks']}次检查, {trend['successful']}次成功"
        
        keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(stats_text, reply_markup=reply_markup)
    
    async def _handle_cancel_add_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理取消添加回调"""
        context.user_data.clear()
        
        keyboard = [
            [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')],
            [InlineKeyboardButton("➕ 重新添加", callback_data='add_item')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "❌ 已取消添加",
            reply_markup=reply_markup
        )
    
    async def _show_monitor_list(self, message, page: int = 0) -> None:
        """显示监控列表（分页版）"""
        items = await self.db_manager.get_monitor_items()
        if not items:
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            if self._check_admin_permission(str(message.chat.id)):
                keyboard.insert(0, [InlineKeyboardButton("➕ 添加商品", callback_data='add_item')])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text("📝 当前没有监控的商品", reply_markup=reply_markup)
            return
        
        # 分页计算
        items_list = list(items.values())
        total_items = len(items_list)
        items_per_page = self.config.items_per_page
        total_pages = (total_items + items_per_page - 1) // items_per_page
        
        # 确保页码有效
        page = max(0, min(page, total_pages - 1))
        
        # 获取当前页的商品
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, total_items)
        page_items = items_list[start_idx:end_idx]
        
        # 构建列表文本
        list_text = f"📝 **监控列表** (第 {page + 1}/{total_pages} 页)\n\n"
        
        for i, item in enumerate(page_items, start=start_idx + 1):
            status_emoji = "⚪" if item.status is None else ("🟢" if item.status else "🔴")
            list_text += f"{i}\\. {status_emoji} **{self._escape_markdown(item.name)}**\n"
            
            # 显示简要信息
            config_lines = item.config.split('\n')
            for line in config_lines[:2]:  # 只显示前两行
                if line.strip():
                    list_text += f"   {self._escape_markdown(line)}\n"
            
            list_text += f"   🔗 {item.url[:40]}{'...' if len(item.url) > 40 else ''}\n\n"
        
        # 构建按钮
        keyboard = []
        
        # 翻页按钮
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f'list_items_page_{page-1}'))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️ 下一页", callback_data=f'list_items_page_{page+1}'))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # 功能按钮
        keyboard.extend([
            [InlineKeyboardButton("🔄 全部检查", callback_data='check_all')],
            [InlineKeyboardButton("📊 系统状态", callback_data='status')],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
        ])
        
        # 管理员按钮
        if self._check_admin_permission(str(message.chat.id)):
            keyboard.insert(1, [InlineKeyboardButton("➕ 添加商品", callback_data='add_item')])
            keyboard.insert(2, [InlineKeyboardButton("🛠️ 管理商品", callback_data='manage_items')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(list_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def _handle_check_all_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理全部检查回调"""
        items = await self.db_manager.get_monitor_items()
        if not items:
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                "❌ 没有监控商品需要检查",
                reply_markup=reply_markup
            )
            return
        
        progress_text = f"🔄 开始检查 {len(items)} 个商品...\n\n进度：0/{len(items)}"
        await update.callback_query.edit_message_text(progress_text)
        
        checked_count = 0
        results = []
        stock_checker = StockChecker(self.config)
        
        for item in items.values():
            try:
                checked_count += 1
                progress_text = f"🔄 正在检查商品...\n\n进度：{checked_count}/{len(items)}\n当前：{item.name}"
                await update.callback_query.edit_message_text(progress_text)
                
                stock_available, error, check_info = await stock_checker.check_stock(item.url)
                
                # 记录检查历史
                await self.db_manager.add_check_history(
                    monitor_id=item.id,
                    status=stock_available,
                    response_time=check_info['response_time'],
                    error_message=error or '',
                    http_status=check_info['http_status'],
                    content_length=check_info['content_length']
                )
                
                if error:
                    results.append(f"❗ {item.name}: {error}")
                else:
                    status_emoji = "🟢" if stock_available else "🔴"
                    status_text = "有货" if stock_available else "无货"
                    results.append(f"{status_emoji} {item.name}: {status_text}")
                    await self.db_manager.update_monitor_item_status(item.id, stock_available)
                
            except Exception as e:
                results.append(f"❌ {item.name}: 检查失败")
                self.logger.error(f"批量检查失败 {item.url}: {e}")
        
        result_text = "✅ **批量检查完成**\n\n"
        result_text += "\n".join(results[:15])
        
        if len(results) > 15:
            result_text += f"\n\n... 还有 {len(results) - 15} 个结果"
        
        keyboard = [
            [InlineKeyboardButton("📝 查看列表", callback_data='list_items_page_0')],
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
        
        items = await self.db_manager.get_monitor_items()
        if not items:
            keyboard = [
                [InlineKeyboardButton("➕ 添加商品", callback_data='add_item')],
                [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                "📝 当前没有监控商品",
                reply_markup=reply_markup
            )
            return
        
        manage_text = f"🛠️ **商品管理** ({len(items)} 个)\n\n选择操作："
        
        keyboard = [
            [InlineKeyboardButton("➕ 添加商品", callback_data='add_item')],
            [InlineKeyboardButton("📤 导出数据", callback_data='export_data')],
            [InlineKeyboardButton("📝 查看列表", callback_data='list_items_page_0')],
            [InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            manage_text, 
            reply_markup=reply_markup, 
            parse_mode='Markdown'
        )
    
    async def _handle_export_data_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理导出数据回调"""
        user_id = str(update.effective_user.id)
        if not self._check_admin_permission(user_id):
            return
        
        try:
            export_file = f"vps_monitor_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            success = await self.db_manager.export_to_json(export_file)
            
            if success:
                keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.callback_query.edit_message_text(
                    f"✅ 数据导出成功\n\n文件名：{export_file}",
                    reply_markup=reply_markup
                )
            else:
                raise Exception("导出失败")
                
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(
                f"❌ 导出数据失败: {str(e)}",
                reply_markup=reply_markup
            )
    
    async def _delete_monitor_item(self, message, url: str) -> None:
        """删除监控项"""
        try:
            item = await self.db_manager.get_monitor_item_by_url(url)
            if not item:
                keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await message.reply_text(
                    "❌ 未找到该监控项",
                    reply_markup=reply_markup
                )
                return
            
            success = await self.db_manager.remove_monitor_item(url)
            if success:
                keyboard = [
                    [InlineKeyboardButton("📝 查看列表", callback_data='list_items_page_0')],
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
        """手动检查单个商品"""
        try:
            item = await self.db_manager.get_monitor_item_by_url(url)
            if not item:
                keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data='main_menu')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await message.reply_text(
                    "❌ 未找到该监控项",
                    reply_markup=reply_markup
                )
                return
            
            checking_msg = await message.reply_text(f"🔄 正在检查 {item.name}...")
            
            stock_checker = StockChecker(self.config)
            stock_available, error, check_info = await stock_checker.check_stock(url)
            
            # 记录检查历史
            await self.db_manager.add_check_history(
                monitor_id=item.id,
                status=stock_available,
                response_time=check_info['response_time'],
                error_message=error or '',
                http_status=check_info['http_status'],
                content_length=check_info['content_length']
            )
            
            if error:
                result_text = f"❗ 检查失败: {error}"
            else:
                status_emoji = "🟢" if stock_available else "🔴"
                status_text = "有货" if stock_available else "无货"
                result_text = f"📊 当前状态: {status_emoji} {status_text}"
                await self.db_manager.update_monitor_item_status(item.id, stock_available)
            
            final_text = (
                f"📦 {item.name}\n"
                f"🔗 {url}\n"
                f"{result_text}\n"
                f"🕒 检查时间: {datetime.now().strftime('%m-%d %H:%M:%S')}\n"
                f"⏱️ 响应时间: {check_info['response_time']:.2f}秒"
            )
            
            keyboard = [
                [InlineKeyboardButton("🔄 再次检查", callback_data=f'check_{url}')],
                [InlineKeyboardButton("📝 查看列表", callback_data='list_items_page_0')],
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
    
    async def send_notification(self, message: str, parse_mode: str = None, chat_id: str = None) -> None:
        """发送通知（支持发送到不同聊天）"""
        try:
            if self.app and self.app.bot:
                # 如果没有指定chat_id，使用默认的
                target_chat_id = chat_id or self.config.channel_id or self.config.chat_id
                
                await self.app.bot.send_message(
                    chat_id=target_chat_id, 
                    text=message,
                    parse_mode=parse_mode,
                    disable_web_page_preview=False
                )
                self.logger.info(f"通知发送成功到 {target_chat_id}")
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
    """主监控类（数据库版）"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager()
        self.stock_checker = None
        self.telegram_bot = None
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._pending_notifications = []
        self._last_aggregation_time = datetime.now()
        self._last_notified = {}  # 记录每个商品的最后通知时间
    
    async def initialize(self) -> None:
        """初始化监控器"""
        try:
            print("🔧 初始化监控器...")
            
            # 加载配置
            config = self.config_manager.load_config()
            print("✅ 配置文件加载成功")
            
            # 初始化数据库
            await self.db_manager.initialize()
            print("✅ 数据库初始化成功")
            
            # 初始化组件
            self.stock_checker = StockChecker(config)
            self.telegram_bot = TelegramBot(config, self.db_manager)
            
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
        items = await self.db_manager.get_monitor_items()
        if not items:
            await self.telegram_bot.send_notification("⚠️ 当前没有监控商品，请使用 /add 添加")
            print("⚠️ 当前没有监控商品")
            return
        
        print(f"🔍 开始检查 {len(items)} 个监控项...")
        await self.telegram_bot.send_notification("🔄 正在进行启动检查...")
        
        success_count = 0
        fail_count = 0
        
        for item in items.values():
            try:
                print(f"检查: {item.name}")
                stock_available, error, check_info = await self.stock_checker.check_stock(item.url)
                
                # 记录检查历史
                await self.db_manager.add_check_history(
                    monitor_id=item.id,
                    status=stock_available,
                    response_time=check_info['response_time'],
                    error_message=error or '',
                    http_status=check_info['http_status'],
                    content_length=check_info['content_length']
                )
                
                if error:
                    fail_count += 1
                    print(f"  ❌ 检查失败: {error}")
                else:
                    success_count += 1
                    status = "🟢 有货" if stock_available else "🔴 无货"
                    print(f"  ✅ 状态：{status}")
                    await self.db_manager.update_monitor_item_status(item.id, stock_available, 0)
                
            except Exception as e:
                fail_count += 1
                self.logger.error(f"启动检查失败 {item.url}: {e}")
                print(f"  ❌ 检查异常: {e}")
        
        summary = f"✅ 启动检查完成\n\n成功: {success_count} 个\n失败: {fail_count} 个"
        await self.telegram_bot.send_notification(summary)
        print(f"\n{summary}")
    
    async def _monitor_loop(self) -> None:
        """主监控循环"""
        config = self.config_manager.config
        print(f"🔄 开始监控循环，检查间隔: {config.check_interval}秒")
        
        while self._running:
            try:
                items = await self.db_manager.get_monitor_items()
                if not items:
                    await asyncio.sleep(config.check_interval)
                    continue
                
                print(f"🔍 执行定期检查 ({len(items)} 个项目)")
                
                for item in items.values():
                    if not self._running:
                        break
                    
                    try:
                        stock_available, error, check_info = await self.stock_checker.check_stock(item.url)
                        
                        # 记录检查历史
                        await self.db_manager.add_check_history(
                            monitor_id=item.id,
                            status=stock_available,
                            response_time=check_info['response_time'],
                            error_message=error or '',
                            http_status=check_info['http_status'],
                            content_length=check_info['content_length']
                        )
                        
                        if error:
                            self.logger.warning(f"检查失败 {item.url}: {error}")
                            continue
                        
                        # 检查状态变化
                        previous_status = item.status
                        
                        if previous_status is None:
                            await self.db_manager.update_monitor_item_status(item.id, stock_available, 0)
                            continue
                        
                        if stock_available and not previous_status:
                            # 从无货变为有货
                            item_id = item.id
                            if item_id not in self._last_notified or \
                               (datetime.now() - self._last_notified[item_id]).total_seconds() > config.notification_cooldown:
                                self._pending_notifications.append(item)
                                self._last_notified[item_id] = datetime.now()
                            
                            await self.db_manager.update_monitor_item_status(
                                item.id, stock_available, 
                                item.notification_count + 1
                            )
                        elif not stock_available and previous_status:
                            # 从有货变为无货
                            await self._send_status_change_notification(item, stock_available)
                            await self.db_manager.update_monitor_item_status(item.id, stock_available, 0)
                        else:
                            # 状态未变化，只更新检查时间
                            await self.db_manager.update_monitor_item_status(item.id, stock_available)
                        
                    except Exception as e:
                        self.logger.error(f"监控循环出错 {item.url}: {e}")
                        continue
                
                # 处理聚合通知
                await self._process_aggregated_notifications()
                
                # 定期清理旧数据
                if random.random() < 0.01:  # 1%的概率执行清理
                    await self.db_manager.cleanup_old_history(days=90)
                
                await asyncio.sleep(config.check_interval)
                
            except Exception as e:
                self.logger.error(f"监控循环出错: {e}")
                await asyncio.sleep(config.retry_delay)
    
    async def _send_status_change_notification(self, item: MonitorItem, stock_available: bool) -> None:
        """发送状态变化通知"""
        if stock_available:
            message = (
                f"🎉 **补货通知**\n\n"
                f"📦 **{item.name}**\n\n"
                f"{item.config}\n\n"
                f"🔗 [立即抢购]({item.url})\n\n"
                f"🛒 **库存**：有货"
            )
        else:
            message = f"📦 {item.name}\n📊 状态：🔴 已经无货"
        
        # 如果配置了频道，发送到频道；否则发送到私聊
        await self.telegram_bot.send_notification(
            message, 
            parse_mode='Markdown' if stock_available else None,
            chat_id=self.config_manager.config.channel_id
        )
        
        print(f"{'🎉' if stock_available else '📉'} {item.name} {'现在有货！' if stock_available else '已无货'}")
    
    async def _process_aggregated_notifications(self) -> None:
        """处理聚合通知"""
        if not self._pending_notifications:
            return
        
        time_since_last = (datetime.now() - self._last_aggregation_time).total_seconds()
        if time_since_last < self.config_manager.config.notification_aggregation_interval:
            return
        
        if self._pending_notifications:
            message = "🎉 **补货通知** 🎉\n\n"
            for item in self._pending_notifications:
                message += (
                    f"📦 **{item.name}**\n"
                    f"{item.config}\n"
                    f"🔗 [立即抢购]({item.url})\n\n"
                )
            
            await self.telegram_bot.send_notification(
                message, 
                parse_mode='Markdown',
                chat_id=self.config_manager.config.channel_id
            )
            print(f"📮 发送了 {len(self._pending_notifications)} 个商品的聚合通知")
        
        self._pending_notifications.clear()
        self._last_aggregation_time = datetime.now()
    
    async def start(self) -> None:
        """启动监控"""
        try:
            print("🚀 启动VPS监控系统 v2.0...")
            await self.initialize()
            
            # 发送启动通知
            config = self.config_manager.config
            startup_message = (
                "🚀 VPS监控程序 v2.0 已启动\n"
                f"⏰ 检查间隔：{config.check_interval}秒\n"
                f"📊 聚合间隔：{config.notification_aggregation_interval}秒\n"
                f"🕐 通知冷却：{config.notification_cooldown}秒\n\n"
                "🆕 **新功能**：\n"
                "📊 数据库存储\n"
                "📈 统计分析\n"
                "📄 分页显示\n"
                "📤 数据导出\n\n"
                "💡 使用 /start 开始操作\n\n"
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
    
    print("🤖 VPS监控系统 v2.0 - 数据库优化版")
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

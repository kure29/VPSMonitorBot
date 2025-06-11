#!/usr/bin/env python3
"""
VPS监控系统 v1.0 - 主程序
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
    created_at: str = ""
    last_checked: str = ""
    status: Optional[bool] = None
    notification_count: int = 0

@dataclass
class Config:
    """配置数据类 - 支持所有可能的配置字段"""
    bot_token: str
    chat_id: str
    check_interval: int = 300
    max_notifications: int = 3
    request_timeout: int = 30
    retry_delay: int = 60
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    proxy: Optional[str] = None
    debug: bool = False
    log_level: str = "INFO"
    
    def __post_init__(self):
        """初始化后处理"""
        # 确保必要字段不为空
        if not self.bot_token or self.bot_token == "YOUR_TELEGRAM_BOT_TOKEN":
            raise ValueError("请配置正确的Telegram Bot Token")
        
        if not self.chat_id or self.chat_id == "YOUR_TELEGRAM_CHAT_ID":
            raise ValueError("请配置正确的Telegram Chat ID")

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
    "check_interval": 300,
    "max_notifications": 3,
    "request_timeout": 30,
    "retry_delay": 60
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
                        created_at=item_data.get('created_at', ''),
                        last_checked=item_data.get('last_checked', ''),
                        status=item_data.get('status'),
                        notification_count=item_data.get('notification_count', 0)
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
                    'created_at': item.created_at,
                    'last_checked': item.last_checked,
                    'status': item.status,
                    'notification_count': item.notification_count
                }
            
            async with aiofiles.open(self.data_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=4))
        except Exception as e:
            self.logger.error(f"保存数据文件失败: {e}")
            raise
    
    def add_monitor_item(self, name: str, url: str, config: str = "") -> str:
        """添加监控项"""
        item_id = str(int(time.time()))
        item = MonitorItem(
            id=item_id,
            name=name,
            url=url,
            config=config,
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

# ====== Telegram机器人 ======
class TelegramBot:
    """Telegram机器人"""
    
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
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message),
            CallbackQueryHandler(self._handle_callback)
        ]
        
        for handler in handlers:
            self.app.add_handler(handler)
    
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /start 命令"""
        keyboard = [
            [
                InlineKeyboardButton("📝 查看监控列表", callback_data='list_items'),
                InlineKeyboardButton("➕ 添加监控", callback_data='add_item')
            ],
            [InlineKeyboardButton("❓ 帮助", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            "👋 欢迎使用 VPS 监控机器人！\n\n"
            "🔍 主要功能：\n"
            "• 实时监控VPS库存状态\n"
            "• 智能检测商品上架\n"
            "• 即时通知库存变化\n\n"
            "📱 快速操作："
        )
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /help 命令"""
        help_text = (
            "🤖 VPS监控机器人使用说明\n\n"
            "📝 主要命令：\n"
            "/start - 显示主菜单\n"
            "/list - 查看监控列表\n"
            "/add - 添加监控商品\n"
            "/help - 显示帮助信息\n\n"
            "➕ 添加流程：\n"
            "1. 输入商品名称\n"
            "2. 输入配置信息（可选）\n"
            "3. 输入监控URL\n\n"
            "🔄 监控逻辑：\n"
            "• 智能检测库存状态变化\n"
            "• 有货时最多通知3次\n"
            "• 支持多种电商平台\n\n"
            "💡 提示：确保URL格式正确（包含http://或https://）"
        )
        await update.message.reply_text(help_text)
    
    async def _list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /list 命令"""
        await self._show_monitor_list(update.message)
    
    async def _add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理 /add 命令"""
        context.user_data.clear()
        context.user_data['adding_item'] = True
        context.user_data['step'] = 'name'
        
        await update.message.reply_text(
            "📝 添加新的监控商品\n\n"
            "请输入商品名称：\n"
            "（例如：Racknerd 2G VPS）"
        )
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理文本消息"""
        if not context.user_data.get('adding_item'):
            return
        
        text = update.message.text.strip()
        step = context.user_data.get('step')
        
        if step == 'name':
            context.user_data['name'] = text
            context.user_data['step'] = 'config'
            await update.message.reply_text(
                f"✅ 商品名称：{text}\n\n"
                "请输入配置信息（可选）：\n"
                "（例如：2GB RAM, 20GB SSD）\n"
                "或直接发送 /skip 跳过"
            )
        
        elif step == 'config':
            if text != '/skip':
                context.user_data['config'] = text
            else:
                context.user_data['config'] = ""
            
            context.user_data['step'] = 'url'
            await update.message.reply_text(
                "请输入监控URL：\n"
                "（必须以 http:// 或 https:// 开头）"
            )
        
        elif step == 'url':
            await self._process_new_monitor_item(update, context, text)
    
    async def _process_new_monitor_item(self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
        """处理新的监控项"""
        if not url.startswith(('http://', 'https://')):
            await update.message.reply_text(
                "❌ URL格式错误！\n"
                "请确保URL以 http:// 或 https:// 开头"
            )
            return
        
        name = context.user_data['name']
        config = context.user_data.get('config', '')
        
        # 检查是否已存在
        if self.data_manager.get_monitor_item_by_url(url):
            await update.message.reply_text("❌ 该URL已在监控列表中！")
            context.user_data.clear()
            return
        
        processing_msg = await update.message.reply_text("⏳ 正在添加并检查状态...")
        
        try:
            # 添加到数据库
            item_id = self.data_manager.add_monitor_item(name, url, config)
            await self.data_manager.save_monitor_items()
            
            # 立即检查状态
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
                f"🔗 URL：{url}\n"
            )
            if config:
                success_text += f"⚙️ 配置：{config}\n"
            success_text += f"\n{status_text}"
            
            await processing_msg.edit_text(success_text)
            
        except Exception as e:
            await processing_msg.edit_text(f"❌ 添加失败: {str(e)}")
            self.logger.error(f"添加监控项失败: {e}")
        
        finally:
            context.user_data.clear()
    
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """处理回调查询"""
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == 'list_items':
                await self._show_monitor_list(query.message)
            elif query.data == 'add_item':
                await self._add_command(update, context)
            elif query.data == 'help':
                await self._help_command(update, context)
            elif query.data.startswith('delete_'):
                url = query.data[7:]
                await self._delete_monitor_item(query.message, url)
        except Exception as e:
            self.logger.error(f"处理回调失败: {e}")
            await query.message.reply_text("❌ 操作失败，请重试")
    
    async def _show_monitor_list(self, message) -> None:
        """显示监控列表"""
        items = self.data_manager.monitor_items
        if not items:
            await message.reply_text("📝 当前没有监控的商品")
            return
        
        await message.reply_text(f"📝 当前监控 {len(items)} 个商品：")
        
        for item in items.values():
            keyboard = [[InlineKeyboardButton("🗑️ 删除", callback_data=f'delete_{item.url}')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # 构建状态显示
            if item.status is None:
                status = "⚪ 未检查"
            elif item.status:
                status = "🟢 有货"
            else:
                status = "🔴 无货"
            
            item_text = f"📦 {item.name}\n🔗 {item.url}\n📊 状态：{status}"
            if item.config:
                item_text += f"\n⚙️ 配置：{item.config}"
            if item.last_checked:
                try:
                    check_time = datetime.fromisoformat(item.last_checked)
                    item_text += f"\n🕒 最后检查：{check_time.strftime('%m-%d %H:%M')}"
                except:
                    pass
            
            await message.reply_text(item_text, reply_markup=reply_markup)
    
    async def _delete_monitor_item(self, message, url: str) -> None:
        """删除监控项"""
        try:
            item = self.data_manager.get_monitor_item_by_url(url)
            if not item:
                await message.reply_text("❌ 未找到该监控项")
                return
            
            if self.data_manager.remove_monitor_item(url):
                await self.data_manager.save_monitor_items()
                await message.reply_text(f"✅ 已删除监控：{item.name}")
            else:
                await message.reply_text("❌ 删除失败")
        except Exception as e:
            self.logger.error(f"删除监控项失败: {e}")
            await message.reply_text("❌ 删除失败")
    
    async def send_notification(self, message: str) -> None:
        """发送通知"""
        try:
            if self.app and self.app.bot:
                await self.app.bot.send_message(chat_id=self.config.chat_id, text=message)
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
                        
                        if stock_available != previous_status:
                            # 状态发生变化
                            await self._send_status_change_notification(item, stock_available)
                            
                            notification_count = 1 if stock_available else 0
                            self.data_manager.update_monitor_item_status(item.url, stock_available, notification_count)
                            
                        elif stock_available and item.notification_count < config.max_notifications:
                            # 持续有货，继续通知
                            await self._send_continued_stock_notification(item)
                            self.data_manager.update_monitor_item_status(
                                item.url, stock_available, item.notification_count + 1
                            )
                        
                    except Exception as e:
                        self.logger.error(f"监控循环出错 {item.url}: {e}")
                        continue
                
                # 保存状态
                await self.data_manager.save_monitor_items()
                await asyncio.sleep(config.check_interval)
                
            except Exception as e:
                self.logger.error(f"监控循环出错: {e}")
                await asyncio.sleep(config.retry_delay)
    
    async def _send_status_change_notification(self, item: MonitorItem, stock_available: bool) -> None:
        """发送状态变化通知"""
        message = f"📦 {item.name}\n🔗 {item.url}\n"
        if item.config:
            message += f"⚙️ 配置：{item.config}\n"
        
        if stock_available:
            message += "📊 状态：🟢 补货啦！商品现在有货"
            print(f"🎉 {item.name} 现在有货！")
        else:
            message += "📊 状态：🔴 已经无货"
            print(f"📉 {item.name} 已无货")
        
        await self.telegram_bot.send_notification(message)
    
    async def _send_continued_stock_notification(self, item: MonitorItem) -> None:
        """发送持续有货通知"""
        message = f"📦 {item.name}\n🔗 {item.url}\n"
        if item.config:
            message += f"⚙️ 配置：{item.config}\n"
        
        count = item.notification_count + 1
        max_count = self.config_manager.config.max_notifications
        message += f"📊 状态：🟢 仍然有货 (通知 {count}/{max_count})"
        
        await self.telegram_bot.send_notification(message)
    
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
                f"📢 最大通知次数：{config.max_notifications}次\n\n"
                "💡 使用 /start 开始操作\n"
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

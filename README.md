# VPSMonitorBot v2.1 - 优化版本

VPSMonitorBot 是一个基于 Telegram 的网站库存监控工具，专门用于监控VPS商家的库存状态。本版本经过全面优化，提供更好的性能、稳定性和用户体验。

## 🚀 新特性与优化

### v2.1 优化亮点

#### 🏗️ **代码架构优化**
- **模块化设计**: 使用数据类和管理器模式，代码更清晰易维护
- **异步优化**: 全面使用异步操作，提升性能和响应速度
- **类型注解**: 添加完整的类型提示，提高代码质量
- **错误处理**: 增强的异常处理和重试机制

#### 💾 **数据管理优化**
- **异步文件操作**: 使用 `aiofiles` 进行非阻塞文件操作
- **数据结构改进**: 使用 `@dataclass` 定义数据模型
- **扩展数据字段**: 支持价格、线路、库存等更多信息
- **配置验证**: 自动验证配置文件格式和内容

#### 🤖 **Telegram Bot 增强**
- **管理员权限控制**: 支持限制只有管理员才能添加监控
- **Markdown格式通知**: 美化的通知样式，支持富文本
- **聚合通知**: 每3分钟聚合一次补货通知
- **冷却机制**: 每个商品10分钟内最多通知一次

#### 🔍 **监控功能优化**
- **智能检测**: 改进的库存状态检测算法
- **多编码支持**: 自动处理多种字符编码
- **防反爬**: 更好的反爬虫策略和请求头管理
- **URL清理**: 自动清理不必要的URL参数

#### 🛠️ **Shell脚本优化**
- **系统检测**: 修复各种系统兼容性问题
- **环境验证**: 完整的环境检查和验证流程
- **错误处理**: 强化的错误处理和恢复机制
- **用户体验**: 更美观的界面和更清晰的提示信息

## 📦 快速开始

### 系统要求
- **操作系统**: Ubuntu/Debian, CentOS/RHEL, Arch Linux
- **Python**: 3.7+ (推荐 3.9+)
- **系统工具**: curl, jq (自动安装)
- **网络**: 可访问 Telegram API

### 一键安装
```bash
# 克隆项目
git clone https://github.com/kure29/VPSMonitorBot.git
cd VPSMonitorBot

# 给予执行权限并运行
chmod +x scripts/install.sh
./scripts/install.sh
```

首次运行会自动：
1. 检测并安装系统依赖
2. 创建Python虚拟环境
3. 安装Python依赖包
4. 引导配置Telegram信息
5. 可选择添加第一个监控商品

## 🎮 使用说明

### Telegram Bot 命令
| 命令 | 说明 |
|------|------|
| `/start` | 显示主菜单和快速操作 |
| `/add` | 添加新的监控商品（管理员限定） |
| `/list` | 查看所有监控商品 |
| `/help` | 显示详细帮助信息 |

### Shell 管理菜单
```
============== 功能菜单 ==============
1. 添加监控商品      6. 停止监控
2. 删除监控商品      7. 查看监控状态  
3. 显示所有监控商品   8. 查看监控日志
4. 配置Telegram信息  9. 系统状态检查
5. 启动监控         0. 退出
=====================================
```

### 添加监控商品流程
1. **输入商品名称**: 例如 "ZgoCloud - Los Angeles AMD VPS"
2. **输入配置信息**: 例如 "1 Core AMD EPYC, 2GB RAM, 30GB SSD"
3. **输入价格信息**: 例如 "$36.00 / 年付"
4. **输入线路信息**: 例如 "优化线路 #9929 & #CMIN2"
5. **输入监控URL**: 商品购买链接

## ⚙️ 配置说明

### config.json 配置文件
```json
{
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID",
    "admin_ids": ["123456789", "987654321"],
    "check_interval": 180,
    "notification_aggregation_interval": 180,
    "notification_cooldown": 600,
    "request_timeout": 30,
    "retry_delay": 60
}
```

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `bot_token` | Telegram Bot Token | 必填 |
| `chat_id` | Telegram Chat ID | 必填 |
| `admin_ids` | 管理员ID列表（可选） | [] |
| `check_interval` | 检查间隔（秒） | 180 |
| `notification_aggregation_interval` | 通知聚合间隔（秒） | 180 |
| `notification_cooldown` | 单商品通知冷却时间（秒） | 600 |
| `request_timeout` | 请求超时时间 | 30 |
| `retry_delay` | 重试延迟时间 | 60 |

### 获取 Telegram 配置
1. **创建Bot**: 向 [@BotFather](https://t.me/BotFather) 发送 `/newbot`
2. **获取Chat ID**: 向 [@userinfobot](https://t.me/userinfobot) 发送 `/start`
3. **激活Bot**: 向你的Bot发送任意消息建立对话

### 通知格式示例
```
📦 **ZgoCloud - Los Angeles AMD VPS - Specials - Starter**

💰 **$36.00 / 年付**

🖥️ **配置**
1 Core AMD EPYC 7B13  
2 GB DDR4 RAM  
30 GB NVMe SSD  
1 IPv4 /64 IPv6  
1TB/月 @ 300Mbps  
🌍 Los Angeles（优化大陆线路）

📡 **线路**：#优化线路 #9929 & #CMIN2  
🔗 [立即抢购](https://clients.zgovps.com/?cmd=cart&action=add&affid=288&id=66)

🛒 **库存**：∞ #Available
```

## 🔧 高级功能

### 管理员权限控制
在 `config.json` 中配置 `admin_ids` 字段，限制只有特定用户才能添加监控：
```json
{
    "admin_ids": ["123456789", "987654321"]
}
```
留空则所有人都可以操作。

### 聚合通知机制
- **聚合间隔**: 每3分钟检查一次待发送通知
- **冷却时间**: 每个商品10分钟内最多通知一次
- **批量通知**: 多个商品补货时合并为一条消息

### 数据库支持（可选）
`database_manager.py` 提供SQLite数据库支持：
- 历史记录追踪
- 统计分析功能
- 更好的查询性能

使用方法：
```python
# 修改monitor.py，替换DataManager
from database_manager import DatabaseManager
self.data_manager = DatabaseManager("vps_monitor.db")
```

### Web管理界面
提供静态Web界面用于监控状态展示：

**方法一：Python HTTP服务器**
```bash
cd web
python3 -m http.server 8000
```

**方法二：Nginx配置**
```bash
sudo cp config/nginx.conf.example /etc/nginx/sites-available/vps-monitor
sudo ln -s /etc/nginx/sites-available/vps-monitor /etc/nginx/sites-enabled/
sudo systemctl reload nginx
```

## 📊 监控逻辑

### 库存检测算法
1. **页面获取**: 使用cloudscraper绕过Cloudflare保护
2. **内容分析**: 智能识别缺货/有货关键词
3. **状态判断**: 综合多种指标判断库存状态
4. **变化检测**: 只在状态变化时发送通知

### 通知策略
- **补货通知**: 从无货变为有货时触发
- **聚合发送**: 3分钟内的补货通知合并发送
- **冷却保护**: 单个商品10分钟内不重复通知
- **缺货通知**: 从有货变为无货时立即通知

### 防反爬策略
- 随机延迟请求（2-5秒）
- 轮换User-Agent
- 自动清理URL参数
- 智能重试机制

## 🛡️ 安全与隐私

- **配置安全**: 敏感信息本地存储，不上传
- **管理员控制**: 支持限制添加权限
- **日志脱敏**: 自动脱敏敏感信息
- **数据备份**: 支持自动备份重要数据

## 🔧 故障排除

### 常见问题

**Q: 安装脚本报错**
```bash
# 手动检测系统
cat /etc/os-release

# 手动安装依赖
apt-get update && apt-get install -y python3 python3-pip python3-venv
```

**Q: Telegram通知不工作**
```bash
# 测试配置
curl -s "https://api.telegram.org/bot{TOKEN}/getMe"
curl -s "https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text=test"
```

**Q: 库存检测不准确**
- 确保URL是商品的直接链接
- 检查网站是否有反爬虫保护
- 调整检查间隔避免频率过高

**Q: 虚拟环境问题**
```bash
# 重新创建虚拟环境
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 性能优化建议
1. **检查间隔**: 建议设置为180秒（3分钟）
2. **监控数量**: 单实例建议不超过50个URL
3. **日志管理**: 定期清理旧日志文件
4. **系统资源**: 确保足够的内存和磁盘空间

## 🤝 贡献指南

### 开发环境设置
```bash
# 克隆项目
git clone https://github.com/kure29/VPSMonitorBot.git
cd VPSMonitorBot

# 设置开发环境
python3 -m venv dev-env
source dev-env/bin/activate
pip install -r requirements.txt
pip install -r dev-requirements.txt  # 开发依赖

# 运行测试
python -m pytest tests/
```

### 代码规范
- 使用Black进行代码格式化
- 遵循PEP 8编码规范
- 添加类型注解
- 编写单元测试

## 📝 更新日志

### v2.1.0 (当前版本)
- ✨ 添加管理员权限控制
- 🔔 实现聚合通知和冷却机制
- 📝 支持Markdown格式通知
- 🎨 扩展监控数据字段
- 🛠️ 修复install.sh兼容性问题
- 📚 完善文档和注释

### v2.0.0
- 🤖 完全重构代码架构
- 🚀 性能优化和异步改进
- 🎨 用户界面优化
- 🛡️ 增强错误处理和稳定性

### v1.0.0
- 🎉 初始版本发布
- 📝 基础监控功能
- 💻 命令行管理界面

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 👨‍💻 作者

- **kure29** - *项目作者*
- 网站: [https://kure29.com](https://kure29.com)
- GitHub: [@kure29](https://github.com/kure29)

## 🆘 支持

- 🐛 问题反馈: [GitHub Issues](https://github.com/kure29/VPSMonitorBot/issues)
- 📖 文档: [项目Wiki](https://github.com/kure29/VPSMonitorBot/wiki)
- 💬 交流群组: [Telegram Group](https://t.me/vpsmonitor)

---

⭐ 如果这个项目对你有帮助，请给个星标支持！

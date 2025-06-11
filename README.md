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
- **状态持久化**: 更好的状态跟踪和数据一致性
- **配置验证**: 自动验证配置文件格式和内容

#### 🤖 **Telegram Bot 增强**
- **更好的用户界面**: 改进的按钮和交互设计
- **状态反馈**: 实时的操作状态反馈
- **错误提示**: 更友好的错误消息和帮助信息
- **批量操作**: 支持批量管理监控项

#### 🔍 **监控功能优化**
- **智能检测**: 改进的库存状态检测算法
- **多编码支持**: 自动处理多种字符编码
- **防反爬**: 更好的反爬虫策略和请求头管理
- **URL清理**: 自动清理不必要的URL参数

#### 🛠️ **Shell脚本优化**
- **系统检测**: 自动检测操作系统并适配包管理器
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
chmod +x menu.sh
./menu.sh
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
| `/add` | 添加新的监控商品 |
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
1. **输入商品名称**: 例如 "Racknerd 2G VPS"
2. **输入配置信息**: 例如 "2GB RAM, 20GB SSD"（可选）
3. **输入监控URL**: 必须以 `http://` 或 `https://` 开头
4. **自动测试**: 系统会立即检查URL状态

## ⚙️ 配置说明

### config.json 配置文件
```json
{
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID", 
    "check_interval": 300,
    "max_notifications": 3,
    "request_timeout": 30,
    "retry_delay": 60
}
```

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `bot_token` | Telegram Bot Token | 必填 |
| `chat_id` | Telegram Chat ID | 必填 |
| `check_interval` | 检查间隔（秒） | 300 |
| `max_notifications` | 最大通知次数 | 3 |
| `request_timeout` | 请求超时时间 | 30 |
| `retry_delay` | 重试延迟时间 | 60 |

### 获取 Telegram 配置
1. **创建Bot**: 向 [@BotFather](https://t.me/BotFather) 发送 `/newbot`
2. **获取Chat ID**: 向 [@userinfobot](https://t.me/userinfobot) 发送 `/start`
3. **激活Bot**: 向你的Bot发送任意消息建立对话

## 🔧 高级功能

### 系统状态检查
使用菜单选项9可以查看：
- 系统基本信息
- 磁盘和内存使用情况
- 网络连接状态
- 文件完整性检查
- Python环境状态

### 日志管理
支持多种日志查看方式：
- 查看最近50/100行日志
- 实时日志查看（tail -f）
- 关键词搜索
- 自动日志轮转

### URL测试功能
添加商品时可以：
- 验证URL格式
- 测试URL可访问性
- 预检查库存状态
- 检测页面编码

## 📊 监控逻辑

### 库存检测算法
1. **页面获取**: 使用cloudscraper绕过Cloudflare保护
2. **内容分析**: 智能识别缺货/有货关键词
3. **状态判断**: 综合多种指标判断库存状态
4. **变化检测**: 只在状态变化时发送通知

### 通知策略
- **状态变化**: 无货→有货或有货→无货时立即通知
- **持续有货**: 有货状态下最多通知3次
- **错误处理**: 检查失败时发送错误通知

### 防反爬策略
- 随机延迟请求
- 轮换User-Agent
- 自动清理URL参数
- 智能重试机制

## 🛡️ 安全与隐私

- **配置加密**: 敏感信息本地存储
- **日志脱敏**: 自动脱敏敏感信息
- **权限控制**: 最小权限原则
- **数据备份**: 自动备份重要数据

## 🔧 故障排除

### 常见问题

**Q: 监控程序启动失败**
```bash
# 检查日志
tail -f monitor.log

# 检查Python环境
source venv/bin/activate
python3 monitor.py
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
1. **检查间隔**: 不建议低于60秒
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
- ✨ 完全重构代码架构
- 🚀 性能优化和异步改进
- 🎨 用户界面优化
- 🛡️ 增强错误处理和稳定性
- 📚 完善文档和注释

### v2.0.0
- 🤖 添加Telegram Bot集成
- 📊 改进库存检测算法
- 🔄 支持实时状态监控
- 💾 JSON数据存储格式

### v1.0.0
- 🎉 初始版本发布
- 📝 基础监控功能
- 💻 命令行管理界面

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 👨‍💻 作者

- **jinqian** - *项目维护者*
- 网站: [https://kure29.com](https://kure29.com)
- 演示Bot: [@JQ_VPSMonitorBot](https://t.me/JQ_VPSMonitorBot)

## 🆘 支持

- 📧 邮箱: [联系邮箱]
- 💬 Telegram: [@your_telegram]
- 🐛 问题反馈: [GitHub Issues](https://github.com/kure29/VPSMonitorBot/issues)
- 📖 文档: [项目Wiki](https://github.com/kure29/VPSMonitorBot/wiki)

---

⭐ 如果这个项目对你有帮助，请给个星标支持！

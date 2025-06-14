#!/usr/bin/env python3
"""
VPS监控系统 v3.1 - 多用户智能监控版
主程序入口文件

作者: kure29
网站: https://kure29.com

功能特点：
- 多用户支持，所有人可添加监控
- 管理员权限控制
- 智能组合监控算法
- 用户行为统计和管理
- 完整的管理员工具
- 调试功能集成
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / "src"
if src_dir.exists():
    sys.path.insert(0, str(src_dir))

# 设置项目路径
from utils import setup_project_paths

# 设置项目路径
if __name__ == '__main__':
    PROJECT_ROOT = setup_project_paths()

# 导入主监控器
from main_monitor import VPSMonitor


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


async def main():
    """主函数"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    print("🤖 VPS监控系统 v3.1 - 多用户智能监控版")
    print("👨‍💻 作者: kure29")
    print("🌐 网站: https://kure29.com")
    print("🆕 新功能: 多用户+智能算法+多重验证+置信度评分+完整管理工具")
    print("=" * 80)
    
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
        print("4. 安装selenium: pip install selenium webdriver-manager")
        print("5. 查看monitor.log获取详细错误信息")
        print("6. 确保admin_ids配置正确（多用户版必需）")
        print("7. 检查vendor_optimization.py文件是否存在")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已停止")
    except Exception as e:
        print(f"程序发生错误: {e}")

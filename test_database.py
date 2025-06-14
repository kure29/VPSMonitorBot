#!/usr/bin/env python3
"""
数据库测试脚本
解决模块导入问题的独立测试程序
"""

import asyncio
import sys
import os
import traceback
from pathlib import Path

def setup_python_path():
    """设置Python模块搜索路径"""
    current_dir = Path(__file__).parent
    
    # 可能的模块路径
    possible_paths = [
        current_dir,  # 当前目录
        current_dir / "src",  # src目录
        current_dir.parent,  # 上级目录
        current_dir.parent / "src"  # 上级的src目录
    ]
    
    # 查找database_manager.py
    db_manager_path = None
    for path in possible_paths:
        if (path / "database_manager.py").exists():
            db_manager_path = str(path)
            break
    
    if not db_manager_path:
        print("❌ 未找到 database_manager.py 文件")
        print("请确保文件存在于以下任一位置：")
        for path in possible_paths:
            print(f"  - {path / 'database_manager.py'}")
        return False
    
    # 添加到Python路径
    if db_manager_path not in sys.path:
        sys.path.insert(0, db_manager_path)
    
    print(f"✅ 找到数据库管理器: {db_manager_path}/database_manager.py")
    return True

async def test_database_functionality():
    """测试数据库功能"""
    try:
        # 动态导入数据库管理器
        from database_manager import DatabaseManager
        print("✅ database_manager模块导入成功")
        
        # 初始化数据库管理器
        db = DatabaseManager('test_multiuser_db.db')
        await db.initialize()
        print('✅ 多用户数据库初始化成功')
        
        # 测试用户管理
        user = await db.add_or_update_user(
            user_id='test_user_123',
            username='testuser',
            first_name='Test',
            last_name='User'
        )
        print(f'✅ 用户管理测试成功: {user.username}')
        
        # 测试监控项管理
        item_id, success = await db.add_monitor_item(
            user_id='test_user_123',
            name='测试监控项',
            url='https://example.com/test',
            config='test config',
            tags=['测试'],
            is_global=False
        )
        
        if success:
            print(f'✅ 监控项管理测试成功: {item_id}')
        else:
            print('❌ 监控项管理测试失败')
            return False
        
        # 测试监控项获取
        items = await db.get_monitor_items(user_id='test_user_123')
        print(f'✅ 监控项获取测试成功: 找到 {len(items)} 个项目')
        
        # 测试统计功能
        stats = await db.get_user_statistics('test_user_123')
        print(f'✅ 统计功能测试成功')
        
        # 测试全局统计
        global_stats = await db.get_global_statistics()
        print(f'✅ 全局统计测试成功')
        
        # 清理测试数据
        if os.path.exists('test_multiuser_db.db'):
            os.remove('test_multiuser_db.db')
            print('✅ 测试数据清理完成')
        
        return True
        
    except ImportError as e:
        print(f'❌ 模块导入失败: {e}')
        print('💡 请检查：')
        print('  1. database_manager.py 文件是否存在')
        print('  2. 虚拟环境是否已激活')
        print('  3. 依赖包是否已安装 (pip install -r requirements.txt)')
        return False
        
    except Exception as e:
        print(f'❌ 数据库测试失败: {e}')
        print('\n详细错误信息:')
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🔍 开始多用户数据库功能测试")
    print("=" * 50)
    
    # 设置Python路径
    if not setup_python_path():
        sys.exit(1)
    
    # 运行异步测试
    try:
        result = asyncio.run(test_database_functionality())
        if result:
            print("\n" + "=" * 50)
            print("✅ 所有数据库测试通过！")
            sys.exit(0)
        else:
            print("\n" + "=" * 50)
            print("❌ 数据库测试失败")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n❌ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试执行出错: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

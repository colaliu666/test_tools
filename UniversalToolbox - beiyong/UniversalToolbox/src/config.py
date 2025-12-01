# config.py

import pathlib
import sys
import time
import importlib
import traceback
from typing import Any, Callable

# ----------------------------------------------------------------------
# 1. 核心路径设置
# ----------------------------------------------------------------------

# 获取 config.py 脚本所在的目录，即项目根目录
APP_DIR = pathlib.Path(__file__).resolve().parent
CONFIG_DIR = APP_DIR / "config"
PLUGIN_DIR = APP_DIR / "plugins"

# 确保必要的目录存在
CONFIG_DIR.mkdir(exist_ok=True)
PLUGIN_DIR.mkdir(exist_ok=True)

# ----------------------------------------------------------------------
# 2. 日志和安全调用函数 (在 GUI 初始化前使用)
# ----------------------------------------------------------------------

def log(*args, level="INFO"):
    """
    默认日志函数。
    主程序启动 GUI 后，它会被 ToolboxApp 实例中的 log_to_console 方法覆盖，
    从而将日志输出重定向到 GUI 的 Log 文本框。
    """
    timestamp = time.strftime("%H:%M:%S")
    # 默认输出到标准控制台/终端
    print(f"[{timestamp}] [{level}] [CORE] {' '.join(str(a) for a in args)}")

def safe_call(func: Callable, *args, **kwargs) -> Any:
    """
    安全地执行一个函数，捕获任何异常，记录错误，并返回 None。
    这防止插件或工具中的错误导致主应用程序崩溃。
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        # 使用配置中的 log 函数记录错误
        func_name = getattr(func, '__name__', 'anonymous')
        log(f"[ERROR] Safe call failed on {func_name}: {type(e).__name__}: {e}", level="ERROR")
        # 如果需要详细调试信息，可以取消注释下面一行
        # log(traceback.format_exc(), level="DEBUG") 
        return None

# ----------------------------------------------------------------------
# 3. 插件发现逻辑
# ----------------------------------------------------------------------

def discover_plugins() -> list[tuple[str, Any, dict]]:
    """
    扫描 PLUGIN_DIR 目录，导入或重载所有 .py 文件作为插件。
    返回 (插件名称, 模块对象, 元数据字典) 的列表。
    """
    log("Scanning plugin directory for modules...", level="INFO")
    discovered = []
    
    # 确保项目根目录在 sys.path 中，以便进行绝对导入（例如 'plugins.tool_name'）
    # 尽管主程序已做此操作，在此处再次检查确保安全
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))

    # 遍历 plugins 目录下的所有 Python 文件
    for file in PLUGIN_DIR.glob('*.py'):
        if file.name.startswith(('__', '.')): 
            continue
        
        # 构造模块名：例如 'plugins.test_tool'
        module_name = f"{PLUGIN_DIR.name}.{file.stem}"
        
        try:
            # 导入或重载模块
            if module_name in sys.modules:
                # 模块已在内存中，执行热重载
                module = importlib.reload(sys.modules[module_name])
                log(f"Plugin reloaded: {file.stem}")
            else:
                # 首次导入模块
                module = importlib.import_module(module_name)
                log(f"Plugin loaded: {file.stem}")
            
            # 获取插件元数据
            meta = getattr(module, 'PLUGIN_META', {
                'name': file.stem,
                'version': 'N/A',
                'description': 'No description provided.'
            })
            
            discovered.append((meta['name'], module, meta))
            
        except Exception as e:
            log(f"[ERROR] Failed to load plugin {file.stem}: {e}", level="ERROR")
            
    log(f"Plugin scan complete. Found {len(discovered)} plugins.", level="INFO")
    return discovered

# ----------------------------------------------------------------------
# 4. 全局配置变量 (可选，可在主程序中引用)
# ----------------------------------------------------------------------

# GUI_THEME = "superhero"
# DEFAULT_FONT_SIZE = 11
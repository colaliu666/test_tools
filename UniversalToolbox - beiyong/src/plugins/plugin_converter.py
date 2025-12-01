import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import os
import sys

# ------------------------------------------------
# 0. Plugin Metadata (插件元数据)
# ------------------------------------------------
# 显式定义插件名称，帮助主应用正确识别和显示。
name = "Script Converter (Register Tool)" 
# 增加大写变量 PLUGIN_NAME，以兼容可能只查找大写名称的加载器。
PLUGIN_NAME = name
# 标准插件系统通常需要一个 __version__ 变量
__version__ = "1.1.0"

# ------------------------------------------------
# 1. Plugin UI Setup (插件用户界面设置)
# ------------------------------------------------

def _show_conversion_ui(app, parent_frame):
    """Sets up the main conversion tool UI components, called after user confirmation."""
    for widget in parent_frame.winfo_children():
        widget.destroy()
        
    main_container = ttk.Frame(parent_frame, padding=20)
    main_container.pack(fill="both", expand=True)

    # 标题
    ttk.Label(main_container, text="插件自动转换工具 (Plugin Converter)", 
              font=("Segoe UI", 16, "bold"), bootstyle="primary").pack(anchor="w", pady=(0, 20))
    
    ttk.Label(main_container, 
              text="该工具会自动为选定的 Python 脚本添加插件所需的 `register(app, parent_frame)` 函数样板。", 
              wraplength=700).pack(anchor="w", pady=(0, 10))
    
    # File Path Input (文件路径输入)
    file_path_var = tk.StringVar()
    
    path_frame = ttk.Frame(main_container)
    path_frame.pack(fill="x", pady=5)
    
    ttk.Entry(path_frame, textvariable=file_path_var, width=60, bootstyle="info").pack(side="left", fill="x", expand=True, padx=(0, 5))
    
    def browse_file():
        """打开文件对话框选择目标脚本"""
        path = filedialog.askopenfilename(
            title="选择要转换的脚本文件",
            filetypes=[("Python Files", "*.py")]
        )
        if path:
            file_path_var.set(path)
            app.update_status(f"Selected: {os.path.basename(path)}")
            
    ttk.Button(path_frame, text="浏览...", command=browse_file, bootstyle="secondary").pack(side="left")

    # Conversion Button (转换按钮 - 触发核心逻辑)
    ttk.Button(main_container, 
               text="⚡ 转换脚本并添加 register 函数 (一键打卡)", 
               # FIX: Removed app.safe_call() which caused the AttributeError
               command=lambda: convert_script(file_path_var.get(), app), 
               bootstyle="success").pack(fill="x", pady=20)

    ttk.Separator(main_container).pack(fill="x", pady=10)
    
    # Status/Guidance Area (重要提示区域)
    ttk.Label(main_container, text="** 转换后 - 立即打卡指南 **", font=("Segoe UI", 12, "bold"), bootstyle="warning").pack(anchor="w")
    ttk.Label(main_container, text="1. 此工具只添加了入口函数。您必须手动打开转换后的脚本。\n"
                                   "2. **将原脚本的核心 UI 逻辑 (例如创建按钮、标签的代码) 剪切并粘贴到 `register` 函数内部。**\n"
                                   "3. 如果原脚本使用了 `root` 作为主窗口，请将所有 UI 组件的父级从 `root` 更改为 `parent_frame`。",
              justify="left", wraplength=700).pack(anchor="w", pady=5)
    
    app.update_status(f"{name} UI loaded. Ready for script conversion.")


def register(app, parent_frame):
    """
    Plugin entry point for the Script Converter tool with confirmation dialog.
    """
    
    # 1. 弹窗询问是否继续
    confirm = messagebox.askyesno(
        title="插件转换工具确认",
        message="是否自动修改您的其他脚本以适合 plugins/ 目录下的插件识别和加载？\n\n(选择“是”将加载转换工具界面)"
    )
    
    # 2. 根据用户选择决定后续操作
    if confirm:
        # 如果用户选择“是”，则加载完整的转换 UI
        _show_conversion_ui(app, parent_frame)
    else:
        # 如果用户选择“否”，则清空容器并显示取消消息
        for widget in parent_frame.winfo_children():
            widget.destroy()
            
        cancel_frame = ttk.Frame(parent_frame, padding=20)
        cancel_frame.pack(fill="both", expand=True)
        
        ttk.Label(cancel_frame, 
                  text="操作已取消。插件转换工具未加载。", 
                  font=("Segoe UI", 14, "italic"),
                  bootstyle="warning").pack(pady=50)
        
        app.update_status(f"{name} loading cancelled by user.")


# ------------------------------------------------
# 2. Conversion Core Logic (转换核心逻辑)
# ------------------------------------------------

REGISTER_BOILERPLATE = """

# --- [ Universal Toolbox Plugin Entry Point - 插件注册入口 ] ---
# 请将您脚本的核心 UI/逻辑代码移至此函数内。
# 'parent_frame' 是插件界面的容器。
import tkinter as tk
from tkinter import ttk

def register(app, parent_frame):
    \"\"\"
    将脚本注册为 Universal Toolbox 的插件。
    app: 主应用实例，用于访问日志、状态栏等。
    parent_frame: 插件UI的容器 frame。
    \"\"\"
    # 清空容器 frame，确保插件干净加载
    for widget in parent_frame.winfo_children():
        widget.destroy()

    # ------------------------------------------------
    # ⬇️ 请将您的脚本核心逻辑从这里开始粘贴 ⬇️
    # ------------------------------------------------
    
    ttk.Label(parent_frame, text="✅ 插件已加载。请手动将您的脚本逻辑粘贴到此处。", 
              font=('Segoe UI', 12, 'italic')).pack(padx=20, pady=20)

    # ------------------------------------------------
    # ⬆️ 请将您的脚本核心逻辑粘贴到这里 ⬆️
    # ------------------------------------------------
    
    # 提示: 如果原脚本使用 'root' 作为主窗口，请替换为 'parent_frame'
    app.update_status(f"Plugin loaded via register function.")

# --- [ End of Plugin Entry Point ] ---
"""

def convert_script(filepath, app):
    """
    读取目标脚本并追加插件样板代码。
    """
    if not filepath or not os.path.exists(filepath):
        messagebox.showerror("错误", "请选择一个有效的文件路径。")
        return

    # 安全检查：防止自我转换
    try:
        # 使用 os.path.realpath 确保路径一致性
        current_plugin_path = os.path.realpath(__file__)
        target_file_path = os.path.realpath(filepath)
        
        if target_file_path == current_plugin_path:
            messagebox.showwarning("警告", "不能将插件入口函数添加到插件转换工具本身。操作中止。")
            app.update_status("Conversion skipped: Attempted self-conversion.")
            return
    except NameError:
        # __file__ may not be defined in all environments, skip check if necessary
        pass

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 简单检查是否已存在 register 函数
        if "def register(app, parent_frame):" in content:
            messagebox.showwarning("警告", f"文件 {os.path.basename(filepath)} 似乎已包含 'register' 函数。操作中止。")
            app.update_status("Conversion skipped: 'register' function found.")
            return

        # 追加样板代码到文件末尾
        new_content = content + REGISTER_BOILERPLATE

        # 写回文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # 成功反馈与日志记录（即“打卡”）
        messagebox.showinfo("成功", f"脚本 {os.path.basename(filepath)} 已成功修改并添加了插件入口！\n\n请手动将核心逻辑移动到新添加的 register 函数中。")
        # 替换 app.log 为 print
        print(f"✅ Conversion successful (Check-in): '{filepath}' was modified to include the plugin entry point.")
        app.update_status(f"Script converted: {os.path.basename(filepath)}. Ready for manual logic move.")

    except Exception as e:
        messagebox.showerror("错误", f"修改文件时发生错误: {e}")
        # 替换 app.log 为 print
        print(f"❌ Conversion failed for {filepath}: {e}")
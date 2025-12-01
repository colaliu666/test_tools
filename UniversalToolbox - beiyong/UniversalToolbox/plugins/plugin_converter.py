import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import os
import sys
import pathlib
import re # 导入正则表达式模块用于文件修改

# ------------------------------------------------
# 0. Plugin Metadata (插件元数据)
# ------------------------------------------------
name = "Script Converter (Register Tool)" 
PLUGIN_NAME = name
__version__ = "1.4.1" # 版本号更新以反映修改
# ！！！ 保持此描述为默认值，以便触发修改弹窗 ！！！
PLUGIN_META = {
    'name': name,
    'version': __version__,
    'description': 'No description provided', # 默认值，加载时将触发弹窗
    'author': 'AI Assistant'
}

# ------------------------------------------------
# 1. Plugin UI Setup (插件用户界面设置)
# ------------------------------------------------

def _update_current_plugin_description(new_description):
    """
    修改当前插件文件中的 PLUGIN_META 描述，确保更改反映在 Available Description 列表中。
    （仅依靠精确的正则表达式进行匹配和替换）
    """
    filepath = os.path.realpath(__file__)
    if not os.path.exists(filepath):
        print("Error: Cannot find plugin file to update description.")
        return False

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 构造新的描述字符串，转义内部的单引号，以确保写入时不会破坏 Python 字符串定义
        new_description_safe = new_description.replace("'", "\\'")
        
        # 正则表达式匹配 'description' 键及其值。
        # 匹配模式：('description':\s*)(\"|')([^\"']*?)(\"|')
        # 兼容单引号和双引号，并捕获引号以便写回
        pattern = r"('description':\s*)([\"'])([^\"']*?)([\"'])"
        
        # 替换函数：替换匹配到的值
        def replacer(match):
            # match.group(1) 是键名和冒号 ('description': )
            # match.group(2) 是起始引号 (" 或 ')
            # match.group(4) 是结束引号 (" 或 ')
            return match.group(1) + match.group(2) + new_description_safe + match.group(4)
            
        new_content = re.sub(pattern, replacer, content, count=1)

        if new_content == content:
            # 如果内容没有改变，则表示没有找到匹配项
            print("Error: Cannot find standard 'description' line in PLUGIN_META to update. Please check the metadata format.")
            return False

        # 写回文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"✅ Plugin description successfully updated to: {new_description}")
        return True

    except Exception as e:
        print(f"❌ Error updating plugin file description: {e}")
        # 使用 Tkinter 消息框显示错误，确保用户可以看到
        messagebox.showerror("更新错误", f"无法修改插件文件（请检查权限）：{e}")
        return False
    
def _update_external_plugin_meta_in_file(filepath, updates):
    """
    通用地修改目标插件文件中的 PLUGIN_NAME, __version__ 变量以及 PLUGIN_META 字典中的多个字段。
    """
    if not os.path.exists(filepath):
        print(f"Error: Cannot find target plugin file: {filepath}")
        return False

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        new_content = content
        
        # --- 1. 更新顶部变量 (PLUGIN_NAME, __version__) ---
        top_vars = {
            'PLUGIN_NAME': updates.get('name_var'), 
            '__version__': updates.get('version_var')
        }
        
        for var_name, new_value in top_vars.items():
            if new_value:
                # 匹配模式: (VARIABLE_NAME\s*=\s*)(["'])(.*?)(["'])
                pattern = re.compile(rf"({var_name}\s*=\s*)([\"'])(.*?)([\"'])")
                
                def replacer(match):
                    # match.group(1) 是变量名和等号 (e.g., PLUGIN_NAME = )
                    # match.group(2/4) 是引号
                    return match.group(1) + match.group(2) + new_value.strip() + match.group(4)

                new_content, count = pattern.subn(replacer, new_content, count=1)
                if count > 0:
                    print(f"Updated top variable: {var_name}")
                else:
                    print(f"Warning: Could not find top variable '{var_name}' to update.")


        # --- 2. 更新 PLUGIN_META 字典中的键 ---
        meta_updates = {
            'name': updates.get('name_meta'),
            'version': updates.get('version_meta'),
            'description': updates.get('description'),
            'author': updates.get('author')
        }

        for key, value in meta_updates.items():
            if value is not None: # 只有当用户提供了值时才尝试修改
                # 转义内部的引号和换行符
                value_safe = value.replace("'", "\\'").replace('\n', '\\n').strip()
                
                # 正则表达式匹配指定的 key 及其值。
                # 匹配模式: ('key':\s*)(["'])(.*?)(["'])
                pattern = re.compile(rf"('{key}':\s*)([\"'])(.*?)([\"'])", re.DOTALL)
                
                def replacer(match):
                    # match.group(1) 是键名和冒号 ('key': )
                    # match.group(2) 是起始引号 (" 或 ')
                    # match.group(4) 是结束引号 (" 或 ')
                    return match.group(1) + match.group(2) + value_safe + match.group(4)

                # 替换，只替换第一次找到的匹配（PLUGIN_META 中）
                new_content, count = pattern.subn(replacer, new_content, count=1)
                
                if count == 0:
                    print(f"Warning: Could not find key '{key}' in PLUGIN_META to update in {os.path.basename(filepath)}.")

        if new_content == content:
            print(f"Warning: No changes were applied to {os.path.basename(filepath)}. Check if keys exist or values are identical.")
            return False

        # 写回文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"✅ Plugin metadata successfully updated in: {os.path.basename(filepath)}")
        return True

    except Exception as e:
        print(f"❌ Error updating external plugin file metadata: {e}")
        messagebox.showerror("更新错误", f"无法修改插件文件 ({os.path.basename(filepath)})：{e}")
        return False


def _prompt_for_description_update(app):
    """
    弹出对话框，让用户输入新的插件描述，并尝试更新文件。
    （仅用于本插件 Script Converter 自身的描述更新）
    """
    default_desc = PLUGIN_META.get('description', 'No description provided').strip()
    
    # 仅当描述是默认值时才提示
    if default_desc != 'No description provided' and default_desc != '':
        return

    # 创建一个简单的输入窗口
    input_window = tk.Toplevel(app.root)
    input_window.title("修改插件描述")
    input_window.geometry("400x180")
    input_window.transient(app.root) 
    input_window.grab_set() 

    ttk.Label(input_window, 
              text="请为本插件输入一个有意义的描述：", 
              font=("Segoe UI", 10, "bold")).pack(pady=10, padx=10)
    
    ttk.Label(input_window, 
              text="（**重要：修改后请重启或刷新主应用，才能在列表中看到新描述**）", 
              font=("Segoe UI", 9, "italic"), bootstyle="warning").pack(pady=(0, 5), padx=10)


    desc_var = tk.StringVar(value=default_desc)
    entry = ttk.Entry(input_window, textvariable=desc_var, width=50)
    entry.pack(pady=5, padx=10)
    entry.focus_set()

    def on_ok():
        new_desc = desc_var.get().strip()
        if new_desc:
            _update_current_plugin_description(new_desc) # 调用专门的函数
        input_window.destroy()

    def on_cancel():
        input_window.destroy()

    button_frame = ttk.Frame(input_window)
    button_frame.pack(pady=10)
    
    ttk.Button(button_frame, text="确认更新", command=on_ok, bootstyle="success").pack(side="left", padx=5)
    ttk.Button(button_frame, text="取消/稍后", command=on_cancel, bootstyle="danger").pack(side="left", padx=5)

    try:
        app.root.wait_window(input_window) 
    except tk.TclError:
        pass


def _prompt_for_external_meta_update(app, filepath):
    """
    弹出对话框，让用户输入目标插件文件的 Name, Version, Description, Author。
    并尝试从文件顶部变量和 PLUGIN_META 字典中读取当前值。
    """
    if not filepath:
        messagebox.showwarning("警告", "请先选择一个插件文件！")
        return
        
    filename = os.path.basename(filepath)
    
    # 尝试从文件中读取当前元数据
    current_meta = {
        'name_var': '', 'version_var': '', # 顶部变量
        'name_meta': '', 'version_meta': '', 'description': '', 'author': '' # 字典键
    }
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
            def find_var(var_name):
                # 查找顶部的 PLUGIN_NAME 或 __version__ 变量
                match = re.search(rf"^{var_name}\s*=\s*([\"'])(.*?)\1", content, re.MULTILINE)
                if match:
                    return match.group(2).strip()
                return ''

            def find_meta(key):
                # 查找 PLUGIN_META 字典中的键
                # \1 是反向引用，确保开头和结尾引号一致
                # re.DOTALL 允许 . 匹配换行符
                match = re.search(rf"'{key}':\s*([\"'])(.*?)\1", content, re.DOTALL)
                if match:
                    # 还原换行符，以便在文本框中显示多行
                    return match.group(2).replace('\\n', '\n').strip() 
                return ''

            # 读取所有值
            current_meta['name_var'] = find_var('PLUGIN_NAME')
            current_meta['version_var'] = find_var('__version__')
            current_meta['name_meta'] = find_meta('name')
            current_meta['version_meta'] = find_meta('version')
            current_meta['description'] = find_meta('description')
            current_meta['author'] = find_meta('author')
            
            # 使用更可靠的 meta 值作为默认显示
            default_display_name = current_meta['name_meta'] or current_meta['name_var'] or f"N/A ({filename})"
            default_display_version = current_meta['version_meta'] or current_meta['version_var'] or "N/A"
            default_display_author = current_meta['author'] or "N/A"
            default_display_desc = current_meta['description'] or "No description found."
            
    except Exception as e:
        messagebox.showerror("读取错误", f"无法读取文件元数据：{e}")
        return

    # 创建输入窗口
    input_window = tk.Toplevel(app.root)
    input_window.title(f"编辑插件元数据: {filename}")
    input_window.geometry("550x450")
    input_window.transient(app.root) 
    input_window.grab_set() 

    main_frame = ttk.Frame(input_window, padding=10)
    main_frame.pack(fill="both", expand=True)

    ttk.Label(main_frame, text=f"正在编辑：{filename}", 
              font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))
    
    ttk.Label(main_frame, text="提示：此工具将同时修改顶部变量（如 PLUGIN_NAME）和 PLUGIN_META 字典中的对应键。", 
              font=("Segoe UI", 9, "italic"), bootstyle="secondary").pack(anchor="w", pady=(0, 5))

    # --- 输入字段 ---
    fields = [
        ('name_var', '插件名称 (变量)', default_display_name), 
        ('version_var', '插件版本 (变量)', default_display_version),
        ('author', '作者 (META)', default_display_author),
        ('description', '描述 (META)', default_display_desc)
    ]
    
    # 跟踪变量，以便在 on_ok 中获取最新值
    vars_ = {f[0]: tk.StringVar(value=f[2]) for f in fields}

    for field_key, label_text, default_val in fields:
        if field_key != 'description':
            row = ttk.Frame(main_frame)
            row.pack(fill="x", pady=2)
            
            ttk.Label(row, text=label_text + ":", width=16).pack(side="left")
            entry = ttk.Entry(row, textvariable=vars_[field_key], width=50)
            entry.pack(side="left", fill="x", expand=True)
        else:
            # 描述字段使用 ScrolledText 允许多行输入
            ttk.Label(main_frame, text="描述 (META):", width=16).pack(anchor="w", pady=(5, 0))
            desc_text = scrolledtext.ScrolledText(main_frame, height=6, width=50, wrap="word", font=('Segoe UI', 10))
            desc_text.insert(tk.END, default_val)
            desc_text.pack(fill="x", pady=(0, 10))
            
    # --- 确认/取消按钮 ---
    def on_ok():
        # 构建一个包含所有更新的字典
        updates = {
            # 顶部变量
            'name_var': vars_['name_var'].get().strip(),
            'version_var': vars_['version_var'].get().strip(),
            
            # PLUGIN_META 字典键 (将顶部变量的值也映射到 META 键上)
            'name_meta': vars_['name_var'].get().strip(),
            'version_meta': vars_['version_var'].get().strip(),
            'description': desc_text.get('1.0', tk.END).strip(),
            'author': vars_['author'].get().strip()
        }

        # 过滤掉空值
        updates = {k: v for k, v in updates.items() if v}

        if updates:
            if _update_external_plugin_meta_in_file(filepath, updates):
                messagebox.showinfo("更新成功", 
                                    f"插件 {filename} 的元数据已更新！\n请重新加载插件列表以查看更改。", 
                                    parent=input_window)
        input_window.destroy()

    def on_cancel():
        input_window.destroy()

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill="x", pady=10)
    
    ttk.Button(button_frame, text="确认更新", command=on_ok, bootstyle="success").pack(side="left", expand=True, padx=5)
    ttk.Button(button_frame, text="取消", command=on_cancel, bootstyle="danger").pack(side="left", expand=True, padx=5)

    try:
        app.root.wait_window(input_window) 
    except tk.TclError:
        pass


def _select_file_and_prompt(app):
    """引导用户选择文件，然后弹出编辑窗口。"""
    filepath = filedialog.askopenfilename(
        title="选择要编辑元数据的插件文件 (.py)",
        filetypes=[("Python Files", "*.py")]
    )
    if filepath:
        _prompt_for_external_meta_update(app, filepath)


def _show_conversion_ui(app, parent_frame):
    """Sets up the main conversion tool UI components."""
    for widget in parent_frame.winfo_children():
        widget.destroy()
        
    main_container = ttk.Frame(parent_frame, padding=20)
    main_container.pack(fill="both", expand=True)

    # 标题
    ttk.Label(main_container, text="插件自动转换与管理工具", 
              font=("Segoe UI", 16, "bold"), bootstyle="primary").pack(anchor="w", pady=(0, 20))
    
    # ------------------- Metadata Editor Section (元数据编辑区) --- NEW
    ttk.Label(main_container, text="** 插件元数据编辑 **", font=("Segoe UI", 12, "bold"), bootstyle="info").pack(anchor="w", pady=(5, 5))
    ttk.Label(main_container, 
              text="使用此工具修改任意插件脚本中的 Name, Version, Description 和 Author 等元数据。", 
              wraplength=700).pack(anchor="w", pady=(0, 10))
    
    ttk.Button(main_container, 
               text="🖋️ 编辑其他插件的元数据...", 
               command=lambda: _select_file_and_prompt(app), 
               bootstyle="info").pack(fill="x", pady=(0, 20))
    
    ttk.Separator(main_container).pack(fill="x", pady=10)
    
    # ------------------- File Conversion Section (文件转换区) --- EXISTING
    ttk.Label(main_container, 
              text="选择要批量处理的文件夹或多个脚本文件。工具将为每个脚本添加插件所需的 `register` 函数样板。", 
              wraplength=700).pack(anchor="w", pady=(0, 10))
    
    # ------------------- 文件选择区域 -------------------
    file_list_text = scrolledtext.ScrolledText(main_container, height=8, wrap="word", font=('Consolas', 10))
    file_list_text.pack(fill="x", pady=5)
    
    # 递归处理选项
    recursive_var = tk.BooleanVar(value=False)
    
    path_frame = ttk.Frame(main_container)
    path_frame.pack(fill="x", pady=10)
    
    ttk.Checkbutton(path_frame, text="包含子文件夹中的脚本 (递归处理)", 
                    variable=recursive_var, bootstyle="round-toggle").pack(side="left", padx=10)
    
    def browse_paths():
        """打开文件/文件夹对话框选择目标路径"""
        # 首先尝试选择多个文件
        paths = filedialog.askopenfilenames(
            title="选择要转换的脚本文件",
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )
        
        # 如果没有选择文件，则提示选择文件夹
        if not paths:
            folder = filedialog.askdirectory(title="选择要批量转换的文件夹")
            if folder:
                file_list_text.delete('1.0', tk.END)
                file_list_text.insert(tk.END, folder + "\n")
                app.update_status(f"Selected Folder: {os.path.basename(folder)}")
            return
        
        # 如果选择了文件
        file_list_text.delete('1.0', tk.END)
        for path in paths:
            file_list_text.insert(tk.END, path + "\n")
            
        app.update_status(f"Selected {len(paths)} file(s).")
            
    ttk.Button(path_frame, text="选择 文件 / 文件夹...", command=browse_paths, bootstyle="secondary").pack(side="right")

    # Conversion Button (转换按钮 - 触发核心逻辑)
    ttk.Button(main_container, 
                text="⚡ 批量转换脚本并添加 register 函数", 
                command=lambda: handle_batch_conversion(file_list_text.get('1.0', tk.END).strip(), recursive_var.get(), app), 
                bootstyle="success").pack(fill="x", pady=20)

    ttk.Separator(main_container).pack(fill="x", pady=10)
    
    # Status/Guidance Area (重要提示区域)
    ttk.Label(main_container, text="** 转换后 - 立即上手指南 **", font=("Segoe UI", 12, "bold"), bootstyle="warning").pack(anchor="w")
    ttk.Label(main_container, text="1. 此工具只添加了入口函数。您必须手动打开转换后的脚本。\n"
                                 "2. **将原脚本的核心 UI 逻辑 (例如创建按钮、标签的代码) 剪切并粘贴到 `register` 函数内部。**\n"
                                 "3. 如果原脚本使用了 `root` 作为主窗口，请将所有 UI 组件的父级从 `root` 更改为 `parent_frame`。",
                     justify="left", wraplength=700).pack(anchor="w", pady=5)
    
    app.update_status(f"{name} UI loaded. Ready for batch script conversion.")


def register(app, parent_frame):
    """
    Plugin entry point for the Script Converter tool with confirmation dialog.
    """
    
    # --- 新增：检查并提示修改 description ---
    if PLUGIN_META.get('description') == 'No description provided':
        _prompt_for_description_update(app)

    # 1. 弹窗询问是否继续
    confirm = messagebox.askyesno(
        title="插件转换工具确认",
        message="是否自动修改您的其他脚本以适合 plugins/ 目录下的插件识别和加载？\n\n(选择“是”将加载批量转换工具界面)"
    )
    
    # 2. 根据用户选择决定后续操作
    if confirm:
        _show_conversion_ui(app, parent_frame)
    else:
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
    
    # 这是一个占位符，请用您的实际 UI 逻辑代码替换它。
    ttk.Label(parent_frame, text="✅ 插件已加载。请手动将您的脚本逻辑粘贴到此处。", 
              font=('Segoe UI', 12, 'italic')).pack(padx=20, pady=20)

    # ------------------------------------------------
    # ⬆️ 请将您的脚本核心逻辑粘贴到这里 ⬆️
    # ------------------------------------------------
    
    # 提示: 如果原脚本使用 'root' 作为主窗口，请替换为 'parent_frame'
    app.update_status(f"Plugin loaded via register function.")

# --- [ End of Plugin Entry Point ] ---
"""

def process_conversion(filepath, app):
    """
    读取目标脚本并追加插件样板代码的核心逻辑。
    此版本增加了对重复 register 函数的用户确认。
    """
    if not filepath or not os.path.exists(filepath):
        return False, f"Error: File not found or invalid path: {filepath}"
    
    if not filepath.lower().endswith(".py"):
        return False, f"Skipped: Not a Python file: {filepath}"

    # 安全检查：防止自我转换
    try:
        current_plugin_path = os.path.realpath(__file__)
        target_file_path = os.path.realpath(filepath)
        
        if target_file_path == current_plugin_path:
            return False, "Warning: Attempted self-conversion. Skipped."
    except NameError:
        # 在某些环境中 __file__ 可能未定义，忽略此检查
        pass

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        is_duplicate = False
        
        # --- 检查是否存在 register 函数 ---
        # 使用正则表达式进行更灵活的匹配 (如 def register(app, container):)
        if re.search(r"^\s*def\s+register\s*\(\s*app\s*,\s*parent_frame\s*\)\s*:", content, re.MULTILINE):
            is_duplicate = True
            
            # --- POPUP CONFIRMATION (用户选择是否覆盖/追加) ---
            dialog_message = (
                f"文件 '{os.path.basename(filepath)}' 中已检测到 'register' 函数。\n\n"
                f"选择 '是' (强制追加) 将在文件末尾追加新的插件入口样板。\n"
                f"**注意：追加后文件将包含两个同名函数，您需要手动移除旧的函数。**\n\n"
                f"选择 '否' (操作终止) 将跳过此文件。"
            )
            
            # 使用 app.root 作为父级
            confirm = messagebox.askyesno(
                "重复函数警告 - 确认操作",
                dialog_message,
                parent=app.root 
            )
            
            if not confirm:
                # 用户选择 '否'，跳过当前文件
                return False, "Skipped: Operation aborted by user due to existing 'register' function."
            
            # 如果用户选择了 '是'，记录警告并继续
            app.log_to_console(f"⚠️ WARNING: User chose to overwrite/append to '{os.path.basename(filepath)}', creating a duplicate function definition.")
            
        # 追加样板代码到文件末尾 (如果用户选择了 '是' 或者原本就没有重复)
        new_content = content + REGISTER_BOILERPLATE

        # 写回文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # 成功反馈
        if is_duplicate:
            return True, "Success: Appended new entry point (Manual cleanup required)."
        else:
            return True, "Success: Plugin entry point added."

    except Exception as e:
        return False, f"Error modifying file: {e}"


def handle_batch_conversion(path_input, recursive, app):
    """
    处理批量的文件或文件夹路径输入，并调用核心转换逻辑。
    """
    if not path_input:
        messagebox.showerror("错误", "请选择至少一个文件或文件夹。")
        return

    # 解析路径输入
    paths = [p.strip() for p in path_input.split('\n') if p.strip()]
    
    file_list = []
    
    for path in paths:
        p = pathlib.Path(path)
        if not p.exists():
            app.log_to_console(f"Path not found: {path}")
            continue

        if p.is_file() and p.suffix.lower() == '.py':
            file_list.append(str(p))
        elif p.is_dir():
            if recursive:
                # 递归查找所有 .py 文件
                for f in p.rglob('*.py'):
                    if f.is_file():
                        file_list.append(str(f))
            else:
                # 只查找顶层 .py 文件
                for f in p.glob('*.py'):
                    if f.is_file():
                        file_list.append(str(f))
    
    if not file_list:
        messagebox.showwarning("警告", "在选定的路径中未找到有效的 Python (.py) 脚本进行转换。")
        app.update_status("Batch conversion aborted: No valid scripts found.")
        return

    # 去重并开始处理
    unique_files = sorted(list(set(file_list)))
    total_files = len(unique_files)
    
    converted_count = 0
    
    app.log_to_console(f"Starting batch conversion for {total_files} files...")
    
    for idx, filepath in enumerate(unique_files):
        app.update_status(f"Processing ({idx+1}/{total_files}): {os.path.basename(filepath)}")
        
        is_success, message = process_conversion(filepath, app)
        
        log_prefix = "✅" if is_success and "Warning" not in message else ("⚠️" if "Warning" in message else "❌")
        app.log_to_console(f"{log_prefix} [{idx+1}/{total_files}] {os.path.basename(filepath)} - {message}")
        
        if is_success:
            converted_count += 1

    # 最终结果反馈
    app.update_status(f"Batch conversion finished. Converted {converted_count}/{total_files} file(s).")
    
    summary_message = (f"批量转换完成！\n"
                      f"总文件数: {total_files}\n"
                      f"成功转换: {converted_count}\n\n"
                      f"请查看底部的控制台日志获取每个文件的详细状态。\n"
                      f"重要: 如果您选择了强制追加，请手动将核心逻辑移动到 register 函数中并清理旧的定义！")
                      
    messagebox.showinfo("批量转换结果", summary_message)
    
    app.log_to_console("Batch conversion detailed log finished.")
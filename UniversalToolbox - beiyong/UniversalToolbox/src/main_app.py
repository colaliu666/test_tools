import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Menu, simpledialog
import tkinter.font as tkFont
from collections import deque
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import pathlib 
import sys 
import importlib
import time 
import re 
import importlib.util
from typing import Optional, Any

# --- 导入配置和安全函数 ---
try:
    # 尝试导入 config.py (如果存在)
    import config 
    log = config.log
    safe_call = config.safe_call
except ImportError:
    # Fallback for missing config.py
    def log(*args): 
        # 使用 print 模拟 log，并加上时间戳
        print(f"[{time.strftime('%H:%M:%S')}] [LOG] {' '.join(str(a) for a in args)}")
        
    def safe_call(func, *args, **kwargs): 
        try: 
            return func(*args, **kwargs)
        except Exception as e: 
            # 模拟错误日志
            print(f"[{time.strftime('%H:%M:%M')}] [ERROR] Safe call failed: {e}")
            return None
        
    class ConfigPlaceholder:
        """简化配置类，用于插件发现和路径定义"""
        APP_DIR = pathlib.Path(os.getcwd())
        PLUGIN_DIR = APP_DIR / "plugins"
        
        def discover_plugins(self): 
            """发现并加载 plugins 目录下的所有 .py 文件"""
            if not self.PLUGIN_DIR.exists():
                log("Warning: Plugin directory 'plugins/' not found. Creating it.")
                self.PLUGIN_DIR.mkdir(exist_ok=True)
                return []
            
            discovered = []
            
            # 确保父目录在路径中
            if str(self.PLUGIN_DIR.parent) not in sys.path:
                sys.path.insert(0, str(self.PLUGIN_DIR.parent)) 
            
            plugin_pkg_name = self.PLUGIN_DIR.name
            
            for file in self.PLUGIN_DIR.glob('*.py'):
                if file.name.startswith(('__', '.')): continue
                module_name = f"{plugin_pkg_name}.{file.stem}" 
                
                try:
                    if module_name in sys.modules:
                        module = importlib.reload(sys.modules[module_name])
                        log(f"Plugin reloaded: {file.stem}")
                    else:
                        spec = importlib.util.spec_from_file_location(module_name, file)
                        if spec is None: continue
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)
                        log(f"Plugin loaded: {file.stem}")

                    meta = getattr(module, 'PLUGIN_META', {
                        'name': file.stem,
                        'version': 'N/A',
                        'author': 'Unknown',
                        'description': 'No description provided.'
                    })
                    
                    # 关键：使用插件 name 作为键
                    discovered.append((meta['name'], module, meta)) 
                except Exception as e:
                    log(f"[ERROR] Failed to load plugin {file.stem}: {e}")
        
            return discovered

    config = ConfigPlaceholder()
    log("Warning: config.py not found. Using internal fallback.")


# --- 辅助类：语法高亮 ---
class SyntaxHighlighter:
    PYTHON_KEYWORDS = [
        'for', 'in', 'if', 'else', 'elif', 'def', 'class', 'return', 'import', 
        'from', 'while', 'try', 'except', 'finally', 'with', 'as', 'lambda', 
        'yield', 'is', 'not', 'and', 'or', 'pass', 'break', 'continue', 'global', 
        'nonlocal', 'del', 'await', 'async'
    ]
    KEYWORD_FONT = ("Consolas", 10, "bold") 

    def __init__(self, text_widget):
        self.text = text_widget
        self.text.tag_configure("keyword", foreground="#DAA520", font=self.KEYWORD_FONT) 
        self.text.tag_configure("comment", foreground="#6A9955") 
        self.text.tag_configure("string", foreground="#CE9178") 
        self.text.tag_configure("function", foreground="#569CD6")
        
    def highlight(self):
        self._remove_tags()
        content = self.text.get("1.0", "end-1c")
        
        # 1. 关键词
        for word in self.PYTHON_KEYWORDS:
            self._apply_tag("keyword", r'\b' + word + r'\b')
            
        # 2. 字符串
        self._apply_tag("string", r'"[^"\n]*"') 
        self._apply_tag("string", r"'[^'\n]*'") 

        # 3. 注释
        self._apply_tag("comment", r'#.*$')
        
    def _remove_tags(self):
        for tag in ["keyword", "comment", "string", "function"]:
            self.text.tag_remove(tag, "1.0", "end")

    def _apply_tag(self, tag, pattern):
        start = "1.0"
        while True:
            match = self.text.search(pattern, start, stopindex="end", regexp=True)
            if not match: break
            
            pos = match
            match_end = self.text.index(f"{pos} + {len(match.group(0))} chars")
            self.text.tag_add(tag, pos, match_end)
            start = match_end


# --- 日志重定向类 ---
class ConsoleRedirector:
    def __init__(self, text_widget, app_instance):
        self.text_widget = text_widget
        self.app = app_instance
        self.buffer = ""
        
    def write(self, s):
        self.buffer += s

    def _schedule_flush(self):
        # 启动异步日志处理
        if hasattr(self.app, 'root'):
            self.app.root.after(100, self.flush) 
            self.app.root.after(100, self._schedule_flush) 

    def flush(self):
        if not self.buffer: return
        output_to_write = self.buffer
        self.buffer = "" 
        
        if not output_to_write.strip() and '\n' not in output_to_write: return 

        self.text_widget.configure(state="normal")
        self.text_widget.insert(tk.END, output_to_write, 'log') 
        self.text_widget.see(tk.END)
        self.text_widget.configure(state="disabled")

# --- 主应用类 ---

class ToolboxApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Universal Toolbox (Modular)")
        self.root.geometry("1200x780") 
        
        self.recent_files = deque(maxlen=20)
        self.open_tabs_map = {} 
        self.plugin_modules = {} 
        
        self.style_name = tk.StringVar(value="superhero") 
        self.font_size = tk.IntVar(value=11) 
        self.style = tb.Style(self.style_name.get()) 
        
        # --- UI 初始化 ---
        self._create_topbar()
        self._create_statusbar() 
        self._create_main_panes()
        self._create_context_menu()
        self._bind_global_events()

        # 延迟重定向日志，确保 log_text 存在
        self.redirect_log()
        # 启动日志刷新机制
        if isinstance(sys.stdout, ConsoleRedirector):
             sys.stdout._schedule_flush() 
        
        self.apply_theme()
        self._load_plugins()
        self._create_welcome_tab()
        
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    # ----------------------------
    # Core Utility & Setup
    # ----------------------------

    def log_to_console(self, *args, tag='log'):
        """记录日志到控制台文本框"""
        message = " ".join(str(a) for a in args) + "\n"
        if hasattr(sys.stdout, 'write'):
            sys.stdout.write(message)
            # 立即 flush 一次，确保关键信息快速显示
            if len(sys.stdout.buffer) > 256: 
                 sys.stdout.flush() 
        else:
            print(message, end='')
            
    def redirect_log(self):
        """重定向 sys.stdout 和 sys.stderr 到 GUI 文本框"""
        if hasattr(self, 'log_text'):
            global log
            log = self.log_to_console 
            
            if not isinstance(sys.stdout, ConsoleRedirector):
                sys.stdout = ConsoleRedirector(self.log_text, self)
            if not isinstance(sys.stderr, ConsoleRedirector):
                sys.stderr = sys.stdout 
            
            self.log_text.tag_configure('log', foreground="#ffffff")
            self.log_text.tag_configure('error', foreground="#dc3545", font=('Consolas', 10, 'bold'))
            self.log_text.tag_configure('warning', foreground="#ffc107")
            self.log_text.tag_configure('info', foreground="#0dcaf0")
            
    def update_status(self, text):
        if hasattr(self, 'status'):
            self.status.config(text=text)

    def apply_theme(self):
        theme = self.style_name.get()
        try:
            self.style.theme_use(theme)
            self.update_status(f"Theme: {theme}")
        except Exception as e:
            self.log_to_console(f"主题应用失败: {e}")
        self._apply_font_size()

    def _apply_font_size(self):
        fs = max(8, min(20, self.font_size.get()))
        try:
            # 更新默认字体
            tkFont.nametofont("TkDefaultFont").configure(size=fs)
            tkFont.nametofont("TkTextFont").configure(size=fs)
            
            # 更新所有文本编辑器的字体
            for frame in self.open_tabs_map:
                text_widget = next((w for w in frame.winfo_children() if isinstance(w, scrolledtext.ScrolledText)), None)
                if text_widget:
                    text_widget.configure(font=('Consolas', fs))
                    
        except Exception:
            pass 
        self.update_status(f"Theme: {self.style_name.get()} | Font: {fs}px") 

    def _adjust_font(self, delta):
        self.font_size.set(self.font_size.get() + delta)
        self._apply_font_size()
        
    def _is_tab_dirty(self, frame):
        """检查标签页内容是否被修改（脏标记）"""
        return self.open_tabs_map.get(frame, (None, False))[1]

    def _mark_tab_dirty(self, frame, is_dirty):
        """设置标签页的脏标记"""
        current_data = self.open_tabs_map.get(frame, (None, False))
        if current_data[1] != is_dirty:
            self.open_tabs_map[frame] = (current_data[0], is_dirty)
            
            for tab_id in self.notebook.tabs():
                if self.root.nametowidget(tab_id) == frame:
                    current_text = self.notebook.tab(tab_id, "text").lstrip('* ')
                    new_text = f"*{current_text}" if is_dirty else current_text
                    self.notebook.tab(tab_id, text=new_text)
                    break
                    
    def _bind_global_events(self):
        """绑定全局快捷键"""
        self.root.bind('<Control-s>', lambda e: self.save_active_file())
        self.root.bind('<Control-w>', lambda e: self.close_active_tab())
        self.root.bind('<Control-n>', lambda e: self.create_empty_tab())
        self.root.bind('<Control-o>', lambda e: self.open_file_dialog())

    # ----------------------------
    # UI Layout Methods 
    # ----------------------------

    def _create_topbar(self):
        top = ttk.Frame(self.root, padding=5) 
        top.pack(side="top", fill="x")

        # --- File Actions Group ---
        file_group = ttk.Frame(top)
        file_group.pack(side="left", padx=4)
        
        ttk.Button(file_group, text="New Tab (N)", bootstyle="info-outline",
                             command=self.create_empty_tab).pack(side="left", padx=4)
        ttk.Button(file_group, text="Open File (O)", bootstyle="secondary-outline",
                             command=self.open_file_dialog).pack(side="left", padx=4)
        ttk.Button(file_group, text="Save (S)", bootstyle="success", 
                             command=self.save_active_file).pack(side="left", padx=4)
        ttk.Button(file_group, text="Close (W)", bootstyle="danger-outline",
                             command=self.close_active_tab).pack(side="left", padx=4)
                             
        ttk.Separator(top, orient=tk.VERTICAL).pack(side="left", padx=15, fill="y")
        
        # --- System/Plugin Group ---
        system_group = ttk.Frame(top)
        system_group.pack(side="left", padx=4)
        
        ttk.Button(system_group, text="Reload Plugins", bootstyle="warning-outline",
                             command=self._load_plugins).pack(side="left", padx=4)
        
        ttk.Button(system_group, text="Refresh Explorer", bootstyle="secondary-outline",
                             command=self._refresh_workspace_tree).pack(side="left", padx=4)

        ttk.Separator(top, orient=tk.VERTICAL).pack(side="left", padx=15, fill="y")

        # --- Recent & Search Group ---
        center_group = ttk.Frame(top)
        center_group.pack(side="left", padx=4)
        
        # Recent Files
        ttk.Label(center_group, text="Recent:").pack(side="left", padx=(4,2))
        self.file_combo = ttk.Combobox(center_group, values=list(self.recent_files), width=35, state='readonly')
        self.file_combo.pack(side="left", padx=4)
        self.file_combo.bind("<<ComboboxSelected>>", self._open_selected_recent)
        
        ttk.Separator(center_group, orient=tk.VERTICAL).pack(side="left", padx=10, fill="y")
        
        # Search Functionality
        ttk.Label(center_group, text="Search Content:").pack(side="left", padx=(4,2))
        self.search_entry = ttk.Entry(center_group, width=20, bootstyle="info")
        self.search_entry.pack(side="left", padx=4)
        ttk.Button(center_group, text="Find", bootstyle="primary", command=self._start_global_search).pack(side="left", padx=4)

        # --- Theme Group ---
        theme_group = ttk.Frame(top)
        theme_group.pack(side="right", padx=4)

        ttk.Label(theme_group, text="Theme:").pack(side="right", padx=(4,2))
        themelist = sorted(self.style.theme_names()) 
        theme_combo = ttk.Combobox(theme_group, values=themelist, textvariable=self.style_name, width=15, state='readonly')
        theme_combo.pack(side="right", padx=4)
        theme_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_theme())

        # Font Buttons
        ttk.Button(theme_group, text="A-", bootstyle="secondary-outline", command=lambda: self._adjust_font(-1)).pack(side="right", padx=4)
        ttk.Button(theme_group, text="A+", bootstyle="secondary-outline", command=lambda: self._adjust_font(+1)).pack(side="right", padx=4)
        
    def _create_statusbar(self):
        self.status = ttk.Label(self.root, text="Initializing...", anchor="w", bootstyle="secondary")
        self.status.pack(side="bottom", fill="x")
        
    def _create_main_panes(self):
        paned = ttk.Panedwindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True) 

        self.sidebar = ttk.Frame(paned, width=300) 
        paned.add(self.sidebar, weight=0)
        self._build_sidebar(self.sidebar)

        self.main_frame = ttk.Frame(paned)
        paned.add(self.main_frame, weight=1)

        # 主 Tab 区域
        self.notebook = ttk.Notebook(self.main_frame, bootstyle="primary")
        self.notebook.pack(fill="both", expand=True)

        # 日志控制台
        log_frame = ttk.Frame(self.main_frame, padding=(0, 5, 0, 0))
        log_frame.pack(side="bottom", fill="x", pady=(5,0)) 
        
        ttk.Label(log_frame, text="Log / Console Output:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=4)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=7, wrap="word", padx=4, pady=2, font=('Consolas', 10), relief=tk.FLAT)
        self.log_text.pack(fill="x", expand=False)
        self.log_text.configure(state="disabled")

    def _build_sidebar(self, parent):
        
        # --- Explorer ---
        ttk.Label(parent, text="📂 Workspace Explorer", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=8, pady=(8,4))
        explorer_frame = ttk.Frame(parent)
        explorer_frame.pack(fill="both", expand=True, padx=8)

        self.tree = ttk.Treeview(explorer_frame, show="tree", bootstyle="default")
        vsb = ttk.Scrollbar(explorer_frame, orient="vertical", command=self.tree.yview, bootstyle="round")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        self.tree.bind("<Double-1>", self._on_tree_select) 
        self.tree.bind("<Button-3>", self._handle_tree_right_click)
        
        self._refresh_workspace_tree()

        # --- Quick Actions ---
        ttk.Separator(parent).pack(fill="x", pady=8)
        ttk.Label(parent, text="⚡ Quick Actions", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8)
        
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill="x", padx=8, pady=4)
        
        ttk.Button(button_frame, text="Plugins Tab", bootstyle="primary", 
                             command=lambda: self._select_tab_by_name("Plugins")).pack(side="left", expand=True, fill="x", padx=(0, 4))
        
        ttk.Button(button_frame, text="New File", bootstyle="secondary", 
                             command=lambda: self._create_new_item(is_file=True)).pack(side="left", expand=True, fill="x", padx=(4, 0))

    def _create_context_menu(self):
        self.tree_menu = Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="Open (Double Click)", command=self._open_tree_selection)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="New File in Folder", command=lambda: self._create_new_item(is_file=True))
        self.tree_menu.add_command(label="New Folder in Folder", command=lambda: self._create_new_item(is_file=False))
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Delete (Empty Folder/File)", command=self._delete_item, foreground='red')
        
    def _handle_tree_right_click(self, event):
        try:
            item_id = self.tree.identify_row(event.y)
            if item_id:
                self.tree.selection_set(item_id)
                path = self._get_path_from_tree_item(item_id)
                is_root = (path == str(config.APP_DIR))
                self.tree_menu.entryconfig("Delete", state="disabled" if is_root else "normal")
                self.tree_menu.post(event.x_root, event.y_root)
        except Exception as e:
            self.log_to_console(f"[ERROR] 右键菜单错误: {e}")

    def _delete_item(self):
        selected_item = self.tree.focus()
        if not selected_item: return
        
        path = self._get_path_from_tree_item(selected_item)
        if not path or path == str(config.APP_DIR): return # 保护根目录
        
        name = os.path.basename(path)
        p = pathlib.Path(path)
        
        if p.is_dir():
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the folder '{name}'? Note: This tool only deletes EMPTY folders. Cannot be undone."):
                try:
                    os.rmdir(p) 
                    self.log_to_console(f"Folder deleted: {path}")
                except OSError as e:
                    messagebox.showerror("Deletion Error", f"Could not delete '{name}'. Is it empty? Error: {e}")
                    self.log_to_console(f"[ERROR] Deletion failed: {e}")
        elif p.is_file():
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the file '{name}'? This cannot be undone."):
                try:
                    os.remove(p)
                    self.log_to_console(f"File deleted: {path}")
                except Exception as e:
                    messagebox.showerror("Deletion Error", f"Could not delete {name}: {e}")
                    self.log_to_console(f"[ERROR] Deletion failed: {e}")
        
        self._refresh_workspace_tree()

    def _create_new_item(self, is_file=True):
        selected_item = self.tree.focus()
        base_path = config.APP_DIR
        
        # 确定新项目创建的父目录
        if selected_item:
            path_check = self._get_path_from_tree_item(selected_item)
            path_obj = pathlib.Path(path_check)
            if path_obj.is_dir():
                base_path = path_obj
            elif path_obj.is_file():
                 base_path = path_obj.parent
        
        new_name = simpledialog.askstring("New Item", f"Enter name for new {'file' if is_file else 'folder'}:", parent=self.root)
        
        if new_name:
            full_path = base_path / new_name
            try:
                if full_path.exists():
                    messagebox.showerror("Creation Error", f"'{new_name}' already exists.")
                    return
                    
                if is_file:
                    full_path.touch()
                else:
                    full_path.mkdir(exist_ok=True)
                
                self.log_to_console(f"Created new {'file' if is_file else 'folder'}: {full_path}")
                self._refresh_workspace_tree()
                
                # 展开父节点
                if selected_item and full_path.parent == base_path:
                    self.tree.item(selected_item, open=True)
            except Exception as e:
                messagebox.showerror("Creation Error", f"Could not create {new_name}: {e}")

    # ----------------------------
    # File / Tab Logic
    # ----------------------------

    def _get_path_from_tree_item(self, item_id):
        """
        根据 Treeview ID 递归构建绝对路径。
        """
        if not item_id: return None
        
        parts = []
        current_id = item_id
        while current_id:
            text = self.tree.item(current_id, 'text')
            parent_id = self.tree.parent(current_id)

            if not parent_id:
                # 已经是根节点 (APP_DIR 名称)
                break
                
            parts.insert(0, text)
            current_id = parent_id
        
        if not parts and self.tree.item(item_id, 'text') == str(config.APP_DIR.name):
            return str(config.APP_DIR)
        
        if not parts: return None 
        
        full_path = config.APP_DIR
        for part in parts:
             full_path /= part
             
        return str(full_path)

    def _on_tree_select(self, event):
        item_id = self.tree.focus()
        path = self._get_path_from_tree_item(item_id)
        if path and pathlib.Path(path).is_file():
            self.open_file(path)
        elif path and pathlib.Path(path).is_dir():
            is_open = self.tree.item(item_id, 'open')
            self.tree.item(item_id, open=not is_open)

    def _open_tree_selection(self):
        item_id = self.tree.focus()
        path = self._get_path_from_tree_item(item_id)
        if path and pathlib.Path(path).is_file():
            self.open_file(path)

    def _refresh_workspace_tree(self):
        """刷新文件浏览器 Treeview"""
        self.tree.delete(*self.tree.get_children())
        if not hasattr(config, 'APP_DIR'): return
        
        root_path = config.APP_DIR
        root_node = self.tree.insert("", "end", text=str(root_path.name), iid=str(root_path), open=True, tags=('dir',))
        
        def insert_node(parent_id, current_path, depth):
            if depth > 4: return 
            
            try:
                items = sorted(list(current_path.iterdir()))
                
                # 先添加文件夹
                for p in items:
                    if p.name.startswith(('.', '__pycache__')): continue
                    is_dir = p.is_dir()
                    
                    if is_dir:
                        tag = "dir"
                        new_id = self.tree.insert(parent_id, "end", text=p.name, iid=str(p), tags=(tag,))
                        insert_node(new_id, p, depth + 1)
                
                # 后添加文件
                for p in items:
                    if p.name.startswith(('.', '__pycache__')): continue
                    if p.is_file():
                        tag = "file"
                        self.tree.insert(parent_id, "end", text=p.name, iid=str(p), tags=(tag,))
                        
            except Exception as e:
                self.log_to_console(f"无法读取目录 {current_path}: {e}")

        insert_node(root_node, root_path, 1)
        
        self.tree.tag_configure('dir', font=('Segoe UI', 10, 'bold'), foreground="#87CEEB")
        self.tree.tag_configure('file', font=('Segoe UI', 10))

    def create_empty_tab(self, title="Untitled"):
        """
        创建一个新的空文本编辑标签页。
        """
        frame = ttk.Frame(self.notebook)
        txt = scrolledtext.ScrolledText(frame, wrap="none", padx=8, pady=8, font=('Consolas', self.font_size.get()), undo=True)
        txt.pack(fill="both", expand=True)
        self.notebook.add(frame, text=title)
        self.notebook.select(frame)
        
        # 初始状态: (path=None, is_dirty=False)
        self.open_tabs_map[frame] = (None, False) 
        
        # 绑定 KeyRelease，用于语法高亮和脏标记
        txt.highlighter = SyntaxHighlighter(txt)
        def on_key_release(e):
            safe_call(txt.highlighter.highlight)
            self._mark_tab_dirty(frame, True)
            
        txt.bind("<KeyRelease>", on_key_release)
        
        self.log_to_console(f"Created new tab: {title}")
        
    def open_file_dialog(self):
        filetypes = [("All files", "*.*"), ("Text files", "*.txt"), ("Python", "*.py")]
        path = filedialog.askopenfilename(
            title="Open a file", 
            initialdir=str(config.APP_DIR),
            filetypes=filetypes
        )
        if path:
            self.open_file(path)
            
    def _open_selected_recent(self, event):
        """Combobox 选中时自动打开文件"""
        # 获取选中的文件名 (Combobox 只显示文件名)
        selected_file_name = self.file_combo.get()
        # 从 recent_files 中查找对应的完整路径
        path = next((p for p in self.recent_files if os.path.basename(p) == selected_file_name), None)

        if path and os.path.exists(path):
            self.open_file(path)

    def open_file(self, path, line_num=1):
        """
        打开文件到新的标签页，并可跳转到指定行。
        """
        path = str(path)
        if not os.path.exists(path):
            messagebox.showerror("File not found", f"{path} 不存在")
            return
            
        # 检查是否已打开，如果已打开则切换到该Tab
        for frame, (existing_path, _) in self.open_tabs_map.items():
            if existing_path == path:
                self.notebook.select(frame)
                
                text_widget = next((w for w in frame.winfo_children() if isinstance(w, scrolledtext.ScrolledText)), None)
                if text_widget and line_num > 1:
                     text_widget.see(f"{line_num}.0")
                     
                return
        
        # --- 创建新的标签页并加载内容 ---
        
        # 更新最近文件列表
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.appendleft(path)
        
        self.file_combo['values'] = [os.path.basename(p) for p in self.recent_files]
        self.file_combo.set(os.path.basename(path)) 
        self.log_to_console(f"Opening file: {path}")

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            content = f"无法读取为文本: {e}"

        frame = ttk.Frame(self.notebook)
        txt = scrolledtext.ScrolledText(frame, wrap="none", padx=8, pady=8, font=('Consolas', self.font_size.get()), undo=True)
        txt.insert("1.0", content)
        txt.configure(state="normal")
        txt.pack(fill="both", expand=True)
        self.notebook.add(frame, text=os.path.basename(path))
        self.notebook.select(frame)

        self.open_tabs_map[frame] = (path, False) 
        
        txt.highlighter = SyntaxHighlighter(txt)
        
        def on_key_release(e):
            safe_call(txt.highlighter.highlight)
            self._mark_tab_dirty(frame, True)
            
        if path.endswith(".py"):
            txt.bind("<KeyRelease>", on_key_release)
            safe_call(txt.highlighter.highlight) 
        else:
            txt.unbind("<KeyRelease>")
            txt.highlighter._remove_tags() 
            
        if line_num > 1:
             txt.see(f"{line_num}.0")
             
        self.update_status(f"Opened file: {os.path.basename(path)}")
        
    def close_active_tab(self):
        current_tab_id = self.notebook.select()
        if not current_tab_id: return
        
        frame = self.root.nametowidget(current_tab_id)
        tab_title = self.notebook.tab(current_tab_id, "text").lstrip('*')
        
        if self._is_tab_dirty(frame):
            response = messagebox.askyesnocancel(
                "Unsaved Changes", 
                f"文件 '{tab_title}' 尚未保存。是否在关闭前保存？", 
                parent=self.root
            )
            if response is True:
                if not self.save_active_file():
                    return
            elif response is None: 
                return

        if frame in self.open_tabs_map:
            del self.open_tabs_map[frame]
            
        self.notebook.forget(current_tab_id)
        self.update_status(f"Closed tab: {tab_title}")


    def save_active_file(self):
        current_tab_id = self.notebook.select()
        if not current_tab_id: return False
        current_tab_frame = self.root.nametowidget(current_tab_id)

        path, _ = self.open_tabs_map.get(current_tab_frame, (None, False))
        
        text_widget = next((w for w in current_tab_frame.winfo_children() if isinstance(w, scrolledtext.ScrolledText)), None)

        if not text_widget:
            messagebox.showwarning("保存失败", "当前标签页没有可保存的文本内容。")
            return False

        content = text_widget.get("1.0", "end-1c")

        if path is None or not os.path.exists(path) or "Untitled" in self.notebook.tab(current_tab_id, "text"):
            filetypes = [("All files", "*.*"), ("Text files", "*.txt"), ("Python", "*.py")]
            path = filedialog.asksaveasfilename(
                title="Save file as", 
                initialdir=str(config.APP_DIR), 
                filetypes=filetypes, 
                defaultextension=".txt"
            )
            if not path:
                return False

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            
            # 更新状态为已保存
            self.open_tabs_map[current_tab_frame] = (path, False) 
            self.notebook.tab(current_tab_id, text=os.path.basename(path))
                
            self.update_status(f"文件已保存: {os.path.basename(path)}")
            self._refresh_workspace_tree()
            self.log_to_console(f"File saved: {path}")
            return True

        except Exception as e:
            messagebox.showerror("保存错误", f"保存文件时发生错误: {e}")
            self.log_to_console(f"[ERROR] Save Error: {e}")
            return False
            
    # --- 文件内容全局搜索 ---
    def _start_global_search(self):
        search_term = self.search_entry.get().strip()
        if not search_term:
            messagebox.showinfo("Search", "Please enter a search term.")
            return

        self.log_to_console(f"Starting global search for: '{search_term}'")
        self.update_status(f"Searching for '{search_term}'...")
        
        # 在单独的线程中执行搜索以避免 UI 阻塞
        self.root.after(10, lambda: self._execute_search_and_display(search_term))
        
    def _execute_search_and_display(self, search_term):
        results = self._perform_content_search(search_term)
        
        if not results:
            self.update_status(f"Search complete. No matches found for '{search_term}'.")
            messagebox.showinfo("Search Result", f"No file content found matching '{search_term}' in the workspace.")
            return

        self._display_search_results(search_term, results)
        self.update_status(f"Search complete. Found {len(results)} matches.")
        
    def _perform_content_search(self, term):
        results = []
        term_lower = term.lower()
        
        def search_dir(directory):
            try:
                for item in directory.iterdir():
                    if item.name.startswith(('.', '__pycache__')): continue
                    
                    if item.is_dir():
                        search_dir(item)
                    elif item.is_file():
                        # 只搜索常见的文本文件类型
                        if item.suffix.lower() in ['.txt', '.py', '.json', '.log', '.md', '.ini', '.csv']:
                            try:
                                with open(item, 'r', encoding='utf-8', errors='ignore') as f:
                                    for line_num, line in enumerate(f, 1):
                                        if term_lower in line.lower():
                                            results.append({
                                                'path': str(item),
                                                'line': line_num,
                                                'content': line.strip()
                                            })
                                            break # 只记录每文件第一次匹配
                            except Exception as e:
                                self.log_to_console(f"[WARNING] Could not read file {item.name}: {e}")
            except Exception as e:
                self.log_to_console(f"[ERROR] Error traversing directory {directory}: {e}")

        search_dir(config.APP_DIR)
        return results

    def _display_search_results(self, term, results):
        title = f"Search Results for '{term}'"
        
        # 移除已有的搜索结果 Tab
        for tab_id in self.notebook.tabs():
            if self.notebook.tab(tab_id, "text").startswith("Search Results"):
                self.notebook.forget(tab_id)
        
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text=title)
        self.notebook.select(frame)
        self.open_tabs_map[frame] = (None, False)

        ttk.Label(frame, text=f"🔍 {title}", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 10))

        tree = ttk.Treeview(frame, columns=('Line', 'Preview'), show="headings", bootstyle="primary")
        tree.heading('Line', text='Line', anchor=tk.CENTER)
        tree.column('Line', width=50, stretch=tk.NO, anchor=tk.CENTER)
        tree.heading('Preview', text='Content Preview', anchor=tk.W)
        tree.column('Preview', width=500, stretch=tk.YES, anchor=tk.W)
        
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview, bootstyle="round")
        tree.configure(yscrollcommand=vsb.set)
        
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # 插入结果
        file_items = {}
        for result in results:
            path = result['path']
            
            if path not in file_items:
                file_items[path] = tree.insert('', 'end', iid=path, text=os.path.basename(path), tags=('file_path',))
            
            tree.insert(file_items[path], 'end', values=(result['line'], result['content']), tags=('match',))
        
        tree.tag_configure('file_path', font=('Segoe UI', 10, 'bold'), foreground='#90EE90')
        tree.tag_configure('match', font=('Consolas', 9))

        def on_result_double_click(event):
            selected_item = tree.focus()
            if not selected_item: return
            
            parent_id = tree.parent(selected_item)
            if not parent_id: return 
            
            path = parent_id # 父 ID 就是路径
            line_num = tree.item(selected_item, 'values')[0]
            
            self.open_file(path, line_num=int(line_num))
            
        tree.bind('<Double-1>', on_result_double_click)


    # ----------------------------
    # Plugin Logic
    # ----------------------------

    def _create_welcome_tab(self):
        frame = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(frame, text="Welcome")
        
        ttk.Label(frame, text="Universal Toolbox", font=("Segoe UI", 24, "bold"), bootstyle="primary").pack(pady=10)
        ttk.Label(frame, text="A Modular Workspace for Python Tools and Files", font=("Segoe UI", 14)).pack(pady=5)
        
        ttk.Separator(frame).pack(fill='x', pady=20)
        
        info_text = (
            "1. File Explorer on the left allows navigation and creation/deletion of files in the current directory.\n"
            "2. Use 'New Tab', 'Open File', and 'Save Active' buttons, or the respective keyboard shortcuts (Ctrl+N, Ctrl+O, Ctrl+S).\n"
            "3. Go to the 'Plugins' tab to discover and launch modular tools.\n"
            "4. Use the 'Search Content' bar to find text across all text files in the workspace.\n"
            "5. Plugins must define a 'PLUGIN_META' dictionary and a 'register(app_instance, parent_frame)' function.\n"
            "6. Console output is redirected to the log pane at the bottom."
        )
        ttk.Label(frame, text=info_text, justify="left", bootstyle="info").pack(anchor="w")

        self.open_tabs_map[frame] = (None, False)

    def _load_plugins(self):
        """重新加载所有插件，支持热重载。"""
        self.log_to_console("--- Starting Plugin Reload ---")
        
        self.plugin_modules = {} 

        plugins = safe_call(config.discover_plugins) or []
        
        for name, module, meta in plugins:
            self.plugin_modules[meta['name']] = module
            
        self.log_to_console(f"发现并缓存插件: {', '.join(self.plugin_modules.keys()) if self.plugin_modules else '无'}")
        
        self._create_plugins_tab(plugins)
        
    def _select_tab_by_name(self, name):
        for tab_id in self.notebook.tabs():
            tab_text = self.notebook.tab(tab_id, "text").lstrip('*')
            if name in tab_text:
                self.notebook.select(tab_id)
                return

    def _create_plugins_tab(self, plugins):
        """
        创建或更新 'Plugins' 标签页，包含优化的 Treeview 列表。
        """
        tab_name = "Plugins"
        
        plugin_tab_frame = None
        for tab_id in self.notebook.tabs():
            if self.notebook.tab(tab_id, "text") == tab_name:
                plugin_tab_frame = self.root.nametowidget(tab_id)
                for widget in plugin_tab_frame.winfo_children():
                    widget.destroy()
                break

        if plugin_tab_frame is None:
            plugin_tab_frame = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(plugin_tab_frame, text=tab_name)
            self.open_tabs_map[plugin_tab_frame] = (None, False)
        
        # 2. UI 构建
        
        ttk.Label(plugin_tab_frame, text="⚙️ Available Plugins", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 5))
        
        list_container = ttk.Frame(plugin_tab_frame)
        list_container.pack(fill="x", pady=5)
        
        self.plugin_list_tree = ttk.Treeview(
            list_container, 
            columns=('Name', 'Version', 'Author'), 
            show="headings", 
            selectmode='browse',
            height=10,
            bootstyle="primary" 
        )
                                             
        self.plugin_list_tree.heading('Name', text='Plugin Name', anchor=tk.CENTER)
        self.plugin_list_tree.column('Name', width=250, stretch=tk.YES, anchor=tk.W) 
        
        self.plugin_list_tree.heading('Version', text='Ver', anchor=tk.CENTER)
        self.plugin_list_tree.column('Version', width=60, stretch=tk.NO, anchor=tk.CENTER) 
        
        self.plugin_list_tree.heading('Author', text='Author', anchor=tk.CENTER)
        self.plugin_list_tree.column('Author', width=100, stretch=tk.NO, anchor=tk.CENTER) 
        
        vsb = ttk.Scrollbar(list_container, orient="vertical", command=self.plugin_list_tree.yview, bootstyle="round")
        self.plugin_list_tree.configure(yscrollcommand=vsb.set)
        
        self.plugin_list_tree.pack(side="left", fill="x", expand=True)
        vsb.pack(side="right", fill="y")
        
        self.plugin_list_tree.bind('<<TreeviewSelect>>', self._on_plugin_select_list)
        
        # 3. 填充数据
        for name, module, meta in plugins:
            plugin_name = meta.get('name', name)
            plugin_version = meta.get('version', 'N/A')
            plugin_author = meta.get('author', 'N/A')
            
            tag_list = []
            if 'ai assistant' in plugin_author.lower(): 
                 tag_list.append('ai_author')
            
            self.plugin_list_tree.insert('', 'end', 
                                         iid=plugin_name, 
                                         values=(plugin_name, plugin_version, plugin_author),
                                         tags=tuple(tag_list))

        # --- Treeview 样式 ---
        self.plugin_list_tree.tag_configure('ai_author', background='#005691', foreground='white')
        
        # 4. 详情面板
        ttk.Separator(plugin_tab_frame).pack(fill='x', pady=10)
        
        run_frame = ttk.Frame(plugin_tab_frame)
        run_frame.pack(fill="x", pady=(0, 10))
        
        self.plugin_run_btn = ttk.Button(run_frame, text="▶ Run/Launch Plugin", bootstyle="success", state=tk.DISABLED, command=self._run_selected_plugin)
        self.plugin_run_btn.pack(side="left", padx=(0, 10))
        
        self.plugin_select_info = ttk.Label(run_frame, text="Select a plugin to see details and run.", bootstyle="info")
        self.plugin_select_info.pack(side="left")
        
        detail_frame = ttk.Frame(plugin_tab_frame, padding=10, relief=tk.RIDGE, bootstyle="secondary")
        detail_frame.pack(fill="both", expand=True)
        
        self.detail_name = ttk.Label(detail_frame, text="Name: N/A", font=("Segoe UI", 10, "bold"))
        self.detail_version = ttk.Label(detail_frame, text="Version: N/A")
        self.detail_author = ttk.Label(detail_frame, text="Author: N/A")
        
        self.detail_name.pack(anchor="w")
        self.detail_version.pack(anchor="w")
        self.detail_author.pack(anchor="w")
        
        ttk.Label(detail_frame, text="Description:", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(5, 2))
        self.detail_desc = scrolledtext.ScrolledText(detail_frame, height=4, wrap=tk.WORD, state=tk.DISABLED, font=('Consolas', 10), relief=tk.FLAT)
        self.detail_desc.pack(fill="x")
        
        if self.plugin_list_tree.get_children():
             self.plugin_list_tree.selection_set(self.plugin_list_tree.get_children()[0])

    def _on_plugin_select_list(self, event):
        """
        当用户在插件列表中选择一个项目时触发，更新详情面板。
        """
        selected_id = self.plugin_list_tree.focus()
        if not selected_id:
            # 清空详情
            self.plugin_run_btn.config(state=tk.DISABLED)
            self.plugin_select_info.config(text="Select a plugin to see details and run.")
            
            self.detail_name.config(text="Name: N/A")
            self.detail_version.config(text="Version: N/A")
            self.detail_author.config(text="Author: N/A")
            self.detail_desc.config(state=tk.NORMAL)
            self.detail_desc.delete("1.0", tk.END)
            self.detail_desc.config(state=tk.DISABLED)
            return

        module = self.plugin_modules.get(selected_id) 
        
        if module:
            meta = getattr(module, 'PLUGIN_META', {'name': selected_id, 'version': 'N/A', 'author': 'N/A'})
        else:
            meta = {'name': selected_id, 'version': 'N/A', 'author': 'N/A', 'description': 'Module not found in cache. Reload plugins.'}

        name = meta.get('name', selected_id)
        version = meta.get('version', 'N/A')
        author = meta.get('author', 'N/A')
        description = meta.get('description', 'No description provided.')

        self.plugin_run_btn.config(state=tk.NORMAL if module else tk.DISABLED)
        self.plugin_select_info.config(text=f"Ready to launch: {name}")

        self.detail_name.config(text=f"Name: {name}")
        self.detail_version.config(text=f"Version: {version}")
        self.detail_author.config(text=f"Author: {author}")
        
        self.detail_desc.config(state=tk.NORMAL)
        self.detail_desc.delete("1.0", tk.END)
        self.detail_desc.insert("1.0", description)
        self.detail_desc.config(state=tk.DISABLED)


    def _run_selected_plugin(self):
        """
        执行选定插件的 register 函数。
        """
        selected_id = self.plugin_list_tree.focus()
        if not selected_id: return
        
        module = self.plugin_modules.get(selected_id) 

        if not module:
            self.log_to_console(f"[ERROR] Plugin module not found for: {selected_id}", tag='error')
            messagebox.showerror("Run Error", f"Plugin module '{selected_id}' not found in cache.")
            return

        register_func = getattr(module, 'register', None)
        plugin_name = module.PLUGIN_META.get('name', selected_id)
        
        if register_func and callable(register_func):
            plugin_frame = ttk.Frame(self.notebook, padding=5)
            self.notebook.add(plugin_frame, text=f"Tool: {plugin_name}")
            self.notebook.select(plugin_frame)
            self.open_tabs_map[plugin_frame] = (None, False)
            
            self.log_to_console(f"Launching plugin: {plugin_name}...")
            
            success = safe_call(register_func, self, plugin_frame)
            
            if success is not True:
                self.log_to_console(f"[WARNING] Plugin '{plugin_name}' register function failed or returned False.", tag='warning')
                messagebox.showwarning("Plugin Error", f"'{plugin_name}' failed to initialize. See console for details.")
                self.notebook.forget(plugin_frame)
                if plugin_frame in self.open_tabs_map:
                    del self.open_tabs_map[plugin_frame]
            else:
                self.log_to_console(f"Plugin '{plugin_name}' launched successfully.", tag='info')

        else:
            self.log_to_console(f"[ERROR] Plugin '{plugin_name}' does not have a valid 'register' function.", tag='error')
            messagebox.showerror("Run Error", f"Plugin '{plugin_name}' is missing the required 'register' function.")

# ----------------------------
# Application Entry Point
# ----------------------------

if __name__ == '__main__':
    root = tb.Window(themename="superhero") 
    app = ToolboxApp(root)
    root.mainloop()
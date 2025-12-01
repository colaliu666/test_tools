import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, Menu, simpledialog
import tkinter.font as tkFont
from collections import deque
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import pathlib 
import sys 
from typing import Optional, Any
# 导入用于处理模块重载的库
import importlib
import inspect

# --- 导入配置和安全函数 ---
try:
    # 核心修正 1: 使用相对导入引用同一目录下的 config.py
    from . import config
    log = config.log
    safe_call = config.safe_call
except ImportError:
    # Fallback for standalone execution (如果 config.py 缺失或在模块外部)
    def log(*args): print(f"[LOG] {' '.join(str(a) for a in args)}")
    def safe_call(func, *args, **kwargs): return func(*args, **kwargs)
    
    # 临时定义 config.APP_DIR，以防 main_app 运行时找不到 config 模块
    class ConfigPlaceholder:
        APP_DIR = pathlib.Path(os.getcwd())
        def discover_plugins(self): 
            log("Warning: Cannot discover plugins without config.py.")
            return []
    try:
        import config # 假设 config.py 在同一目录下
    except ImportError:
        config = ConfigPlaceholder()
        log("Warning: config.py not found. Using current directory as APP_DIR.")


# --- 辅助类：语法高亮（优化后，只包含高亮方法） ---
class SyntaxHighlighter:
    """提供简单的 Python/文本语法高亮。"""
    
    PYTHON_KEYWORDS = [
        'for', 'in', 'if', 'else', 'elif', 'def', 'class', 'return', 'import', 
        'from', 'while', 'try', 'except', 'finally', 'with', 'as', 'lambda', 
        'yield', 'is', 'not', 'and', 'or', 'pass', 'break', 'continue', 'global', 
        'nonlocal', 'del', 'await', 'async'
    ]
    # 关键字字体应为粗体
    KEYWORD_FONT = ("Consolas", 10, "bold") 

    def __init__(self, text_widget):
        self.text = text_widget
        # 标签配置可以更精细地控制字体大小，但为了配合全局调整，我们只设置颜色
        self.text.tag_configure("keyword", foreground="#DAA520", font=self.KEYWORD_FONT) 
        self.text.tag_configure("comment", foreground="#6A9955") 
        self.text.tag_configure("string", foreground="#CE9178") 
        self.text.tag_configure("function", foreground="#569CD6")
        
    def highlight(self):
        """执行语法高亮。"""
        # 性能提示：在大文件上，此操作仍是同步且昂贵的。
        # 实际应用中应只高亮可见区域或在空闲时执行。
        
        self._remove_tags()
        
        # 1. 关键字高亮
        for word in self.PYTHON_KEYWORDS:
            self._apply_tag("keyword", r'\y' + word + r'\y')
            
        # 2. 字符串高亮
        self._apply_tag("string", r'"[^"\n]*"') 
        
        # 3. 注释高亮
        self._apply_tag("comment", r'#.*$')

    def _remove_tags(self):
        """移除所有已应用的高亮标签。"""
        for tag in ["keyword", "comment", "string", "function"]:
            self.text.tag_remove(tag, "1.0", "end")

    def _apply_tag(self, tag, pattern):
        """应用指定的标签到匹配的模式上。"""
        start = "1.0"
        while True:
            match_len = tk.IntVar()
            
            pos = self.text.search(
                pattern, 
                start, 
                stopindex="end", 
                regexp=True,
                count=match_len 
            )
            
            if not pos:
                break
            
            length = match_len.get()
            if length == 0:
                # 防止无限循环
                start = self.text.index(f"{start}+1c")
                if self.text.compare(start, ">=", "end"): break
                continue

            end = f"{pos}+{length}c"
            
            self.text.tag_add(tag, pos, end)
            start = end

# --- 日志重定向类 (修正版：添加了定时刷新) ---
class ConsoleRedirector:
    """重定向 stdout/stderr 到 ScrolledText widget，使用定时器确保刷新。"""
    def __init__(self, text_widget, app_instance):
        self.text_widget = text_widget
        self.app = app_instance
        self.buffer = ""
        self._schedule_flush() # 启动定时刷新

    def write(self, s):
        self.buffer += s
        # 不立即刷新，依赖定时器

    def _schedule_flush(self):
        """定时检查并刷新 buffer。"""
        if self.buffer:
            self.flush()
        # 每 100 毫秒刷新一次
        if hasattr(self.app, 'root'):
            self.app.root.after(100, self._schedule_flush) 

    def flush(self):
        if not self.buffer: 
            return
        
        output_to_write = self.buffer
        self.buffer = "" # 清空缓冲区
        
        if not output_to_write.strip(): return
        
        self.text_widget.configure(state="normal")
        self.text_widget.insert(tk.END, output_to_write, 'log')
        self.text_widget.see(tk.END)
        self.text_widget.configure(state="disabled")

# --- 主应用类 ---

class ToolboxApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Universal Toolbox (Modular)")
        self.root.geometry("1150x720")
        self.recent_files = deque(maxlen=20)
        # Key: Frame Widget (Tab ID's widget), Value: File Path (str) or None
        self.open_tabs_map = {} 
        
        self.style_name = tk.StringVar(value="superhero") 
        self.font_size = tk.IntVar(value=11) 
        self.style = tb.Style(self.style_name.get()) 
        
        self._create_topbar()
        self._create_statusbar() 
        self._create_main_panes()
        self._create_context_menu()
        self._bind_global_events()

        # 重定向 config.log 函数到 ScrolledText
        self.redirect_log()
        
        self.apply_theme()
        self._load_plugins()
        self._create_welcome_tab()
        
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    # ----------------------------
    # Core Utility Methods
    # ----------------------------

    def log_to_console(self, *args):
        """提供给外部模块（如插件）调用的日志接口。"""
        message = " ".join(str(a) for a in args) + "\n"
        if hasattr(self, 'log_text'):
            self.log_text.configure(state="normal")
            # 使用 'log' 标签，如果需要区分 error/info，需要更复杂的逻辑
            self.log_text.insert(tk.END, message, 'log') 
            self.log_text.see(tk.END)
            self.log_text.configure(state="disabled")

    def redirect_log(self):
        """将 config.log 和 stdout/stderr 重定向到 ScrolledText。"""
        # 覆盖 config.log
        if 'config' in sys.modules and hasattr(config, 'log'):
             config.log = self.log_to_console
        
        # 重定向 stdout 和 stderr
        # 检查是否已经被重定向
        if not isinstance(sys.stdout, ConsoleRedirector):
            sys.stdout = ConsoleRedirector(self.log_text, self)
        if not isinstance(sys.stderr, ConsoleRedirector):
            sys.stderr = ConsoleRedirector(self.log_text, self)
        
        self.log_text.tag_configure('log', foreground="#ffffff")
        self.log_text.tag_configure('error', foreground="#dc3545", font=('Consolas', 10, 'bold'))
        self.log_text.tag_configure('info', foreground="#0dcaf0")
        
    def update_status(self, text):
        """统一方法更新状态栏。"""
        if hasattr(self, 'status'):
            self.status.config(text=text)

    def apply_theme(self):
        theme = self.style_name.get()
        try:
            self.style.theme_use(theme)
            self.update_status(f"Theme: {theme}")
        except Exception as e:
            log(f"主题应用失败: {e}")
        self._apply_font_size()

    def _apply_font_size(self):
        fs = max(8, min(20, self.font_size.get()))
        try:
            default_font_obj = tkFont.nametofont('TkDefaultFont')
            default_font_family = default_font_obj.cget("family")
        except:
            default_font_family = "Segoe UI" 
        
        default_font = (default_font_family, fs)
        # 仅针对 ttkbootstrap 控件设置默认字体，不建议全局覆盖 *Font
        # self.root.option_add("*Font", default_font) 
        
        try:
            tkFont.nametofont("TkDefaultFont").configure(size=fs)
            tkFont.nametofont("TkTextFont").configure(size=fs)
            
            # 重新配置所有文本编辑器字体
            for tab_id in self.notebook.tabs():
                frame = self.notebook.tab(tab_id, "widget")
                text_widget = next((w for w in frame.winfo_children() if isinstance(w, scrolledtext.ScrolledText)), None)
                if text_widget:
                    # 使用 Consolas 或其他等宽字体
                    text_widget.configure(font=('Consolas', fs))
        except Exception:
            pass 
        
        log(f"字体大小设置为 {fs}px")
        self.update_status(f"Theme: {self.style_name.get()} | Font: {fs}px") 

    def _adjust_font(self, delta):
        self.font_size.set(self.font_size.get() + delta)
        self._apply_font_size()


    # ----------------------------
    # UI Layout Methods 
    # ----------------------------
    
    def _create_topbar(self):
        top = ttk.Frame(self.root)
        top.pack(side="top", fill="x")

        # 文件操作组
        file_group = ttk.Frame(top)
        file_group.pack(side="left", padx=4, pady=6)
        
        ttk.Button(file_group, text="New Tab", bootstyle="secondary-outline",
                             command=self.create_empty_tab).pack(side="left", padx=4)
        ttk.Button(file_group, text="Open File...", bootstyle="info-outline",
                             command=self.open_file_dialog).pack(side="left", padx=4)
        ttk.Button(file_group, text="Save Active", bootstyle="success", 
                             command=self.save_active_file).pack(side="left", padx=4)
        ttk.Button(file_group, text="Close Tab", bootstyle="danger-outline",
                             command=self.close_active_tab).pack(side="left", padx=4)


        # 插件/系统组
        system_group = ttk.Frame(top)
        system_group.pack(side="left", padx=(20, 4), pady=6)
        
        ttk.Button(system_group, text="Reload Plugins", bootstyle="warning-outline",
                             command=self._load_plugins).pack(side="left", padx=4)
        
        ttk.Button(system_group, text="Refresh Explorer", bootstyle="secondary-outline",
                             command=self._refresh_workspace_tree).pack(side="left", padx=4)

        # 最近文件组
        recent_group = ttk.Frame(top)
        recent_group.pack(side="left", padx=(20, 4), pady=6)

        ttk.Label(recent_group, text="Recent:").pack(side="left", padx=(4,2))
        self.file_combo = ttk.Combobox(recent_group, values=list(self.recent_files), width=40)
        self.file_combo.pack(side="left", padx=4)
        ttk.Button(recent_group, text="Open", command=self._open_selected_recent).pack(side="left", padx=4)

        # 主题/字体组 (靠右)
        theme_group = ttk.Frame(top)
        theme_group.pack(side="right", padx=4, pady=6)

        ttk.Button(theme_group, text="A-", command=lambda: self._adjust_font(-1)).pack(side="right", padx=4)
        ttk.Button(theme_group, text="A+", command=lambda: self._adjust_font(+1)).pack(side="right", padx=4)
        
        ttk.Label(theme_group, text="Theme:").pack(side="right", padx=(4,2))
        themelist = sorted(self.style.theme_names()) 
        theme_combo = ttk.Combobox(theme_group, values=themelist, textvariable=self.style_name, width=16)
        theme_combo.pack(side="right", padx=4)
        theme_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_theme())
        
    def _create_statusbar(self):
        self.status = ttk.Label(self.root, text="Initializing...", anchor="w")
        self.status.pack(side="bottom", fill="x")
        
    def _create_main_panes(self):
        paned = ttk.Panedwindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True) 

        self.sidebar = ttk.Frame(paned, width=260)
        paned.add(self.sidebar, weight=0)
        self._build_sidebar(self.sidebar)

        self.main_frame = ttk.Frame(paned)
        paned.add(self.main_frame, weight=1)

        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True)

        # Log Console
        log_paned = ttk.Panedwindow(self.main_frame, orient="vertical", height=140)
        log_paned.pack(side="bottom", fill="x")
        
        log_frame = ttk.Frame(log_paned)
        log_paned.add(log_frame, weight=1)
        
        ttk.Label(log_frame, text="Log / Console:").pack(anchor="w", padx=4)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=7, wrap="word", padx=4, pady=2, font=('Consolas', 10))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

    def _build_sidebar(self, parent):
        ttk.Label(parent, text="Explorer", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8, pady=(8,4))
        explorer_frame = ttk.Frame(parent)
        explorer_frame.pack(fill="both", expand=True, padx=8)

        self.tree = ttk.Treeview(explorer_frame, show="tree")
        vsb = ttk.Scrollbar(explorer_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Button-3>", self._handle_tree_right_click)
        
        self._refresh_workspace_tree()

        ttk.Separator(parent).pack(fill="x", pady=8)
        ttk.Label(parent, text="Quick Actions", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8)
        
        ttk.Button(parent, text="Go to Plugins Tab", bootstyle="primary", 
                             command=lambda: self._select_tab_by_name("Plugins")).pack(fill="x", padx=8, pady=4)
        
    def _create_context_menu(self):
        self.tree_menu = Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="Open", command=self._open_tree_selection)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="New File", command=lambda: self._create_new_item(is_file=True))
        self.tree_menu.add_command(label="New Folder", command=lambda: self._create_new_item(is_file=False))
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Delete", command=self._delete_item, foreground='red')
        
    def _handle_tree_right_click(self, event):
        try:
            self.tree.selection_set(self.tree.identify_row(event.y))
            selected_item = self.tree.focus()
            if selected_item:
                is_root = (self.tree.parent(selected_item) == '')
                self.tree_menu.entryconfig("Delete", state="disabled" if is_root else "normal")
                self.tree_menu.post(event.x_root, event.y_root)
        except Exception as e:
            log(f"右键菜单错误: {e}")

    def _delete_item(self):
        selected_item = self.tree.focus()
        if not selected_item: return
        
        path = self._get_path_from_tree_item(selected_item)
        if not path: return
        
        name = os.path.basename(path)
        
        p = pathlib.Path(path)
        
        # 修正：删除操作的警告提示
        if p.is_dir():
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the folder '{name}'? Note: This only deletes empty folders using this tool. Cannot be undone."):
                try:
                    os.rmdir(p) # 仅删除空目录
                    log(f"Folder deleted: {path}")
                except OSError as e:
                    messagebox.showerror("Deletion Error", f"Could not delete '{name}'. Is it empty? Error: {e}")
                    log(f"Deletion failed: {e}")
        elif p.is_file():
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the file '{name}'? This cannot be undone."):
                try:
                    os.remove(p)
                    log(f"File deleted: {path}")
                except Exception as e:
                    messagebox.showerror("Deletion Error", f"Could not delete {name}: {e}")
                    log(f"Deletion failed: {e}")
        
        self._refresh_workspace_tree()

    def _create_new_item(self, is_file=True):
        selected_item = self.tree.focus()
        base_path = config.APP_DIR
        
        if selected_item:
            path_check = self._get_path_from_tree_item(selected_item)
            # 如果选中的是目录，则在新目录下创建
            if pathlib.Path(path_check).is_dir():
                base_path = pathlib.Path(path_check)
        
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
                
                log(f"Created new {'file' if is_file else 'folder'}: {full_path}")
                self._refresh_workspace_tree()
                
                # 尝试展开父节点
                if selected_item and full_path.parent == base_path:
                    self.tree.item(selected_item, open=True)
            except Exception as e:
                messagebox.showerror("Creation Error", f"Could not create {new_name}: {e}")

    # ----------------------------
    # File / Tab Logic
    # ----------------------------

    def _get_path_from_tree_item(self, item_id):
        parts = []
        while item_id:
            text = self.tree.item(item_id, 'text')
            # 根节点检查
            if text == str(config.APP_DIR.name) and self.tree.parent(item_id) == '':
                break
            parts.insert(0, text)
            item_id = self.tree.parent(item_id)
        
        # 如果是根节点本身
        if not parts and self.tree.item(self.tree.focus(), 'text') == str(config.APP_DIR.name):
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

    def _open_tree_selection(self):
        item_id = self.tree.focus()
        path = self._get_path_from_tree_item(item_id)
        if path and pathlib.Path(path).is_file():
            self.open_file(path)
        elif path and pathlib.Path(path).is_dir():
            # 切换目录展开状态
            is_open = self.tree.item(item_id, 'open')
            self.tree.item(item_id, open=not is_open)

    def _refresh_workspace_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not hasattr(config, 'APP_DIR'): return
        
        root_path = config.APP_DIR
        root_node = self.tree.insert("", "end", text=str(root_path.name), open=True, tags=('dir',))
        
        def insert_node(parent_id, current_path, depth):
            if depth > 3: return # 限制深度，防止太慢
            
            try:
                # 优先显示目录，然后文件
                items = sorted(list(current_path.iterdir()))
                
                for p in items:
                    if p.name.startswith(('.', '__pycache__')): continue
                    
                    is_dir = p.is_dir()
                    
                    # 仅在非根目录下的文件才在此处插入，以保证顺序
                    if is_dir:
                        tag = "dir"
                        new_id = self.tree.insert(parent_id, "end", text=p.name, tags=(tag,))
                        # 递归调用
                        insert_node(new_id, p, depth + 1)
                
                for p in items:
                    if p.name.startswith(('.', '__pycache__')): continue
                    if p.is_file():
                         tag = "file"
                         self.tree.insert(parent_id, "end", text=p.name, tags=(tag,))
                         
            except Exception as e:
                log(f"无法读取目录 {current_path}: {e}")

        insert_node(root_node, root_path, 1)
        
        self.tree.tag_configure('dir', font=('Segoe UI', 10, 'bold'))
        self.tree.tag_configure('file', font=('Segoe UI', 10))

    def create_empty_tab(self, title="Untitled"):
        frame = ttk.Frame(self.notebook)
        # 确保文本编辑器使用正确的字体大小
        txt = scrolledtext.ScrolledText(frame, wrap="none", padx=8, pady=8, font=('Consolas', self.font_size.get()))
        txt.pack(fill="both", expand=True)
        self.notebook.add(frame, text=title)
        self.notebook.select(frame)
        
        self.open_tabs_map[frame] = None # 表示未保存/未命名文件
        
        txt.highlighter = SyntaxHighlighter(txt)
        
        # 修正：对于空标签页，绑定 KeyRelease 事件以在键入时进行高亮
        txt.bind("<KeyRelease>", lambda e: txt.highlighter.highlight())
        
        log(f"创建新标签: {title}")
        
    def open_file_dialog(self):
        """弹出文件选择对话框，然后调用 open_file。"""
        filetypes = [("All files", "*.*"), ("Text files", "*.txt"), ("Python", "*.py")]
        path = filedialog.askopenfilename(
            title="Open a file", 
            initialdir=str(config.APP_DIR),
            filetypes=filetypes
        )
        if path:
            self.open_file(path)
            
    def _open_selected_recent(self):
        path = self.file_combo.get()
        if path and os.path.exists(path):
            self.open_file(path)

    def open_file(self, path):
        path = str(path)
        if not os.path.exists(path):
            messagebox.showerror("File not found", f"{path} 不存在")
            return
            
        # 检查文件是否已打开
        for frame, existing_path in self.open_tabs_map.items():
            if existing_path == path:
                for tab_id in self.notebook.tabs():
                    if self.notebook.tab(tab_id, "widget") == frame:
                        self.notebook.select(tab_id)
                        return
        
        # Update recent files
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.appendleft(path)
        self.file_combo['values'] = list(self.recent_files)
        self.file_combo.set(os.path.basename(path)) 
        log(f"打开文件: {path}")

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            content = f"无法读取为文本: {e}"

        frame = ttk.Frame(self.notebook)
        # 确保文本编辑器使用正确的字体大小
        txt = scrolledtext.ScrolledText(frame, wrap="none", padx=8, pady=8, font=('Consolas', self.font_size.get()))
        txt.insert("1.0", content)
        txt.configure(state="normal")
        txt.pack(fill="both", expand=True)
        self.notebook.add(frame, text=os.path.basename(path))
        self.notebook.select(frame)

        self.open_tabs_map[frame] = path
        
        txt.highlighter = SyntaxHighlighter(txt)
        
        # 优化：仅对 Python 文件绑定 KeyRelease 事件并执行高亮
        if path.endswith(".py"):
            txt.bind("<KeyRelease>", lambda e: txt.highlighter.highlight())
            txt.highlighter.highlight() 
        else:
            txt.unbind("<KeyRelease>")
            
        self.update_status(f"Opened file: {os.path.basename(path)}")
        
    def close_active_tab(self):
        current_tab_id = self.notebook.select()
        if not current_tab_id: return
        
        frame = self.notebook.tab(current_tab_id, "widget")
        tab_title = self.notebook.tab(current_tab_id, "text")

        # 简单的内容修改检查（可以更精细地实现脏位标记）
        is_modified = False
        text_widget = next((w for w in frame.winfo_children() if isinstance(w, scrolledtext.ScrolledText)), None)
        if text_widget:
            # 这是一个非常简化的检查，需要一个"脏位"机制才能准确判断是否修改
            # 目前暂不实现脏位，避免弹出多次提示
            pass

        if frame in self.open_tabs_map:
            del self.open_tabs_map[frame]
            
        self.notebook.forget(current_tab_id)
        self.update_status(f"Closed tab: {tab_title}")


    def save_active_file(self):
        current_tab_id = self.notebook.select()
        current_tab_frame = self.notebook.tab(current_tab_id, "widget")
        if not current_tab_frame: return

        path = self.open_tabs_map.get(current_tab_frame)
        
        text_widget = next((w for w in current_tab_frame.winfo_children() if isinstance(w, scrolledtext.ScrolledText)), None)

        if not text_widget:
            messagebox.showwarning("保存失败", "当前标签页没有可保存的文本内容。")
            return

        content = text_widget.get("1.0", "end-1c")

        if not path or self.notebook.tab(current_tab_id, "text") == "Untitled":
            filetypes = [("All files", "*.*"), ("Text files", "*.txt"), ("Python", "*.py")]
            path = filedialog.asksaveasfilename(
                title="Save file as", 
                initialdir=str(config.APP_DIR), 
                filetypes=filetypes, 
                defaultextension=".txt"
            )
            if not path:
                return 

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            
            if current_tab_id in self.notebook.tabs():
                self.open_tabs_map[current_tab_frame] = path
                self.notebook.tab(current_tab_id, text=os.path.basename(path))
                
            self.update_status(f"文件已保存: {os.path.basename(path)}")
            self._refresh_workspace_tree()
            log(f"文件已保存: {path}")

        except Exception as e:
            messagebox.showerror("保存错误", f"保存文件时发生错误: {e}")
            log(f"保存错误: {e}")

    # ----------------------------
    # Plugin Logic
    # ----------------------------

    def _on_tab_changed(self, event):
        """标签页切换时更新状态栏和高亮。"""
        current_tab = self.notebook.select()
        tab_name = self.notebook.tab(current_tab, "text")
        self.update_status(f"Active Tab: {tab_name}")
        
        try:
            current_tab_frame = self.notebook.tab(current_tab, "widget")
            text_widget = next((w for w in current_tab_frame.winfo_children() if isinstance(w, scrolledtext.ScrolledText)), None)
            
            if text_widget and hasattr(text_widget, 'highlighter'):
                 file_path = self.open_tabs_map.get(current_tab_frame, "")
                 
                 # 仅在切换到 Python 文件时或未命名标签页时处理高亮绑定
                 if file_path.endswith(".py") or file_path is None:
                    # 重新高亮当前内容
                    text_widget.highlighter.highlight()
                    # 确保 KeyRelease 绑定在切换时重新生效 
                    text_widget.bind("<KeyRelease>", lambda e: text_widget.highlighter.highlight())
                 else:
                    # 对于其他文件/插件标签，移除高亮和 KeyRelease 绑定以保持性能
                    text_widget.unbind("<KeyRelease>")
                    text_widget.highlighter._remove_tags()
        except:
            pass 


    def _load_plugins(self):
        """重新加载插件并刷新 Plugins 标签页。"""
        if hasattr(config, 'discover_plugins'):
            # 注意：为了实现插件代码的实时更新，config.discover_plugins() 
            # 必须在内部使用 importlib.reload() 来强制重新加载模块。
            plugins = config.discover_plugins()
            
            log(f"发现插件: {', '.join(k for k, _, _ in plugins) if plugins else '无'}")
            self._create_plugins_tab(plugins)
        else:
            log("Error: Plugin discovery feature is not available.")


    def _select_tab_by_name(self, name):
        """通过名称选择标签页。"""
        for tab_id in self.notebook.tabs():
            if name in self.notebook.tab(tab_id, "text"):
                self.notebook.select(tab_id)
                return

    def _create_plugins_tab(self, plugins):
        # 移除旧的 Plugins 标签页
        for tab_id in self.notebook.tabs():
            if "Plugins" in self.notebook.tab(tab_id, option="text"):
                self.notebook.forget(tab_id)

        frame = ttk.Frame(self.notebook)
        outer = ttk.Frame(frame)
        outer.pack(fill="both", expand=True, padx=8, pady=8)

        paned = ttk.Panedwindow(outer, orient=HORIZONTAL)
        paned.pack(fill="both", expand=True)

        # --- 左侧：插件列表及描述 ---
        list_frame = ttk.Frame(paned, width=300)
        paned.add(list_frame, weight=0)

        ttk.Label(list_frame, text="Available Plugins", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 6))
        
        list_tree = ttk.Treeview(list_frame, columns=("Version", "Description"), show="headings", selectmode="browse", height=10)
        list_tree.heading("Version", text="Ver.", anchor=W)
        list_tree.heading("Description", text="Description", anchor=W)
        list_tree.column("Version", width=50, stretch=NO)
        list_tree.column("Description", stretch=YES)

        plugin_map = {} 
        for name, module, meta in plugins:
            version = meta.get('version', 'N/A')
            description = meta.get('description', 'No description provided.')
            item_id = list_tree.insert("", "end", text=name, values=(version, description))
            plugin_map[item_id] = module 

        vsb = ttk.Scrollbar(list_tree, orient="vertical", command=list_tree.yview)
        list_tree.configure(yscrollcommand=vsb.set)
        list_tree.pack(fill="both", expand=True)
        vsb.place(relx=1.0, rely=0, relheight=1.0, anchor=NE)
        
        def load_plugin_command(event=None):
            selection = list_tree.selection()
            if not selection:
                messagebox.showinfo("Please Select", "Please select a plugin from the list.")
                return
            
            item_id = selection[0]
            name = list_tree.item(item_id, 'text')
            module = plugin_map.get(item_id)

            for widget in plugin_area.winfo_children():
                widget.destroy() # 清理之前的插件 UI

            if module and hasattr(module, "register"):
                try:
                    # 使用 config.safe_call 确保插件注册过程中不会崩溃主程序
                    safe_call(lambda: module.register(self, plugin_area))
                    self._select_tab_by_name("Plugins")
                    log(f"插件 {name} 注册完成")
                except Exception as e:
                    import traceback
                    ttk.Label(plugin_area, text=f"插件 {name} 注册失败: {e}", bootstyle="danger").pack(padx=10, pady=10)
                    log(f"插件 {name} 注册失败:\n{traceback.format_exc()}")
            else:
                ttk.Label(plugin_area, text=f"插件 {name} 无 register(app, parent_frame) 函数或不可用", bootstyle="danger").pack(padx=10, pady=10)


        list_tree.bind('<Double-1>', load_plugin_command)
        
        ttk.Button(list_frame, text="Load Selected Plugin", command=load_plugin_command, bootstyle="primary").pack(fill="x", pady=6)


        # --- 右侧：插件 UI 区域 ---
        plugin_area_frame = ttk.Frame(paned)
        paned.add(plugin_area_frame, weight=1)
        
        plugin_area = ttk.Frame(plugin_area_frame, padding=10, relief="groove", borderwidth=1)
        plugin_area.pack(fill="both", expand=True, padx=5, pady=5)

        ttk.Label(plugin_area, text="--- Selected Plugin UI Will Load Here ---", bootstyle="secondary").pack(pady=20)

        self.notebook.add(frame, text="Plugins") 
        self.notebook.select(frame)


    # ----------------------------
    # Welcome Tab
    # ----------------------------
    def _create_welcome_tab(self):
        frame = ttk.Frame(self.notebook)
        
        ttk.Label(frame, text="Welcome to Universal Toolbox (Modular)", font=("Segoe UI", 16, "bold")).pack(padx=20, pady=20, anchor="w")
        
        desc = ("这是一个基于 **ttkbootstrap** 的模块化工具框架。\n"
                "所有功能都被设计为**插件**。请点击 **Refresh Explorer** 查看工作区文件，\n"
                "或导航到 **Plugins** 标签页，并双击列表中的插件来加载其 UI。\n\n"
                "要添加新功能，请将 Python 模块放置在 `plugins/` 目录下。\n"
                "每个插件都需要一个 `register(app, parent_frame)` 函数来渲染 UI。")
                
        ttk.Label(frame, text=desc, wraplength=700, justify="left").pack(padx=20, anchor="w")

        self.notebook.add(frame, text="Welcome")
        self.notebook.select(frame)
        
    def _bind_global_events(self):
        # 通用鼠标滚轮滚动
        def _on_mousewheel(event):
            widget = event.widget
            # 仅在非文本控件上执行滚动，避免冲突
            if not isinstance(widget, scrolledtext.ScrolledText):
                try:
                    if hasattr(widget, 'yview_scroll'):
                        widget.yview_scroll(int(-1*(event.delta/120)), "units")
                except Exception:
                    pass
        
        # Binds for font size adjustment (Ctrl+Mousewheel)
        def _on_ctrl_scroll(event):
            # 检查 Control 键是否按下 (event.state & 0x0004)
            if event.state & 0x0004: 
                 if event.delta > 0:
                     self._adjust_font(1)
                 elif event.delta < 0:
                     self._adjust_font(-1)
                 return "break" # 阻止默认滚动
            else:
                 _on_mousewheel(event)

        # 仅绑定一次带 Control 的滚动事件 (它也会捕获普通滚动)
        self.root.bind_all("<Control-MouseWheel>", _on_ctrl_scroll)
        self.root.bind_all("<Control-s>", lambda e: self.save_active_file())
        self.root.bind_all("<Control-w>", lambda e: self.close_active_tab())
        
        # 针对 Unix/Linux 系统，可能需要绑定 <Button-4> 和 <Button-5>
        self.root.bind_all("<Control-Button-4>", lambda e: self._adjust_font(1))
        self.root.bind_all("<Control-Button-5>", lambda e: self._adjust_font(-1))


if __name__ == '__main__':
    print("--- Starting Universal Toolbox Application ---")
    
    # 确保 config.APP_DIR 在 tk 启动前可用
    if not hasattr(config, 'APP_DIR'):
          print("Configuration issue: APP_DIR not set. Using current working directory.")
          # Fallback for main execution environment
          try:
              class ConfigPlaceholder:
                  APP_DIR = pathlib.Path(os.getcwd())
                  def discover_plugins(self): return []
              config = ConfigPlaceholder()
          except NameError:
              pass

    root = tb.Window(themename="superhero")
    app = ToolboxApp(root)
    root.mainloop()

    # 在应用退出时，恢复标准输出/错误
    if isinstance(sys.stdout, ConsoleRedirector):
        sys.stdout = sys.__stdout__
    if isinstance(sys.stderr, ConsoleRedirector):
        sys.stderr = sys.__stderr__
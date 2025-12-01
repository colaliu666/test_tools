import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ttkbootstrap as tb
import os
import sys
import threading
import subprocess
import pathlib
import io
import contextlib
import tk.scrolledtext # 确保导入了scrolledtext

# 核心依赖
try:
    import src.config as config
except ImportError:
    # 仅用于 IDE 静态分析，运行时依赖 main_app 的导入
    class MockConfig:
        APP_DIR = pathlib.Path(__file__).parent.parent.parent.parent.resolve()
        @staticmethod
        def log(*args, **kwargs): pass
        @staticmethod
        def safe_call(*args, **kwargs): return None
    config = MockConfig()


# --- 插件元数据 ---
PLUGIN_META = {
    "name": "Script Runner & Browser",
    "version": "1.0",
    "description": "Browse and execute Python scripts from the 'scripts/' directory.",
    "author": "Gemini AI"
}

class ScriptRunnerPlugin:
    """脚本运行器插件的 UI 和逻辑封装。"""
    
    def __init__(self, app, parent_frame):
        self.app = app
        self.parent_frame = parent_frame
        self.script_dir = config.APP_DIR / "scripts" # 使用 config.APP_DIR
        self.current_script_path = None
        self.is_running = False
        
        # 确保 scripts 目录存在
        self.script_dir.mkdir(exist_ok=True)
        
        self._build_ui()
        self._refresh_script_list()

    def _build_ui(self):
        # 创建一个主容器
        main_paned = ttk.Panedwindow(self.parent_frame, orient=tk.HORIZONTAL)
        main_paned.pack(fill="both", expand=True, padx=10, pady=10)

        # -------------------
        # 1. 左侧: 脚本列表
        # -------------------
        list_frame = ttk.Frame(main_paned, width=300)
        main_paned.add(list_frame, weight=0)
        
        ttk.Label(list_frame, text="Available Scripts (*.py)", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 5))
        
        self.script_tree = ttk.Treeview(list_frame, show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.script_tree.yview)
        self.script_tree.configure(yscrollcommand=vsb.set)
        
        self.script_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        self.script_tree.bind("<<TreeviewSelect>>", self._on_script_select)
        
        # 刷新/创建按钮
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill="x", pady=(5, 0))
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_script_list, bootstyle="secondary").pack(side="left", expand=True, fill="x", padx=(0, 2))
        ttk.Button(btn_frame, text="New Script", command=self._create_new_script, bootstyle="info").pack(side="left", expand=True, fill="x", padx=(2, 0))

        # -------------------
        # 2. 右侧: 脚本详情与运行
        # -------------------
        detail_frame = ttk.Frame(main_paned)
        main_paned.add(detail_frame, weight=1)
        
        # 路径显示
        self.path_label = ttk.Label(detail_frame, text=f"Scripts Directory: {self.script_dir}", wraplength=500)
        self.path_label.pack(anchor="w", pady=(0, 5))
        
        # 运行按钮
        self.run_btn = ttk.Button(detail_frame, text="▶ Run Selected Script", command=self._run_selected_script, bootstyle="success", state=tk.DISABLED)
        self.run_btn.pack(fill="x", pady=10)
        
        # 脚本内容预览
        ttk.Label(detail_frame, text="Script Preview (Read-Only):").pack(anchor="w", pady=(5, 2))
        self.preview_text = scrolledtext.ScrolledText(detail_frame, wrap="none", height=15, state=tk.DISABLED, font=('Consolas', 10))
        self.preview_text.pack(fill="both", expand=True)
        
    def _refresh_script_list(self):
        """扫描 scripts 目录并更新 Treeview 列表。"""
        self.script_tree.delete(*self.script_tree.get_children())
        self.path_label.config(text=f"Scripts Directory: {self.script_dir}")
        self.current_script_path = None
        self.run_btn.config(state=tk.DISABLED)
        
        if not self.script_dir.exists():
            self.script_dir.mkdir(parents=True)
        
        for p in sorted(self.script_dir.glob("*.py")):
            self.script_tree.insert("", "end", text=p.name, iid=str(p.resolve()))

        if not self.script_tree.get_children():
            self.app.log_to_console("Script Runner: No Python scripts found.", tag='info')

    def _on_script_select(self, event):
        """当用户在列表中选择一个脚本时触发。"""
        selected_id = self.script_tree.focus()
        if not selected_id:
            self.current_script_path = None
            self._update_preview("No script selected.")
            self.run_btn.config(state=tk.DISABLED)
            return
            
        path_str = selected_id
        self.current_script_path = pathlib.Path(path_str)
        self.run_btn.config(state=tk.NORMAL if not self.is_running else tk.DISABLED)
        
        self._load_preview()
        
    def _load_preview(self):
        """加载选定脚本的内容到预览文本框。"""
        if not self.current_script_path or not self.current_script_path.is_file():
            self._update_preview("Error: Invalid script path.")
            return

        try:
            with open(self.current_script_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            self._update_preview(content)
            self.app.log_to_console(f"Preview loaded: {self.current_script_path.name}")
        except Exception as e:
            self._update_preview(f"Error reading file: {e}")
            self.app.log_to_console(f"Error loading script preview: {e}", tag='error')

    def _update_preview(self, content):
        """更新预览文本框的内容。"""
        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", content)
        self.preview_text.config(state=tk.DISABLED)

    def _create_new_script(self):
        """在 scripts 目录中创建一个新的空脚本文件，并在主应用中打开它。"""
        name = messagebox.askstring("New Script", "Enter new script file name (e.g., my_new_script.py):", parent=self.parent_frame)
        if name:
            if not name.lower().endswith(".py"):
                name += ".py"
            
            full_path = self.script_dir / name
            
            if full_path.exists():
                messagebox.showwarning("Exists", f"File '{name}' already exists.")
                return

            try:
                # 创建一个包含基本信息的空脚本
                initial_content = f'# Script: {name}\n\n' \
                                  f'import sys\n' \
                                  f'import src.config as config\n\n' \
                                  f'print("Hello from {name}!")\n' \
                                  f'# You can use config.log() for logging to the console\n' \
                                  f'config.log("Example log from script", tag="script")\n'
                                  
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(initial_content)

                self.app.log_to_console(f"Created new script: {name}", tag='info')
                self._refresh_script_list()
                
                # 尝试在主应用的编辑器中打开
                if hasattr(self.app, 'open_file'):
                    self.app.open_file(full_path)
                    
            except Exception as e:
                messagebox.showerror("Creation Error", f"Could not create script: {e}")

    def _run_selected_script(self):
        """在后台线程中执行选定的 Python 脚本。"""
        if self.is_running or not self.current_script_path:
            return

        script_path = self.current_script_path
        if not script_path.is_file():
            self.app.log_to_console("Error: Selected script file not found.", tag='error')
            return

        if messagebox.askyesno("Confirm Run", f"Execute script '{script_path.name}'?"):
            self.app.log_to_console("-" * 40, tag='info')
            self.app.log_to_console(f"Starting execution of: {script_path.name}...", tag='info')
            
            self.is_running = True
            self.run_btn.config(state=tk.DISABLED, text="Running...")
            
            # 使用线程来防止 GUI 阻塞
            thread = threading.Thread(target=self._execute_script_thread, args=(script_path,))
            thread.start()

    def _execute_script_thread(self, script_path: pathlib.Path):
        """实际的脚本执行逻辑，在单独的线程中运行。"""
        
        # 备份 sys.path
        current_sys_path = sys.path[:]
        
        # 暂时修改 sys.path，确保脚本可以导入 src.config
        project_root = str(config.APP_DIR)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        stdout_backup = sys.stdout
        stderr_backup = sys.stderr
        
        # 使用 io.StringIO 捕获脚本的输出
        capture_output = io.StringIO()

        try:
            # 重定向 stdout/stderr 到 StringIO
            sys.stdout = capture_output
            sys.stderr = capture_output

            # 准备执行环境
            global_namespace = {
                '__name__': '__main__', 
                'app': self.app, # 将主应用实例传递给脚本
                'config': config # 将 config 模块传递给脚本
            }
            
            # 使用 exec() 运行脚本
            with open(script_path, 'r', encoding='utf-8') as f:
                code = compile(f.read(), script_path.name, 'exec')
                exec(code, global_namespace) 
            
            self.app.log_to_console(f"Execution of {script_path.name} finished successfully.", tag='info')
            
        except SystemExit:
            self.app.log_to_console(f"Script {script_path.name} called sys.exit().", tag='info')
        except Exception as e:
            # 捕获运行时错误
            self.app.log_to_console(f"Runtime Error in {script_path.name}: {e}", tag='error')
            # 捕获堆栈信息
            import traceback
            error_trace = traceback.format_exc()
            self.app.log_to_console(f"Traceback:\n{error_trace}", tag='debug')
        finally:
            # 恢复 stdout 和 stderr
            sys.stdout = stdout_backup
            sys.stderr = stderr_backup
            
            # 恢复 sys.path
            sys.path = current_sys_path

            # 将捕获的输出发送到主应用的日志控制台
            captured_log = capture_output.getvalue()
            if captured_log.strip():
                self.app.log_to_console(f"\n--- Script STDOUT/STDERR Output from {script_path.name} ---\n{captured_log.strip()}\n--- End Output ---")

            # 切换回主线程更新 UI
            self.app.root.after(10, self._execution_finished)

    def _execution_finished(self):
        """在主线程中执行，用于清理和恢复 UI 状态。"""
        self.is_running = False
        self.run_btn.config(state=tk.NORMAL, text="▶ Run Selected Script")
        self.app.log_to_console(f"Script runner finalized.", tag='system')
        self.app.log_to_console("-" * 40, tag='info')


def register(app, parent_frame: ttk.Frame):
    """插件注册入口函数。"""
    ScriptRunnerPlugin(app, parent_frame)
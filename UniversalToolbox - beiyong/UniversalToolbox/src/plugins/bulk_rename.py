# plugins/bulk_rename.py

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ttkbootstrap.constants import *

# 直接导入同级 config 模块
try:
    import config
    run_background = config.run_background
    safe_call = config.safe_call
    log = config.log
except ImportError:
    # 插件加载失败时的降级方案
    def log(*args): print(f"[PLUGIN] {' '.join(str(a) for a in args)}")
    def run_background(func, on_done=None, *args, **kwargs):
        try: result = func(*args, **kwargs)
        except Exception as e: result, e = None, e
        if on_done: on_done(result, e)
    def safe_call(func, *args, **kwargs): return func(*args, **kwargs)

name = "Bulk_Renamer"

class BulkRenamerUI:
    """批量重命名插件的 UI 和逻辑类"""
    def __init__(self, app, parent_frame):
        self.app = app
        self.parent = parent_frame
        self.dir_path = tk.StringVar(value="")
        self.find_text = tk.StringVar(value="")
        self.replace_text = tk.StringVar(value="")
        self.file_list = []
        self._create_ui()

    def _create_ui(self):
        # --- 标题 ---
        ttk.Label(self.parent, text="批量文件重命名工具", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=8, pady=6)
        
        # --- 目录选择 ---
        dir_frame = ttk.Frame(self.parent)
        dir_frame.pack(fill="x", padx=8, pady=4)
        ttk.Label(dir_frame, text="目标目录:", width=10).pack(side="left")
        ttk.Entry(dir_frame, textvariable=self.dir_path, width=60).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(dir_frame, text="选择目录", command=self._select_directory, bootstyle="info-outline").pack(side="left")

        # --- 查找与替换设置 ---
        setting_frame = ttk.Frame(self.parent)
        setting_frame.pack(fill="x", padx=8, pady=4)
        
        ttk.Label(setting_frame, text="查找文本:", width=10).pack(side="left")
        ttk.Entry(setting_frame, textvariable=self.find_text, width=25).pack(side="left", padx=4)
        
        ttk.Label(setting_frame, text="替换为:", width=8).pack(side="left", padx=(12, 4))
        ttk.Entry(setting_frame, textvariable=self.replace_text, width=25).pack(side="left", padx=4)
        
        ttk.Button(setting_frame, text="预览重命名", command=lambda: safe_call(self._preview_rename), bootstyle="primary").pack(side="left", padx=(20, 4))
        ttk.Button(setting_frame, text="执行重命名", command=lambda: safe_call(self._execute_rename), bootstyle="danger").pack(side="left")

        # --- 预览列表 ---
        ttk.Label(self.parent, text="重命名预览 (原文件名 -> 新文件名):").pack(anchor="w", padx=8, pady=(8, 4))
        self.preview_tree = ttk.Treeview(self.parent, columns=("original", "new"), show="headings", height=15)
        self.preview_tree.heading("original", text="原始文件名")
        self.preview_tree.heading("new", text="新文件名")
        self.preview_tree.column("original", width=300, anchor="w")
        self.preview_tree.column("new", width=300, anchor="w")
        
        vsb = ttk.Scrollbar(self.parent, orient="vertical", command=self.preview_tree.yview)
        vsb.pack(side="right", fill="y", padx=8)
        self.preview_tree.configure(yscrollcommand=vsb.set)
        
        self.preview_tree.pack(fill="both", expand=True, padx=8, pady=4)

        log(f"插件 {name} UI 初始化完成。")

    def _select_directory(self):
        """打开目录选择对话框"""
        initial_dir = str(config.APP_DIR) if config.APP_DIR else os.getcwd()
        path = filedialog.askdirectory(initialdir=initial_dir, title="选择要重命名的目录")
        if path:
            self.dir_path.set(path)
            self._preview_rename()

    def _preview_rename(self):
        """生成文件重命名预览"""
        dir_path = self.dir_path.get()
        find_text = self.find_text.get()
        replace_text = self.replace_text.get()
        self.file_list = []

        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
            
        if not os.path.isdir(dir_path):
            log("错误: 目标目录无效或未选择。")
            return

        if not find_text:
            log("警告: 查找文本不能为空。")
            self.app.update_status("查找文本不能为空。")
            return

        for filename in os.listdir(dir_path):
            if os.path.isfile(os.path.join(dir_path, filename)):
                if find_text in filename:
                    new_filename = filename.replace(find_text, replace_text)
                    self.file_list.append((filename, new_filename))
                    self.preview_tree.insert("", "end", values=(filename, new_filename), tags=("preview",))

        log(f"生成了 {len(self.file_list)} 个文件的重命名预览。")
        self.app.update_status(f"预览完成: {len(self.file_list)} 个文件将被重命名。")

    def _execute_rename(self):
        """执行重命名操作"""
        if not self.file_list:
            messagebox.showinfo("警告", "没有文件需要重命名，请先点击 '预览重命名'。")
            return

        if not messagebox.askyesno("确认操作", f"确定要重命名 {len(self.file_list)} 个文件吗？此操作不可撤销！"):
            return

        dir_path = self.dir_path.get()
        
        # 定义后台执行函数
        def rename_task():
            count = 0
            for original, new in self.file_list:
                old_path = os.path.join(dir_path, original)
                new_path = os.path.join(dir_path, new)
                
                if os.path.exists(new_path):
                    # 避免覆盖现有文件，跳过
                    log(f"跳过: {new} 已存在。")
                    continue
                
                os.rename(old_path, new_path)
                count += 1
            return count

        # 定义完成回调函数
        def on_done(count, exc):
            if exc:
                log(f"批量重命名失败: {exc}")
                messagebox.showerror("错误", f"批量重命名失败: {exc}")
                self.app.update_status("重命名失败。")
            else:
                log(f"成功重命名 {count} 个文件。")
                messagebox.showinfo("成功", f"成功重命名 {count} 个文件。")
                self.app.update_status(f"重命名完成: 成功 {count} 个文件。")
                self._preview_rename() # 刷新预览列表

        # 在后台线程中运行，避免 UI 冻结
        run_background(rename_task, on_done=on_done)


def register(app, parent_frame):
    """插件入口函数"""
    BulkRenamerUI(app, parent_frame)
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ttkbootstrap.constants import *
import traceback
import sys

# 尝试导入核心库
try:
    # 插件需要 pandas 和 openpyxl 来处理 Excel (openpyxl 是 pandas 的一个依赖)
    import pandas as pd
    
    # 检查 Parquet 支持
    try:
        import pyarrow # Parquet support usually requires pyarrow
        HAS_PARQUET = True
    except ImportError:
        HAS_PARQUET = False
        
except ImportError:
    pd = None
    HAS_PARQUET = False

# 核心修正: 使用相对导入来访问 src/config.py
try:
    from .. import config
    run_background = config.run_background
    safe_call = config.safe_call
    log = config.log
except ImportError:
    # 依赖降级方案
    def log(*args, level="INFO"): print(f"[{level}][PLUGIN] {' '.join(str(a) for a in args)}")
    def run_background(func, on_done=None, *args, **kwargs):
        log("警告: config 模块未完全加载，后台任务在主线程执行。", level="WARNING")
        try: result = func(*args, **kwargs)
        except Exception as e: result, e = None, e
        if on_done: on_done(result, e)
    def safe_call(func, *args, **kwargs):
        try: return func(*args, **kwargs)
        except Exception as e: log(f"Safe call failed: {e}", level="ERROR"); return None

name = "Data_Converter"

# --- 核心格式映射定义 ---
# 映射格式名到其扩展名、pandas读取和写入函数
FORMAT_MAP = {
    "CSV": {
        "ext": ".csv",
        "read": "read_csv",
        "write": "to_csv"
    },
    "Excel": {
        "ext": ".xlsx",
        "read": "read_excel",
        "write": "to_excel"
    },
    "JSON": {
        "ext": ".json",
        "read": "read_json",
        "write": "to_json"
    },
}

# 动态添加 Parquet (如果依赖存在)
if HAS_PARQUET:
    FORMAT_MAP["Parquet"] = {
        "ext": ".parquet",
        "read": "read_parquet",
        "write": "to_parquet"
    }

SUPPORTED_FORMATS = list(FORMAT_MAP.keys()) # ["CSV", "Excel", "JSON", "Parquet"]


class DataConverterUI:
    """CSV/Excel 格式转换插件的 UI 和逻辑类"""
    def __init__(self, app, parent_frame):
        self.app = app
        self.parent = parent_frame
        
        # 状态变量
        self.input_path = tk.StringVar(value="")
        self.output_path = tk.StringVar(value="")
        # 核心修正：使用独立的输入和输出格式变量
        self.input_format = tk.StringVar(value="CSV")
        self.output_format = tk.StringVar(value="Excel")
        
        self.disabled = (pd is None) # 依赖检查在 register 函数中已完成
        
        self._create_ui()

    def _create_ui(self):
        # --- 标题 ---
        ttk.Label(self.parent, text="多格式数据转换器 (支持自定义格式输入)", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=8, pady=6)
        
        # --- 转换模式选择 ---
        mode_frame = ttk.Frame(self.parent)
        mode_frame.pack(fill="x", padx=8, pady=4)
        
        # Input Format
        ttk.Label(mode_frame, text="输入格式:").pack(side="left", padx=(0, 5))
        # 核心修改 1: 移除 state="readonly" 以允许手动输入
        input_combo = ttk.Combobox(mode_frame, values=SUPPORTED_FORMATS, textvariable=self.input_format, width=12)
        input_combo.pack(side="left", padx=(0, 10))
        input_combo.bind("<<ComboboxSelected>>", self._update_output_path)
        
        # Separator Label
        ttk.Label(mode_frame, text="->", font=("Segoe UI", 10, "bold")).pack(side="left", padx=5)

        # Output Format
        ttk.Label(mode_frame, text="输出格式:").pack(side="left", padx=(10, 5))
        # 核心修改 2: 移除 state="readonly" 以允许手动输入
        output_combo = ttk.Combobox(mode_frame, values=SUPPORTED_FORMATS, textvariable=self.output_format, width=12)
        output_combo.pack(side="left")
        output_combo.bind("<<ComboboxSelected>>", self._update_output_path)


        # --- 输入文件选择 ---
        input_frame = ttk.Frame(self.parent)
        input_frame.pack(fill="x", padx=8, pady=4)
        ttk.Label(input_frame, text="输入文件:", width=10).pack(side="left")
        ttk.Entry(input_frame, textvariable=self.input_path, width=60).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(input_frame, text="选择文件", command=self._select_input_file, bootstyle="info-outline").pack(side="left")

        # --- 输出文件路径 ---
        output_frame = ttk.Frame(self.parent)
        output_frame.pack(fill="x", padx=8, pady=4)
        ttk.Label(output_frame, text="输出路径:", width=10).pack(side="left")
        ttk.Entry(output_frame, textvariable=self.output_path, width=60).pack(side="left", fill="x", expand=True, padx=4)
        self.save_button = ttk.Button(output_frame, text="选择保存", command=self._select_output_file, bootstyle="info-outline")
        self.save_button.pack(side="left")

        # --- 执行按钮 ---
        exec_frame = ttk.Frame(self.parent)
        exec_frame.pack(fill="x", padx=8, pady=10)
        self.convert_button = ttk.Button(exec_frame, text="开始转换", 
                                         command=lambda: safe_call(self._start_conversion), 
                                         bootstyle="success")
        self.convert_button.pack(side="right")
        
        if self.disabled:
            self.convert_button.configure(state="disabled", text="依赖缺失")

        log(f"插件 {name} UI 初始化完成。")
        self.app.update_status(f"Data Converter 已加载。")


    # --- 文件选择逻辑 ---
    
    def _get_filetypes_and_ext(self, format_name):
        """根据格式名获取文件类型列表和默认扩展名"""
        if format_name in FORMAT_MAP:
            info = FORMAT_MAP[format_name]
            ext = info['ext']
            filetypes = [(f"{format_name} Files", f"*{ext}"), ("All Files", "*.*")]
            return filetypes, ext
        
        # 核心修改 3: 支持自定义格式，返回通用文件类型和推断的扩展名
        custom_ext = f".{format_name.lower()}" if format_name else ""
        return [("All Files", "*.*")], custom_ext

    def _select_input_file(self):
        """打开文件对话框选择输入文件"""
        current_format = self.input_format.get()
        # 核心修改 4: 如果是自定义格式，先尝试获取默认扩展名作为筛选器
        filetypes, default_ext = self._get_filetypes_and_ext(current_format)
        
        path = filedialog.askopenfilename(title=f"选择 {current_format} 输入文件", filetypes=filetypes)
        if path:
            self.input_path.set(path)
            self._update_output_path(None)

    def _update_output_path(self, event):
        """根据输入文件和输出格式，生成默认输出路径"""
        input_path = self.input_path.get()
        if not input_path:
            self.output_path.set("")
            return

        base_name = os.path.splitext(input_path)[0]
        input_fmt = self.input_format.get()
        output_fmt = self.output_format.get()
        
        if output_fmt in FORMAT_MAP:
            new_ext = FORMAT_MAP[output_fmt]['ext']
            
            # 移除输入文件原有的扩展名，避免出现 file.csv.xlsx 的情况
            parts = base_name.rsplit('.', 1)
            # 检查 parts[-1] 是否是任何已知格式的扩展名（不包括点）
            known_extensions = [v['ext'].strip('.') for v in FORMAT_MAP.values()]
            clean_base_name = parts[0] if len(parts) > 1 and parts[-1] in known_extensions else base_name
            
            # 如果输入输出格式相同，添加 '_converted'
            if input_fmt == output_fmt:
                new_path = f"{clean_base_name}_converted{new_ext}"
            else:
                new_path = f"{clean_base_name}{new_ext}"
            
            self.output_path.set(new_path)
        else:
            # 核心修改 5: 对于自定义输出格式，尝试推断扩展名
            new_ext = f".{output_fmt.lower()}"
            self.output_path.set(f"{base_name}{new_ext}")

    def _select_output_file(self):
        """打开文件保存对话框选择输出文件"""
        output_format = self.output_format.get()
        filetypes, default_ext = self._get_filetypes_and_ext(output_format)
        default_path = self.output_path.get()
        if not default_path:
            default_path = f"output{default_ext}"
            
        path = filedialog.asksaveasfilename(
            defaultextension=default_ext,
            filetypes=filetypes,
            initialfile=os.path.basename(default_path),
            title="选择保存路径"
        )
        if path:
            self.output_path.set(path)

    # --- 转换核心逻辑 ---

    def _conversion_task(self, input_path, output_path, input_fmt, output_fmt):
        """实际执行转换的后台函数"""
        log(f"开始转换: {input_fmt} -> {output_fmt}")

        # 核心修改 6: 统一获取 pandas 函数名，支持自定义格式的推断
        def get_func_name(fmt, prefix):
            if fmt in FORMAT_MAP:
                key = 'read' if prefix == 'read' else 'write'
                return FORMAT_MAP[fmt][key]
            # 尝试基于约定派生函数名 (e.g., HDF5 -> read_hdf5, to_hdf5)
            return f"{prefix}_{fmt.lower()}"
            
        read_func_name = get_func_name(input_fmt, 'read')
        write_func_name = get_func_name(output_fmt, 'to')
        
        # 1. 动态读取数据 (read)
        read_func = getattr(pd, read_func_name, None)
        if not read_func:
             raise AttributeError(f"Pandas 不支持读取格式 '{input_fmt}'。找不到函数 'pd.{read_func_name}'。")

        # 针对 CSV 做编码处理
        if input_fmt == "CSV":
            try:
                df = read_func(input_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = read_func(input_path, encoding='gbk')
        
        # 针对 JSON 明确指定 orient='records' 以确保兼容性
        elif input_fmt == "JSON":
            df = read_func(input_path, orient='records')
            
        else:
            # 对于其他已知格式或自定义格式，直接调用函数
            df = read_func(input_path) 

        # 2. 动态写入数据 (write)
        write_func = getattr(df, write_func_name, None)
        if not write_func:
            raise AttributeError(f"Pandas 不支持写入格式 '{output_fmt}'。找不到函数 'df.{write_func_name}'。")
        
        # 针对 CSV/Excel 写入时排除 index
        if output_fmt in ["CSV", "Excel"]:
             write_func(output_path, index=False)
        
        # 针对 JSON 明确指定 orient='records' 以确保兼容性
        elif output_fmt == "JSON":
             write_func(output_path, orient='records')
             
        else:
            # For Parquet or custom formats, default write call
            write_func(output_path)
            
        return f"成功将 {input_fmt} 转换为 {output_fmt}: {output_path}"

    def _start_conversion(self):
        """启动后台转换任务"""
        input_path = self.input_path.get()
        output_path = self.output_path.get()
        input_fmt = self.input_format.get()
        output_fmt = self.output_format.get()
        
        if not all([input_path, output_path]):
            messagebox.showerror("错误", "请选择输入文件和输出路径。")
            return
            
        if not os.path.exists(input_path):
            messagebox.showerror("错误", "输入文件不存在。")
            return
            
        # 允许相同的格式，但会依赖用户修改输出路径 (例如: JSON -> JSON_converted)
        # if input_fmt == output_fmt:
        #     messagebox.showerror("错误", "输入格式和输出格式不能相同。")
        #     return
            
        # 定义任务完成后的回调
        def on_done(result, exc):
            self.convert_button.configure(state="normal", bootstyle="success")
            if exc:
                log(f"转换失败: {exc}")
                # 使用 Tkinter 的 after 方法确保在主线程中显示 messagebox
                self.app.root.after(0, lambda: messagebox.showerror("转换失败", f"文件转换失败: {exc}"))
                self.app.update_status("转换失败。")
            else:
                log(result)
                # 使用 Tkinter 的 after 方法确保在主线程中显示 messagebox
                self.app.root.after(0, lambda: messagebox.showinfo("转换成功", result))
                self.app.update_status(f"转换成功: {input_fmt} -> {output_fmt}")
        
        # 禁用按钮，显示状态
        self.convert_button.configure(state="disabled", bootstyle="secondary")
        self.app.update_status(f"正在后台执行转换: {input_fmt} -> {output_fmt}...")
        
        # 启动后台任务
        run_background(self._conversion_task, on_done, input_path, output_path, input_fmt, output_fmt)


def register(app, parent_frame):
    """插件入口函数，检查依赖并创建 UI"""
    
    missing_deps = []
    if pd is None:
        missing_deps.append("pandas (必要)")
    if 'Parquet' in SUPPORTED_FORMATS and not HAS_PARQUET:
        missing_deps.append("pyarrow (用于 Parquet 格式)")
        
    if missing_deps:
        # 如果依赖检查失败，则只显示提示信息
        error_frame = ttk.Frame(parent_frame, padding=15, bootstyle="danger")
        error_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(error_frame, 
                  text="🔴 依赖缺失: 部分或全部功能不可用。", 
                  bootstyle="inverse-danger",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(error_frame, 
                  text="所需依赖：\n - " + "\n - ".join(missing_deps), 
                  bootstyle="inverse-danger").pack(anchor="w", pady=(5,5))
        ttk.Label(error_frame, 
                  text="请在您的终端中运行: pip install pandas openpyxl pyarrow", 
                  bootstyle="inverse-danger").pack(anchor="w")
                  
        log("Data Converter 插件加载失败，缺少依赖。")
        
        # 即使缺少依赖，如果 pd 存在，仍然允许加载 UI，只是禁用转换按钮
        if pd:
            DataConverterUI(app, parent_frame)
        else:
            return
    else:
        DataConverterUI(app, parent_frame)
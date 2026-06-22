"""
生成各 nearMem 配置相对 baseline 的加速比矩阵。

功能:
  基于 matrix_ipc.py 输出的 IPC 矩阵，计算每个 nearMem 配置
  在每个窗口、每个 CPU 上相对于 baseline 的加速比（speedup = IPC_nm / IPC_bl），
  生成 窗口×CPU 的加速比矩阵 CSV。

依赖:
  需要先运行 matrix_ipc.py 生成 ipc_matrix_*.csv

输入:
  output_dir/ipc_matrix_baseline.csv 和 output_dir/ipc_matrix_{config}.csv

输出:
  output_dir/speedup_matrix_{config}.csv — 各 nearMem 配置的加速比矩阵

用法:
  python3 matrix_speedup.py
"""
import pandas as pd
import numpy as np
import os
import json

# 加载配置
with open('config.json', 'r') as f:
    config = json.load(f)
OUTPUT_DIR = config['OUTPUT_DIR']
os.makedirs(OUTPUT_DIR, exist_ok=True)

all_cpus = config['all_cpus']
nearmem_configs = config['nearmem_configs']
WINDOW = config['window_size']

baseline = pd.read_csv(os.path.join(OUTPUT_DIR, 'ipc_matrix_baseline.csv'))

for c in nearmem_configs:
    nm = pd.read_csv(os.path.join(OUTPUT_DIR, f'ipc_matrix_{c}.csv'))
    
    rows = []
    for i in range(len(nm)):
        row = {'window': nm.iloc[i]['window'], 'tti_range': nm.iloc[i]['tti_range']}
        for cpu in all_cpus:
            col = f'cpu{cpu}'
            bl_val = baseline.iloc[i][col]
            nm_val = nm.iloc[i][col]
            row[col] = nm_val / bl_val if bl_val and bl_val > 0 and not pd.isna(bl_val) and not pd.isna(nm_val) else np.nan
        rows.append(row)
    
    result = pd.DataFrame(rows)
    cols = ['window', 'tti_range'] + [f'cpu{cpu}' for cpu in all_cpus]
    result = result[cols]
    
    fname = os.path.join(OUTPUT_DIR, f'speedup_matrix_{c}.csv')
    result.to_csv(fname, index=False, float_format='%.4f')
    print(f'Saved: {fname}')

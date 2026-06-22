"""
为每个配置生成 IPC 矩阵（滑动窗口 × CPU）。

功能:
  对每个配置，在连续 N 个 TTI 的滑动窗口上，计算每个 CPU 的 IPC
  （numInsts / workCycles），生成 窗口×CPU 的矩阵 CSV。
  输出是 matrix_speedup.py 的前置依赖。

输入:
  data_dir/*.csv — 各配置的模拟数据 CSV

输出:
  output_dir/ipc_matrix_{config}.csv — 每个配置的 IPC 矩阵

用法:
  python3 matrix_ipc.py
"""
import pandas as pd
import numpy as np
import os
import json

# 加载配置
with open('config.json', 'r') as f:
    config = json.load(f)
DATA_DIR = config['DATA_DIR']
OUTPUT_DIR = config['OUTPUT_DIR']
os.makedirs(OUTPUT_DIR, exist_ok=True)

all_cpus = config['all_cpus']
configs = config['configs']

WINDOW = config['window_size']

# 加载所有数据
data = {}
for c in configs:
    data[c] = pd.read_csv(os.path.join(DATA_DIR, f'{c}.csv'))

# 对每个配置，生成 纵轴=窗口序号, 横轴=cpu0~cpu15 的矩阵
for c in configs:
    df = data[c]
    valid_ttis = sorted(df['TTI'].dropna().unique())
    
    rows = []
    for i in range(len(valid_ttis) - WINDOW + 1):
        tti_start = valid_ttis[i]
        tti_end = valid_ttis[i + WINDOW - 1]
        if tti_end > config['tti_end']:  # 只统计到指定 TTI 范围
            break
        sub = df[(df['TTI'] >= tti_start) & (df['TTI'] <= tti_end)]
        
        row = {'window': i + 1, 'tti_range': f'{tti_start:.0f}-{tti_end:.0f}'}
        for cpu in all_cpus:
            inst = sub[f'system.cpu{cpu}.numInsts'].sum()
            cyc = sub[f'system.cpu{cpu}.workCycles'].sum()
            row[f'cpu{cpu}'] = inst / cyc if cyc > 0 else np.nan
        rows.append(row)
    
    result = pd.DataFrame(rows)
    cols = ['window', 'tti_range'] + [f'cpu{cpu}' for cpu in all_cpus]
    result = result[cols]
    
    fname = os.path.join(OUTPUT_DIR, f'ipc_matrix_{c}.csv')
    result.to_csv(fname, index=False, float_format='%.6f')
    print(f'Saved: {fname}')

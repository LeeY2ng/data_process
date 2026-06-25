"""
为每个配置生成逐 TTI 的 IPC 矩阵。

功能:
  对每个配置，在每一个 TTI 上计算各关注 CPU 的 IPC（numInsts / workCycles），
  生成 TTI x CPU 的矩阵 CSV，用于观察 IPC 随时间（逐 TTI）的变化。

输入:
  data_dir/*.csv — 各配置的模拟数据 CSV

输出:
  output_dir/ipc_perTTI_{config}.csv — 每个配置的逐 TTI IPC 矩阵

用法:
  python3 matrix_ipc_per_tti.py
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

cpu_labels = [f'cpu{cpu}' for cpu in all_cpus]

for c in configs:
    df = pd.read_csv(os.path.join(DATA_DIR, f'{c}.csv'))
    
    # 构建 TTI x CPU 的 IPC 矩阵 (每格 = numInsts / workCycles)
    data = {}
    for cpu in all_cpus:
        inst_col = f'system.cpu{cpu}.numInsts'
        cyc_col = f'system.cpu{cpu}.workCycles'
        ipc = df[inst_col] / df[cyc_col]
        data[f'cpu{cpu}'] = ipc.values
    
    result = pd.DataFrame(data)
    result.insert(0, 'TTI', df['TTI'].values)
    
    # 保存 CSV
    result.to_csv(os.path.join(OUTPUT_DIR, f'ipc_perTTI_{c}.csv'), index=False, float_format='%.6f')
    
    print(f'{c}:')
    # 打印前几行和后几行示意
    print(result.head(6).to_string(index=False))
    print('  ...')
    print(result.tail(4).to_string(index=False))
    print()

"""
分析全部 16 个 CPU 合并后的总 IPC 滑动窗口。

功能:
  将全部 16 个 CPU 的 numInsts 和 workCycles 分别求和，计算全局 IPC，
  在连续 N 个 TTI 的滑动窗口上分析，找出各配置的最佳窗口。

输入:
  data_dir/*.csv — 各配置的模拟数据 CSV

输出:
  output_dir/ipc_all16cpu_sliding.csv — 各窗口的全局 IPC 及各配置最佳窗口

用法:
  python3 sliding_ipc_all16.py
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

START_TTI = config['sliding_window_start_tti']
END_TTI = config['sliding_window_end_tti']
WINDOW = config['window_size']

# 加载所有数据
data = {}
for c in configs:
    data[c] = pd.read_csv(os.path.join(DATA_DIR, f'{c}.csv'))

common_ttis = [t for t in range(START_TTI, END_TTI + 1)]

print(f"Common valid TTIs (TTI>={START_TTI}): {common_ttis[0]}-{common_ttis[-1]}")

# 对每个配置、每个窗口，计算所有16个CPU的总IPC = sum(insts) / sum(cycles)
rows = []
for c in configs:
    df = data[c]
    label = 'baseline' if c == 'baseline' else c[10:14]
    for i in range(len(common_ttis) - WINDOW + 1):
        tti_start = common_ttis[i]
        tti_end = common_ttis[i + WINDOW - 1]
        sub = df[(df['TTI'] >= tti_start) & (df['TTI'] <= tti_end)]
        
        total_inst = sum(sub[f'system.cpu{cpu}.numInsts'].sum() for cpu in all_cpus)
        total_cyc = sum(sub[f'system.cpu{cpu}.workCycles'].sum() for cpu in all_cpus)
        ipc = total_inst / total_cyc if total_cyc > 0 else 0
        
        rows.append({
            'config': c,
            'label': label,
            'tti_start': tti_start,
            'tti_end': tti_end,
            'total_inst': total_inst,
            'total_cyc': total_cyc,
            'ipc': ipc,
        })

df_out = pd.DataFrame(rows)
df_out.to_csv(os.path.join(OUTPUT_DIR, 'ipc_all16cpu_sliding.csv'), index=False, float_format='%.6f')
print(f'Saved: {os.path.join(OUTPUT_DIR, "ipc_all16cpu_sliding.csv")}')

# 找出每个配置的最佳窗口，写出汇总
best_rows = []
for c in configs:
    df_c = df_out[df_out['config'] == c]
    best = df_c.loc[df_c['ipc'].idxmax()]
    label = 'baseline' if c == 'baseline' else c[10:14]
    bl_at_win = df_out[(df_out['config'] == 'baseline') & (df_out['tti_start'] == best['tti_start'])]
    bl_ipc = bl_at_win.iloc[0]['ipc'] if not bl_at_win.empty else 0
    sp = best['ipc'] / bl_ipc if bl_ipc > 0 else 0
    best_rows.append({
        'config': label,
        'best_window': f"TTI {best['tti_start']:.0f}-{best['tti_end']:.0f}",
        'ipc': f"{best['ipc']:.6f}",
        'speedup_vs_baseline': f"{sp:.4f}"
    })

df_best = pd.DataFrame(best_rows)
best_txt = os.path.join(OUTPUT_DIR, 'ipc_all16cpu_sliding_best.txt')
with open(best_txt, 'w') as f:
    f.write("Best window per config (16 CPU total IPC)\n")
    f.write("=" * 60 + "\n")
    f.write(f"{'config':>12s}  {'best_window':>12s}  {'ipc':>12s}  {'speedup':>10s}\n")
    f.write("-" * 60 + "\n")
    for _, r in df_best.iterrows():
        f.write(f"{r['config']:>12s}  {r['best_window']:>12s}  {r['ipc']:>12s}  {r['speedup_vs_baseline']:>10s}\n")
print(f'Saved: {best_txt}')
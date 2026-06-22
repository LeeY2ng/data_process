"""
比较 baseline 和所有 nearMem 配置的 Cache 缺失率变化。

功能:
  逐 CPU 对比 L1D、L2、LLC 的 miss rate，计算各 nearMem 配置
  相对于 baseline 的变化百分比。覆盖全部 5 个 nearMem 配置。

输入:
  data_dir/*.csv — 各配置的模拟数据 CSV

输出:
  output_dir/missrate_change_TTI9-12.csv — 每核心每配置的 miss rate 变化

用法:
  python3 report_missrate.py
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
ttis = list(range(config['tti_start'], config['tti_end'] + 1))

# 读取 baseline
bl = pd.read_csv(os.path.join(DATA_DIR, 'baseline.csv'))
bl_sub = bl[bl['TTI'].isin(ttis)]

# 计算 baseline 各核心的 miss rate
bl_miss_rates = {}
for cpu in all_cpus:
    l1d_acc = bl_sub[f'system.cpu{cpu}.l1d.cache.m_demand_accesses'].sum()
    l1d_miss = bl_sub[f'system.cpu{cpu}.l1d.cache.m_demand_misses'].sum()
    l2_acc = bl_sub[f'system.cpu{cpu}.l2.cache.m_demand_accesses'].sum()
    l2_miss = bl_sub[f'system.cpu{cpu}.l2.cache.m_demand_misses'].sum()
    l3_acc = bl_sub[f'cpu{cpu}.l3access'].sum()
    l3_miss = bl_sub[f'cpu{cpu}.l3miss'].sum()
    bl_miss_rates[cpu] = {
        'l1d': l1d_miss / l1d_acc * 100 if l1d_acc > 0 else np.nan,
        'l2': l2_miss / l2_acc * 100 if l2_acc > 0 else np.nan,
        'l3': l3_miss / l3_acc * 100 if l3_acc > 0 else np.nan,
    }

# 收集所有数据用于 CSV
rows = []

for c in configs:
    if c == 'baseline':
        continue
    
    df = pd.read_csv(os.path.join(DATA_DIR, f'{c}.csv'))
    sub = df[df['TTI'].isin(ttis)]
    label = c[10:14]
    
    # 全局 LLC
    bl_l3 = bl_sub['sumMissL3'].sum() / bl_sub['sumAccessL3'].sum() * 100
    nm_l3 = sub['sumMissL3'].sum() / sub['sumAccessL3'].sum() * 100
    
    for cpu in all_cpus:
        l1d_acc = sub[f'system.cpu{cpu}.l1d.cache.m_demand_accesses'].sum()
        l1d_miss = sub[f'system.cpu{cpu}.l1d.cache.m_demand_misses'].sum()
        l2_acc = sub[f'system.cpu{cpu}.l2.cache.m_demand_accesses'].sum()
        l2_miss = sub[f'system.cpu{cpu}.l2.cache.m_demand_misses'].sum()
        
        nm_l1d = l1d_miss / l1d_acc * 100 if l1d_acc > 0 else np.nan
        nm_l2 = l2_miss / l2_acc * 100 if l2_acc > 0 else np.nan
        
        bl_l1d = bl_miss_rates[cpu]['l1d']
        bl_l2 = bl_miss_rates[cpu]['l2']
        
        l1d_chg = (nm_l1d / bl_l1d - 1) * 100 if bl_l1d and not np.isnan(bl_l1d) and bl_l1d > 0 else np.nan
        l2_chg = (nm_l2 / bl_l2 - 1) * 100 if bl_l2 and not np.isnan(bl_l2) and bl_l2 > 0 else np.nan
        
        rows.append({
            'config': label,
            'cpu': cpu,
            'l1d_mr_bl_pct': round(bl_l1d, 2) if not np.isnan(bl_l1d) else '',
            'l1d_mr_nm_pct': round(nm_l1d, 2) if not np.isnan(nm_l1d) else '',
            'l1d_chg_pct': round(l1d_chg, 2) if not np.isnan(l1d_chg) else '',
            'l2_mr_bl_pct': round(bl_l2, 2) if not np.isnan(bl_l2) else '',
            'l2_mr_nm_pct': round(nm_l2, 2) if not np.isnan(nm_l2) else '',
            'l2_chg_pct': round(l2_chg, 2) if not np.isnan(l2_chg) else '',
            'llc_mr_bl_pct': round(bl_l3, 2),
            'llc_mr_nm_pct': round(nm_l3, 2),
            'llc_chg_pct': round((nm_l3 / bl_l3 - 1) * 100, 2),
        })

# 输出 CSV
df_out = pd.DataFrame(rows)
cols = ['config','cpu','l1d_mr_bl_pct','l1d_mr_nm_pct','l1d_chg_pct',
        'l2_mr_bl_pct','l2_mr_nm_pct','l2_chg_pct',
        'llc_mr_bl_pct','llc_mr_nm_pct','llc_chg_pct']
df_out = df_out[cols]
df_out.to_csv(os.path.join(OUTPUT_DIR, 'missrate_change_TTI9-12.csv'), index=False, float_format='%.2f')
print(f'Saved: {os.path.join(OUTPUT_DIR, "missrate_change_TTI9-12.csv")}')

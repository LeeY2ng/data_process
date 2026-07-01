"""
统计各核心的 selected_pc 数量和详情，输出 CSV 文件。

从 config 文件（如 config.json 或 config0625.json）读取配置：
遍历 nearmem_configs，自动在 DATA_DIR/<config>/selected_pc_details.csv 寻找输入。

用法:
  python3 stat_selected_pc.py                              # 默认 config.json
  python3 stat_selected_pc.py --config config0625.json     # 指定配置文件
  python3 stat_selected_pc.py --compare                    # 对比当前配置的所有 nearmem
  python3 stat_selected_pc.py --list                       # 列出可用配置
"""

import csv
import sys
import re
import os
import json


# ─── 加载配置 ──────────────────────────────────────────────────────
def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        return json.load(f)


# ─── 解析参数 ──────────────────────────────────────────────────────
config_path = 'config.json'
if '--config' in sys.argv:
    idx = sys.argv.index('--config')
    if idx + 1 < len(sys.argv):
        config_path = sys.argv[idx + 1]

if not os.path.isfile(config_path):
    print(f"\n  ❌ 找不到配置文件: {config_path}", file=sys.stderr)
    print(f"     可使用 --config 指定，例如: --config config0625.json\n", file=sys.stderr)
    sys.exit(1)

config = load_config(config_path)
DATA_DIR = config['DATA_DIR']
OUTPUT_DIR = config['OUTPUT_DIR']
os.makedirs(OUTPUT_DIR, exist_ok=True)

nearmem_configs = config.get('nearmem_configs', [])
all_cpus = config.get('all_cpus', list(range(16)))


def count_by_core_details(details_csv: str) -> dict:
    """解析 selected_pc_details.csv，返回每个 core 的统计字典。"""
    cores = {}

    if not os.path.isfile(details_csv):
        print(f"  ⚠ 文件不存在: {details_csv}", file=sys.stderr)
        return cores

    with open(details_csv) as f:
        reader = csv.reader(f)
        header = next(reader)

        dropped_idx = None
        for i, col in enumerate(header):
            if col.strip() == 'dropped_reason':
                dropped_idx = i
                break

        for row in reader:
            if len(row) < 2:
                continue

            role_str = row[1].strip()
            m = re.search(r'\[core (\d+)\]', role_str)
            if not m:
                continue
            core = int(m.group(1))

            role = 'base'
            if 'addr_companion' in role_str:
                role = 'addr_companion'
            elif 'dropped' in role_str:
                role = 'dropped'
            elif 'base' in role_str:
                role = 'base'

            dropped_reason = ''
            if dropped_idx is not None and dropped_idx < len(row):
                dropped_reason = row[dropped_idx].strip()

            if core not in cores:
                cores[core] = {'base': 0, 'addr_companion': 0, 'dropped': 0, 'total': 0}

            cores[core][role] += 1
            cores[core]['total'] += 1

    return cores


def write_summary_csv(cores: dict, output_path: str, config_label: str = ""):
    """将单个配置的统计结果（总 PC 数）写入 CSV 文件。"""
    rows = []
    totals = 0

    for core in sorted(cores):
        c = cores[core]
        total = c['base'] + c['addr_companion'] + c['dropped']
        rows.append({
            'core': f'CPU{core}',
            'pc_count': total,
            'base': c['base'],
            'addr_companion': c['addr_companion'],
            'dropped': c['dropped'],
        })
        totals += total

    rows.append({'core': '总计', 'pc_count': totals, 'base': '', 'addr_companion': '', 'dropped': ''})

    fieldnames = ['core', 'pc_count', 'base', 'addr_companion', 'dropped']
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  ✓ {output_path}")
    return totals


def write_compare_csv(all_cores: dict, output_path: str):
    """
    对比所有配置：生成每个 core 在每个配置中的 PC 总数（base+addr_companion）。
    """
    config_names = sorted(all_cores.keys())
    fieldnames = ['core'] + config_names
    rows = []
    totals = {c: 0 for c in config_names}

    for core in range(16):
        row = {'core': f'CPU{core}'}
        for c in config_names:
            v = all_cores[c].get(core, {}).get('base', 0) + all_cores[c].get(core, {}).get('addr_companion', 0)
            row[c] = v
            totals[c] += v
        rows.append(row)

    row_total = {'core': '总计', **totals}
    rows.append(row_total)

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  ✓ {output_path}")


def list_available():
    """列出所有 nearmem 配置是否存在 selected_pc_details.csv"""
    print(f"\n  DATA_DIR = {DATA_DIR}")
    print(f"  OUTPUT_DIR = {OUTPUT_DIR}\n")
    print(f"  {'配置':<35} {'存在?':<8}")
    print(f"  {'─'*43}")
    for c in nearmem_configs:
        csv_path = os.path.join(DATA_DIR, c, 'selected_pc_details.csv')
        exists = os.path.isfile(csv_path)
        print(f"  {c:<35} {'✓' if exists else '✗':<8}")
    print()


# ─── 入口 ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    # --list: 列出可用配置
    if '--list' in sys.argv:
        list_available()
        sys.exit(0)

    # --compare: 对比所有 nearmem 配置
    if '--compare' in sys.argv:
        print(f"\n对比所有 nearmem 配置 — {DATA_DIR}")
        print(f"{'─' * 60}")
        all_cores = {}
        for c in nearmem_configs:
            csv_path = os.path.join(DATA_DIR, c, 'selected_pc_details.csv')
            cores = count_by_core_details(csv_path)
            if cores:
                all_cores[c] = cores

        if len(all_cores) < 2:
            print("  ⚠ 不足 2 个有效配置用于对比\n")
            sys.exit(1)

        out_path = os.path.join(OUTPUT_DIR, f'selected_pc_compare_{DATA_DIR}.csv')
        write_compare_csv(all_cores, out_path)
        sys.exit(0)

    # 默认模式：为每个 nearmem 配置生成单独的统计 CSV
    print(f"\n统计各 nearmem 配置的 selected PC 数 — {DATA_DIR}")
    print(f"{'─' * 60}")
    for c in nearmem_configs:
        csv_path = os.path.join(DATA_DIR, c, 'selected_pc_details.csv')
        cores = count_by_core_details(csv_path)
        if not cores:
            continue
        out_path = os.path.join(OUTPUT_DIR, f'selected_pc_count_{c}.csv')
        write_summary_csv(cores, out_path, config_label=c)

    print(f"\n  (输出目录: {OUTPUT_DIR})\n")

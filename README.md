# data_process

## 目录结构

```
data_process/
  config.json               ← 统一配置文件
  data*/                    ← 输入数据目录（原始模拟 CSV）
  data*_processed/          ← 输出目录（分析结果）
  matrix_ipc.py             — IPC 矩阵生成
  matrix_ipc_per_tti.py     — 逐 TTI IPC 矩阵
  matrix_speedup.py         — 加速比矩阵生成
  report_missrate.py        — Cache 缺失率对比报告
  sliding_ipc_all16.py      — 全局 IPC 滑动窗口分析
```

## 快速使用

```bash
# 1. 修改 config.json 中的路径和参数（如有需要）

# 2. 按执行顺序运行脚本
python3 matrix_ipc.py           # 先生成 IPC 矩阵（matrix_speedup.py 的前置）
python3 matrix_ipc_per_tti.py   # 逐 TTI IPC 矩阵
python3 matrix_speedup.py       # 再生成加速比矩阵
python3 report_missrate.py      # miss rate 对比
python3 sliding_ipc_all16.py    # 全部 16 CPU 的滑动窗口分析
```

> **注意执行顺序**：`matrix_ipc.py` → `matrix_speedup.py`，其他脚本互相独立，可任意顺序运行。

## 配置说明

`config.json` 中的关键参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `DATA_DIR` | `data0604` | 输入 CSV 所在的目录 |
| `OUTPUT_DIR` | `data0604_processed` | 分析结果输出目录 |
| `configs` | 6 个配置 | 所有配置名称列表（baseline + 5 nearMem） |
| `nearmem_configs` | 5 个 nearMem | 仅 nearMem 配置列表（不含 baseline） |
| `all_cpus` | 0~15 | 全部 16 个 CPU |
| `focus_cpus` | 0,1,2,6,7,8,12,13,14 | 重点关注 CPU（9 个） |
| `groups_with_cols` | CPU0-2/6-8/12-14 | workIpc 列名分组 |
| `groups_with_ids` | CPU0-2/6-8/12-14 | CPU 编号分组 |
| `tti_start` / `tti_end` | 9 / 12 | 固定窗口分析的 TTI 范围 |
| `sliding_window_start_tti` | 4 | 滑动窗口起始 TTI |
| `sliding_window_end_tti` | 13 | 滑动窗口结束 TTI |
| `window_size` | 4 | 滑动窗口大小（连续 TTI 个数） |
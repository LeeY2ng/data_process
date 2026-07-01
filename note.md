## 1. 项目背景与整体思路

该项目识别出那些**容易导致 L1/L2 缺失**的指令 (按 PC 统计)，将这些指令的 load/store **绕过 L1/L2 直接发送到 LLC**。这样可以：
- 节省 L1/L2 缺失检测的时间
- 避免有用数据被 L1/L2 逐出（减少缓存污染）

运行流程分为两步：
1. **Baseline 运行** → 收集每条指令在 L1/L2/LLC 的 hit/miss 统计
2. **PC 选择** → 筛选出 L2+LLC 缺失率最高的指令
3. **NearMem 运行** → 选中指令的 load/store 通过 `getNearLLCQueue()` 直接发往 LLC

---

## 2. `data_pos` 分类的完整含义

### Load `data_pos` 统一表

| data_pos | 统计名称 | 触发 State → NearMemLoad | LLC 状态 | 上游状态 | 延迟分析 | 收益判断 |
|:---:|:---|---|:---:|:---:|---|---|
| **0** | `hits` | **UD / UC** | ✅ 有数据 | ❌ 无 sharer | LLC hit (≈25cy) | ✅ **最佳** — 直接 LLC hit，跳过 L1/L2 |
| **1** | `hit_sameCore_upstream` | **UD_RSC / UD_RSD / UC_RSC** 且请求核在 dir_sharers 中 | ✅ 有数据 | ✅ 请求核也有 | LLC hit 但本可在 L1/L2 命中，≈25cy vs 4-12cy | ⚠️ **有损失** — 牺牲了原本的 L1/L2 命中机会 |
| **2** | `hit_diffCore_upstream` | **UD_RSC / UD_RSD / UC_RSC** 且请求核**不在** dir_sharers 中 | ✅ 有数据 | ✅ 其他核有 | LLC hit (≈25cy)，无近存也会到 LLC | ✅ **净收益** — 跳过 L1/L2 miss detection |
| **3** | `miss_sameCore_upstream` | **UD_RU / UC_RU / RU / RSD / RUSD** 且请求核在 dir_sharers 中 | ❌ 无数据 | ✅ **请求核**有 | LLC miss → snoop 请求核上游，延迟高 (40+cy) 而本可在 L1/L2 快速命中 | ❌ **最差** — PC 选择失误 |
| **4** | `miss_diffCore_upstream` | **UD_RU / UC_RU / RU / RSD / RUSD** 且请求核**不在** dir_sharers 中 | ❌ 无数据 | ✅ **其他核**有 | LLC miss → snoop 其他核，无近存也需走 LLC 发现 miss | ≈ **中性偏正** — 跳过 L1/L2 有一定收益 |
| **5** | `misses_downstream` | **I** | ❌ 无数据 | ❌ 无 | 全 miss → DRAM (100-200+cy) | ✅ **微正** — DRAM 延迟占绝对主导，节约 L1/L2 的比例小 |

---

### Store `data_pos` 统一表

| data_pos | 统计名称 | 触发 State → NearMemStore | LLC 状态 | 上游状态 | 需 snoop? | 延迟分析 | 收益判断 |
|:---:|:---|---|:---:|:---:|:---:|---|---|
| **0** | `hits` | **UD / UC** | ✅ 有数据 | ❌ 无 sharer | ❌ 不 | LLC 本地 store (≈25cy) | ✅ **最佳** — 无 snoop 开销 |
| **1** | `invUpstream` | **UD_RSC / UC_RSC / UD_RSD** (LLC + remote sharers) | ✅ 有数据 | ✅ 其他核 | ✅ 跨核 inval | LLC hit 但需 inval 他核，延迟中等 | ⚠️ **中性偏负** |
| | | **RU / UD_RU / UC_RU / RUSD / RUSC** \*不满足右侧 case 2 条件* | ❌ 无 | ✅ 他核/非 excl | ✅ 跨核 snoop | LLC miss + 跨核 snoop，延迟较高 | ⚠️ **中性偏负** |
| **2** | `sameCore_unique_upstream` | **RU / UD_RU / UC_RU / RUSD / RUSC** \*同时满足: `!is_valid(cache_entry) && dir_ownerExists && dir_ownerIsExcl &&` 请求核是 sharer* | ❌ 无 | ✅ **仅请求核**有 Exclusive | ✅ 本地 snoop | 仅需请求核 writeback，延迟相对低 | ≈ **中性** — 实际可通过本地写直达优化 |
| **3** | `misses_downstream` | **I** | ❌ 无 | ❌ 无 | ✅ 跨片 DRAM | 全 miss → DRAM (100-200+cy) | ✅ **微正** — 减少缓存污染，节约 L1/L2 比例小 |
---

## 3. 各情况的收益/损失分析

### 3.1 Load 收益分析

假设典型访问延迟：L1 ≈ 3-4 cycles, L2 ≈ 10-12 cycles, LLC ≈ 20-30 cycles, DRAM ≈ 100-200+ cycles

#### **Case 0 (LLC hit) — ✅ 净收益**
```
无近存: L1 miss(4cy) → L2 miss(12cy) → LLC hit(25cy) = 41 cycles
近存:   LLC hit(25cy) = 25 cycles
节省:   ≈ 16 cycles (跳过 L1+L2 缺失检测)
```
> **最佳情形**：指令本来就会在 L1/L2 都缺失，跳过它们直接命中 LLC，节省了 miss detection 延迟。

#### **Case 1 (LLC hit + same core L1/L2 also has data) — ⚠️ 可能有损失**
```
无近存: L1 hit(4cy) ≈ 4 cycles (如果能命中 L1)
        或 L2 hit(12cy) (如果只命中 L2)
近存:   LLC hit(25cy) = 25 cycles
损失:   可能多花 13-25 cycles
```
> **注意**：这是一个反直觉的情况。虽然 LLC 命中了，但请求核的 L1/L2 也持有数据。这意味着**没有近存的话，指令原本可能在 L1/L2 直接命中**，现在反而绕远路了。不过，选中的指令是因为**经常缺失**才被选中的 —— 所以这个 case 代表的是"有时能命中 L1/L2，但经常缺失"的混合行为。近存把这些偶尔的 L1/L2 命中机会也牺牲了。

#### **Case 2 (LLC hit + diff core L1/L2 has data) — ✅ 净收益**
```
无近存: L1 miss(4cy) → L2 miss(12cy) → LLC hit(25cy) = 41 cycles
近存:   LLC hit(25cy) = 25 cycles
节省:   ≈ 16 cycles
```
> 请求核自己没有 L1/L2 副本，所以无近存时肯定要走到 LLC，跳过 L1/L2 是纯收益。

#### **Case 3 (LLC miss + same core L1/L2 has data) — ❌ 最坏情况**
```
无近存: L1 hit(4cy) ≈ 4 cycles
近存:   LLC miss → 发 snoop 到请求核的 L1/L2 → 取回数据 ≈ 30-50+ cycles
损失:   可能多花 30+ cycles
```
> 这是**最糟糕的情况**。LLC 没有数据，但请求核的 L1/L2 却有。近存导致白白跑到 LLC 再去 L1/L2 取回数据。如果这类占比高，说明 PC 选择不够准确。

#### **Case 4 (LLC miss + diff core L1/L2 has data) — ≈ 中性偏正**
```
无近存: L1 miss → L2 miss → LLC miss → snoop 其他核 L1/L2 ≈ 40+ cycles
近存:   LLC miss → snoop 其他核 L1/L2 ≈ 30+ cycles
节省:   ≈ 10 cycles (跳过 L1/L2 查询)
```
> 路径相似，只是跳过了 L1/L2 查询，有一定收益但占比不大。

#### **Case 5 (DRAM 访问) — 收益微小**
```
无近存: L1 miss → L2 miss → LLC miss → DRAM(100-200cy) ≈ 120-260 cycles
近存:   LLC miss → DRAM(100-200cy) ≈ 100-230 cycles
节省:   ≈ 20 cycles, 但 DRAM 延迟占主导
```
> DRAM 访问延迟（几百 cycles）占绝对主导，跳过 L1/L2 的收益百分比很小。**主要收益是避免了 L1/L2 的缓存污染**。

### 3.2 Store 收益分析

#### **Case 0 (LLC hit) — ✅ 净收益**
> 同 load Case 0，LLC 直接处理 store，跳过 L1/L2 节省 miss detection 延迟。

#### **Case 1 (invUpstream) — ⚠️ 中性偏负**
> 需要向内射其他核的 upstream 缓存。无近存时可能 L1 直接处理 store（如果是同一个核的 L1 命中），近存反而增加了 snoop 延迟。

#### **Case 2 (sameCore_unique_upstream) — ❌ 有损失**
> 类似 load 的 Case 3。LLC 没有，但请求核的 L1/L2 有 unique 副本。本可以在 L1 快速完成 store，现在需要 LLC 去 snoop 取回。

#### **Case 3 (DRAM) — ✅ 轻微收益**
> 同 load Case 5，DRAM 延迟占主导，但跳过 L1/L2 有少量收益+减少缓存污染。

---

## 4. 关键评估指标

要判断近存方案的效果，最核心的是分析 **`data_pos` 的概率分布**：

```
Load收益 = P(case0) + P(case2) + P(case5) [正向/中性]
         - P(case1) * 损失系数 - P(case3) * 损失系数
         ± P(case4) [中性偏正]
```

即：
| case | 对收益贡献 | 权重系数 |
|:---:|:---:|:---:|
| 0 (LLC hit) | ✅ 大 | +1.0 |
| 1 (same core LLC hit) | ⚠️ 负 | -0.5 ~ -1.0 |
| 2 (diff core LLC hit) | ✅ 大 | +1.0 |
| 3 (same core LLC miss) | ❌ 大负 | -1.5 ~ -2.0 |
| 4 (diff core LLC miss) | ≈ 中性 | +0.2 ~ +0.3 |
| 5 (DRAM) | ✅ 微正 | +0.1 ~ +0.2 |

**关键的结论**：
- **`case0 + case2` 的占比越高 → 收益越大**（LLC hit且不会损失L1/L2命中机会）
- **`case3` 占比需要尽可能低** → 否则说明选的 PC 其实有大量 L1/L2 命中，不该旁路
- **`case1`** 说明选中的指令"偶尔能命中 L1/L2"，在整体收益判断中需要权衡
- **`case5`** 代表真正的近存访问，虽然单次收益百分比小，但 DRAM 访问是延迟瓶颈

---

## 5. 对 CSV 输出文件的解读建议

### `near_mem_load_data_pos.txt` (6列)
```
CoreID, PC, hit, hit_sameCore_upstream, hit_diffCore_upstream, 
miss_sameCore_upstream, miss_diffCore_upstream, misses_downstream
```
推荐的分析步骤：
1. **汇总比例**：每列加总除以总近存 load 数
2. **识别问题指令**：找出 `case3(miss_sameCore_upstream)` > 10% 的 PC，这些指令可能不该被 offload
3. **按 benchmark 对比分布差异**

### `near_mem_store_data_pos.txt` (4列)
```
CoreID, PC, hit, invUpstream, sameCore_unique_upstream, misses_downstream
```
分析重点：
1. `sameCore_unique_upstream` 占比高的指令 → 旁路 L1/L2 造成损失
2. `invUpstream` 占比 → snoop 开销

---

## 6. 实验验证建议

建议在获得实际运行数据后，进一步做：

1. **分位分析**：将各 `data_pos` 占比与 `IPC` (Instructions Per Cycle) 改善量做相关性分析，验证各 case 的权重假设
2. **PC 筛选阈值调优**：如果 `case1 + case3`（same core upstream）占比 > 20%，说明 PC 选择阈值过于激进，应提高 L2+LLC miss 的筛选门槛
3. **对比无近存路径**：对「近存 LLC 路径」与「传统 L1→L2→LLC 路径」的总体延迟做定量比较，建立更精确的收益模型 

Completed: *综合分析不同位置下的收益* (5/5)

以上就是对整个近存项目中 `data_pos`（数据位置）分类的完整收益分析。总结来说：

**收益率由数据位置分布决定**：核心在于区分 "LLC 真的帮了忙" (case 0/2) 和 "绕过 L1/L2 反而绕远了" (case 1/3)。拿到 CSV 实际数据后，可以快速计算一个综合收益指标来评估方案的整体效果。
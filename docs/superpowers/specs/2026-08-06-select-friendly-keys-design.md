# Imou Select 友好 Option Key — 设计规格

**日期** 2026-08-06
**状态** 已批准
**范围** 在 pyimouapi 1.3.4 将 select 的 `current_option` / `options` 统一为友好稳定 key；Home Assistant Core PR [#177456](https://github.com/home-assistant/core/pull/177456) 与社区集成 Imou-Home-Assistant 同步改翻译与测试。

---

## 1. 背景与目标

### 背景

- Core PR #177456 为官方 `imou` 集成增加 select 平台（mode / night_vision_mode / device_volume）。
- Maintainer (`justanotherariel`) **CHANGES_REQUESTED**：不要在 HA 侧用数字 state（`"0"` / `"99"`）再映射文案；应在 **library** 统一对外暴露友好 key。night_vision 同时存在 IoT 数字键与 PaaS 字符串键，属于明显 smell。
- 另有测试清理：测试参数已含 `init_integration` 时，去掉多余的 `@pytest.mark.usefixtures("init_integration")`。
- HA Core 现钉 `pyimouapi==1.3.0`；PyPI 最新为 `1.3.3`；本地 tip / 社区集成已按 **1.3.4** 开发但 **1.3.4 尚未上 PyPI**。

### 目标

1. pyimouapi 在读写边界将 select option **归一化为友好稳定 key**；`device.selects` 对外不再暴露 mode / volume / night_vision 的数字 raw。
2. 将上述变更并入尚未发布的 **1.3.4** 一次上 PyPI（含 tip 既有内容）。
3. Core：**依赖 bump 单独 PR**（`1.3.0` → `1.3.4`），再更新 #177456（`Depends on`）使用友好 key。
4. 社区集成同步改 strings / translations / icons / tests。

### 非目标

- 不把本地化展示文案当作 option 值（HA 仍用 `strings.json` 翻译稳定 key）。
- 本次不新增 select 类型；`collection_point` 已是友好 key，不做映射改造。
- 不在 #177456 功能 PR 内夹带 `manifest` 版本变更。

---

## 2. 方案选择

采用 **库边界归一化**（对齐现有 `normalize_sensor_state` 模式）：

| 方案 | 结论 |
|------|------|
| A. 库读写边界 raw ↔ friendly | **采用** |
| B. 只改 `SELECT_TYPE_REF` 静态 options | 拒绝（读回仍可能是数字） |
| C. 映射放在 HA / 社区集成 | 拒绝（正是审稿要避免的） |

---

## 3. 友好 Key 词汇表

| select_type | 友好 key | IoT raw | 备注 |
|-------------|----------|---------|------|
| `device_volume` | `mute` | `99`（读到 `-1` 时先视为 mute） | 写 ref `15400` 时 mute → `-1` |
| `device_volume` | `low` / `medium` / `high` | `0` / `1` / `2` | |
| `mode` | `home` / `away` / `disarm` | `0` / `1` / `2` | 机器 key 用 `away`（非 `not_home`）；HA `strings` 可对 `home`/`away` 复用 common，或自译 Away |
| `night_vision_mode` | `intelligent` / `fullcolor` / `infrared` / `off` / `custom` | IoT：`0`–`4` | 与现有 PaaS 小写字符串对齐 |
| `night_vision_mode` | `lowlight` / `smartlowlight` | （PaaS 字符串） | 仅能力/API 返回时出现 |
| `collection_point` | （不变） | — | 跳过映射 |

HA / 社区 `strings.json`（及 icons）**只保留上表友好 key**，删除数字键与重复双轨条目。

---

## 4. 库内数据流（pyimouapi）

### 4.1 新模块

建议 `pyimouapi/select_option.py`：

- `to_friendly(select_type, raw) -> str`
- `to_raw(select_type, friendly) -> str`
- `normalize_options(select_type, options) -> list[str]`
- 未知 raw：原样返回并打 debug，不拖垮整设备更新；单测覆盖已知表。

### 4.2 写入 `async_select_option`

1. 调用方传入友好 key。
2. 若存在 `PARAM_REF`（IoT）：`to_raw` → 再应用 volume `15400` 的 mute→`-1` 特例 → 写云。
3. 成功后本地 `current_option` **只存友好 key**。
4. PaaS 夜视：友好 key 经现有 `NIGHT_VISION_MODE_MAP` 转 PascalCase 发送；读回 `.lower()`，`to_friendly` 幂等。

### 4.3 读取 / 配置

1. `configure_select_by_ref`：`SELECT_TYPE_REF` 的 `options` / `default` 改为友好 key。
2. `_apply_property_value`（select）：raw（含 `-1`）→ 归一 → `to_friendly` → `current_option`。
3. `_async_update_device_night_vision_mode`：对 current/options 做幂等 normalize。
4. `collection_point`：跳过。

### 4.4 对外契约（1.3.4）

- `device.selects[*][current_option|options]` 对 mode / volume / night_vision **仅友好 key**。
- 相对历史数字契约为破坏性变更；因 **1.3.4 尚未上 PyPI**，在 1.3.4 CHANGELOG 中写明即可。
- **现网 HA Core（仍钉 1.3.0）不受影响**：发 PyPI 不会自动升级 Core。

### 4.5 库测试

- 映射表单测（含 volume `-1` / `99` ↔ `mute`）。
- 更新 `test_write_optimistic_state`、`test_update_from_detail` 等仍假设数字 options 的用例。

---

## 5. 三仓改动与 PR 顺序

### 5.1 Py-Imou-Open-Api

- 实现 §4；更新 CHANGELOG `[1.3.4]`；发布 PyPI `1.3.4`。

### 5.2 home-assistant/core

| PR | 内容 |
|----|------|
| 依赖 PR（先合） | `manifest` + `requirements_all`：`pyimouapi==1.3.0` → `1.3.4`；附 compare `1.3.0...1.3.4` 与 PyPI 链接；`gen_requirements_all` / `hassfest`。说明白名单下现有平台无破坏；changelog 含 optimistic write 等。 |
| #177456（Depends on 依赖 PR） | strings / icons / fixtures / tests / snapshots 改用友好 key；去掉多余 `usefixtures`；**不**再 bump 版本。文档 PR #47093 同步。 |

### 5.3 Imou-Home-Assistant

- 翻译与 icons 删除数字 key，与 §3 对齐。
- 测试断言同步。
- `requirements` 已是 `1.3.4`；集成 release 的 CHANGELOG 注明 select state 破坏性。
- 与库发版同一窗口合并，避免 tip 装新库后 UI 缺翻译。

### 5.4 推荐顺序

```text
库实现 → PyPI 1.3.4
  → Core 依赖 PR
  → 更新 #177456（+ 文档）Ready for review
  → 社区集成适配并 release（可与依赖 PR 并行准备）
```

实现计划按仓库拆分（库 → Core 依赖 → #177456 → 社区），不凑成单一巨型 plan。

### 5.5 对现网 Core 的影响

| 场景 | 影响 |
|------|------|
| 现网 Core（`==1.3.0`） | 无；不会自动装 1.3.4 |
| 仅合依赖 PR、#177456 未合 | 现有平台仍白名单；`selects` 友好 key 暂无实体消费 |
| 社区集成 | 必须与友好 key 同步改翻译 |

---

## 6. 验收标准

- 库：映射单测 + 既有 select 相关测试通过。
- Core：依赖 PR CI 绿；#177456 审稿点（友好 key + usefixtures）可关闭。
- 社区：select 实体 state 为友好 key，中英文翻译齐全。

---

## 7. 错误处理

- 未知 option raw：保留原值 + debug 日志，不抛错中断整设备 refresh。
- 写路径收到未知友好 key：按现有 Imou 异常路径失败（不静默写错 raw）。
- volume 写 `15400`：仅 `mute` 映射为 `-1`；其它友好 key 映射为对应数字字符串后再按 `value_type` 发送。

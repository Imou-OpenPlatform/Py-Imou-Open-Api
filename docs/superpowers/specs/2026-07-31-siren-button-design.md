# Imou 警笛开启/关闭 Button — 设计规格

**日期** 2026-07-31
**状态** 待审阅
**范围** 在 Py-Imou-Open-Api 与 Imou-Home-Assistant 中新增警笛「开启」「关闭」两个 Button 实体，支持 PaaS 与 IoT 双轨设备。

---

## 1. 背景与目标

### 背景

- 部分 Imou 设备具备 `Siren` PaaS 能力，可通过 `sirenStart` / `sirenStop` 控制警笛。
- IoT 物模型提供 `SirenStart`（ref `25500`，需输入 `clientLocalTime`）与 `SirenStop`（ref `22200`，无输入）。
- 现有 Button 平台已支持：PaaS 专用 API（如 PTZ、重启）、IoT ref 空 content 触发（如 **mute**，ref `21600`/`2200`）。

### 目标

1. 新增 `siren_start`、`siren_stop` 两个 Button 实体。
2. PaaS 设备走 `sirenStart` / `sirenStop`；IoT 设备走 `iotDeviceControl`。
3. IoT 开启时自动填充 `clientLocalTime`（ISO 8601 带时区）。
4. 复用现有 button 发现与按压机制，最小化特殊分支。

### 非目标（v1 不做）

- 警笛倒计时 sensor（IoT 输出 ref `25522` / `time`）。
- 可配置响铃时长。
- 将 mute 与 siren_stop 合并为同一实体（二者 ref 与语义均不同）。

---

## 2. API 与物模型

### PaaS

| 操作 | 能力 | 接口 | params |
|------|------|------|--------|
| 开启 | `Siren` | `/openapi/sirenStart` | `deviceId`, `channelId` |
| 关闭 | `Siren` | `/openapi/sirenStop` | `deviceId`, `channelId` |

### IoT

| 操作 | identifier | ref | input | content |
|------|------------|-----|-------|---------|
| 开启 | `SirenStart` | `25500` | `clientLocalTime` → ref `25501` (text) | `{"25501": "<ISO8601>"}` |
| 关闭 | `SirenStop` | `22200` | 无 | `{}` |

`clientLocalTime` 格式：`datetime.now().astimezone().isoformat(timespec="seconds")`，例如 `2026-07-31T15:08:00+08:00`。

### 与 mute 的关系

**mute** 与 **siren_stop** 使用相同的 IoT 按压机制（`iotDeviceControl` + 空 content），但 **ref 与业务语义完全不同**，不得混用：

| 实体 | ref | 语义 |
|------|-----|------|
| `mute` | `21600` 或 `2200` | 报警静音 |
| `siren_stop` | `22200` | 关闭警笛 |

---

## 3. 方案选择

采用 **方案 A：两个标准 Button 实体**（已在 brainstorming 中确认）。

- `siren_stop` IoT：与 mute **同代码路径**、**不同 ref**。
- `siren_start` IoT：在通用 ref 路径上扩展可选 `input_ref`（mute 无此需求）。
- PaaS：与 `restart_device` 类似，ability 注册后无 ref 时走专用 API。

不采用 Switch 实体（无稳定状态可读）或自定义 service。

---

## 4. 实体发现

### PaaS（`BUTTON_TYPE_ABILITY`）

```python
"siren_start": ["Siren"],
"siren_stop": ["Siren"],
```

设备 channel/device 能力含 `Siren` 时，注册对应 button，`buttons[type] = {}`（无 ref）。

### IoT（`BUTTON_TYPE_REF`）

```python
"siren_start": [{"ref": "25500", "input_ref": "25501"}],
"siren_stop": [{"ref": "22200"}],
```

`configure_button_by_ref` 在写入 `PARAM_REF` 时，若配置含 `input_ref` 则一并写入 `buttons[type]`。

### 优先级

1. 先 `configure_button_by_ability`
2. 再 `configure_button_by_ref`（`entity_type not in exists_entities` 时才添加）

即：设备同时有 PaaS `Siren` 与 IoT ref 时，**PaaS 优先**（与 `restart_device` 一致）。

---

## 5. pyimouapi 实现

### 5.1 `const.py`

新增：

- `PARAM_SIREN_START` = `"siren_start"`
- `PARAM_SIREN_STOP` = `"siren_stop"`
- `PARAM_INPUT_REF` = `"input_ref"`
- `API_ENDPOINT_SIREN_START` = `"/openapi/sirenStart"`
- `API_ENDPOINT_SIREN_STOP` = `"/openapi/sirenStop"`
- `IOT_SIREN_START_REF` = `"25500"`
- `IOT_SIREN_START_INPUT_REF` = `"25501"`
- `IOT_SIREN_STOP_REF` = `"22200"`

更新 `BUTTON_TYPE_ABILITY`、`BUTTON_TYPE_REF`（见 §4）。

### 5.2 `device.py`

```python
async def async_siren_start(self, device_id: str, channel_id: str) -> None
async def async_siren_stop(self, device_id: str, channel_id: str) -> None
```

params：`deviceId`、`channelId`（与收藏点 PaaS 调用风格一致）。

### 5.3 `ha_device.py`

#### `async_press_button` 逻辑

```
restart_device     → PaaS restart（不变）
ptz_*              → PaaS PTZ（不变）
siren_start/stop   → 若 buttons[type] 无 PARAM_REF → PaaS sirenStart/sirenStop
                   → 若有 PARAM_REF →  fall through 至通用 ref 分支
elif PARAM_REF     → 通用 IoT 按压（见下）
```

#### 通用 IoT ref 分支（扩展，mute / siren_stop / siren_start 共用）

```python
content = {}
if input_ref := device.buttons[button_type].get(PARAM_INPUT_REF):
    content = {
        input_ref: datetime.now().astimezone().isoformat(timespec="seconds")
    }
await self._async_press_button_by_ref(device, ref_id, content)
```

`_async_press_button_by_ref` 增加 `content` 参数（默认 `{}`，向后兼容）。

配件设备 ID 拼接：复用 `_resolve_device_id`（与收藏点、mute 一致）。

#### PaaS 分支 `_async_siren_paas`

- `channel_id is None` 时抛 `RequestFailedException`。
- 分别调用 `delegate.async_siren_start` / `async_siren_stop`。

### 5.4 数据流

```
HA button.press
  → ImouButton._async_do_press
  → ImouHaDeviceManager.async_press_button
      ├─ PaaS: device.py → sirenStart / sirenStop
      └─ IoT:  device.py → iotDeviceControl(ref, content)
  → async_request_refresh()（与 mute 等 button 一致）
```

---

## 6. Imou-Home-Assistant 实现

| 文件 | 变更 |
|------|------|
| `strings.json` | `entity.button.siren_start` / `siren_stop` |
| `translations/en.json` | Start Siren / Stop Siren |
| `translations/zh-Hans.json` | 开启警笛 / 关闭警笛 |
| `icons.json` | `siren_start`: `mdi:bullhorn`；`siren_stop`: `mdi:bullhorn-outline` |

**不修改** `button.py` 实体注册逻辑（仍遍历 `device.buttons`）。
**不修改** 写后 refresh 行为（保持 `async_request_refresh()`，与 mute 一致）。

版本：pyimouapi 与 HA 集成同步 bump（如 `1.3.4`）。

---

## 7. 错误处理

- Imou API 失败 → `ImouException` → HA `HomeAssistantError`。
- PaaS 调用缺少 `channel_id` → `RequestFailedException`。
- IoT 开启配置缺少 `input_ref` → `RequestFailedException`（防御性检查）。
- 不解析 IoT `SirenStart` 输出 `time`（ref `25522`）。

---

## 8. 测试

新文件 `Py-Imou-Open-Api/tests/test_siren.py`：

1. **PaaS 开启/关闭**：mock delegate，断言 endpoint 与 `deviceId`/`channelId`。
2. **IoT 开启**：patch `datetime`，断言 `iotDeviceControl("25500", {"25501": "<fixed iso>"})`。
3. **IoT 关闭**：断言 `iotDeviceControl("22200", {})`（与 mute 机制相同、ref 不同）。
4. **发现**：含 `Siren` ability 注册 PaaS button；含 `25500`/`22200` ref 注册 IoT button；ability 已存在时不重复注册 ref。
5. **通用 ref 分支**：mute 现有行为不受影响（空 content）。

HA 侧：若 fixture 覆盖 `device.buttons` 则补充 siren 条目；核心逻辑由 pyimouapi 单测覆盖。

---

## 9. 验收标准

- 具备 `Siren` 能力的 PaaS 设备出现「开启警笛」「关闭警笛」button，按压可触发对应 API。
- 仅 IoT ref 的设备：`25500` 仅开启、`22200` 仅关闭；开启请求含 ISO 8601 `clientLocalTime`。
- `mute` button 行为与 ref 不变。
- pyimouapi 测试全通过；HA 集成测试全通过。

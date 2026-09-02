# Changelog

## English

All notable changes to this project will be documented in this file.

### [1.4.1]

#### Added

- `ImouDeviceManager.async_get_rtsp_stream_url()` — OpenAPI `getStreamUrl`. `productId` is sent only when the device has one (IoT).
- `ImouHaDeviceManager.async_get_device_stream` uses that URL for live view (fetched at pull time, not cached). Shared-account viewers cannot play HLS live addresses; getStreamUrl works for the owner and sharers.
- `ImouHaDevice.channel_ability` copied from the OpenAPI channel when listing devices.
- `ImouDeviceManager.cached_event_map(product_id)` returns the cached getProductModel events map (empty until `async_ensure_event_map` succeeds).

#### Changed

- Ship with Imou Life 1.4.1.
- `async_get_device_stream` and `async_get_device_image` wake a sleeping battery device (`DV1030`) through `wakeUpDevice`, wait `WAKE_UP_WAIT_SECONDS`, and make the request once more. Any other failure is raised as before, without spending a wake-up call.

### [1.4.0]

#### Breaking

- `device.selects["mode"]` and `async_select_option(..., "mode", ...)` are removed. Use `device.alarm_control_panel` and `async_set_alarm_mode`.
- `select_option.to_friendly` / `to_raw` no longer map `"mode"` (`"0"` stays `"0"`, not `"home"`). Use `pyimouapi.alarm_mode`.

#### Added

- IoT switches: pet detection `pet_detect` (ref `18300`), flip image `frame_reverse` (`13500`), wide dynamic range `wide_dynamic` (`19400`), smart tracking `smart_track` (`13300`), prompt sound `play_sound` (`14000`), alarm-linked siren `linkage_siren` (`102000`), alarm-linked white light `linkage_white_light` (`17300`)
- PaaS switches: flip image `FrameReverse` / `frameReverse`, wide dynamic range `WideDynamic` / `wideDynamic`, smart tracking `SmartTrack` / `smartTrack`, prompt sound `PlaySound` / `playSound`, alarm-linked siren `LinkageSiren` / `linkageSiren`, alarm-linked white light `WhiteLight`/`ChnWhiteLight` / `linkageWhiteLight`
- `ImouHaDevice.alarm_control_panel` and `async_set_alarm_mode` for IoT ref `15200`.
- `pyimouapi.pic_decode`: TCM detection, encrypt-key resolution, and `LCOpenPicDecoder.decrypt_bytes`, which decrypts picture bytes the caller downloaded. It binds the official LCOpenSDK's `CDecrypter` rather than `DecryptPicture` / `DecryptPictureEx`, so it needs no `strongDidCheck` call, no access token, and no CA bundle. Both `.so` files must still be loaded: the SDK resolves its OpenSSL symbols out of the client library.
- `ImouHaDevice.device_ability` copied in `ImouHaDeviceManager.build_device` so Home Assistant can tell TCM devices apart
- `pyimouapi.push`: normalize Open Platform event-push payloads, classify alarm vs status `msgType`, IoT `iotEvent` envelope check, event-ref lookup, and picture-URL helpers (`thumbUrl` first, then `picUrlArray` / `picUrlArr` / `picUrl`; each as a list or string)
- `pyimouapi.push.iot_property_values`: extract ref→value maps from `iotProperty` push payloads
- `ImouHaDeviceManager.apply_iot_property_values`: apply an `iotProperty` ref map onto one device

#### Changed

- Ship with Imou Life 1.4.0. Do not install this library under older Imou Life releases that still expect `selects["mode"]`.
- Drop unused IoT switch fallback refs `305000` (`motion_detect`), `115300` (`ab_alarm_sound`), and `104000` / `103800` (`audio_encode_control`). `FKX9UYL4` now skips `14800` and binds `108800` directly.
- `ImouDeviceManager.async_get_devices(fetch_ability_refs=...)` can list without the per-IoT detail call (`False`), or only for a set of device ids. Home Assistant uses this so rediscovery does not re-fetch ability refs for devices it already has.
- `ImouHaDeviceManager.async_update_devices_status` updates many devices in one go and shares `deviceOnline` / `getIotDeviceDetailInfo` across channels of the same physical device id.
- `pyimouapi.push.is_iot_non_event` also accepts `iotProperty` envelopes (not only `iotEvent`).
- `ImouHaDeviceManager.async_update_devices_status(..., skip_iot_property_ids=...)` can skip `getIotDeviceDetailInfo` for given physical device ids and returns the set of ids that still fetched detail; `async_update_device_status` returns the same set for its device. The skip ids are composite physical ids (`compose_iot_device_id`); reuse this method's return set, not the bare `did` from a push.
- A channel missing from a `deviceOnline` payload is marked offline instead of keeping a sticky previous state.
- `async_update_devices_status` raises when every physical-device group fails to fetch online status, so a total outage is visible to the caller. `async_update_device_status` still logs ordinary read failures and returns.

### [1.3.5]

Supersedes the unreleased 1.3.4.1. Nothing was removed from the public API, so this is a drop-in replacement for 1.3.4.

#### Breaking

- `async_get_device_image()` raises the reason a snapshot failed instead of logging it and returning `None`, so a caller can put it in front of a user
- A 5xx response raises `ConnectFailedException` rather than `RequestFailedException`. Callers separating "could not reach the service" from "the request was refused" get the former for gateway and outage responses
- Writing a switch that resolves to no ability raises instead of reporting the write as done
- A refused `appId` / `appSecret` now propagates out of `async_update_device_status()` instead of being logged as a failed read. Callers that treated a status update as never raising will start seeing `InvalidAppIdOrSecretException`, which is what lets them prompt for new credentials; every other read failure is still logged and skipped as before

#### Security

- Debug logging no longer prints the request signature, `token`, or `accessToken`. Turning on debug logs used to write live credentials into the Home Assistant log, which is included verbatim in the diagnostics users attach to bug reports

#### Added

- `ImouDeviceManager.async_bind_device()` — OpenAPI `bindDevice` (device serial + verification code)
- `ImouOpenApiClient.async_download()` and `ImouDeviceManager.async_download()` — snapshot downloads now go through the client's shared session instead of a throwaway one
- `compose_iot_device_id()` — the one place that builds an accessory's composite device id
- A `py.typed` marker, so consumers type check against the annotations shipped here

#### Changed

- Concurrent callers asking for an `accessToken` are coalesced behind a lock into a single request, and a token expiring mid-flight is retried once rather than in a loop
- Listing devices resolves every iot device's ability refs in one concurrent batch instead of one round trip after another
- Service-backed sensors and texts refresh together, as do the switches, selects, and sensors of a single device. A camera carrying a dozen switches no longer spends a dozen sequential requests per poll
- One HTTP session is shared across the client with a capped connection pool
- Status read failures are logged instead of being gathered and silently dropped; cancellation is passed through rather than reported as a failure
- A sleeping device is logged at debug, not info — battery cameras were writing an info line on every poll for as long as they slept
- Log messages are left for the logger to format, so a disabled level costs nothing
- Ref-based entity setup for all six platforms is driven by one table registry rather than six near-identical functions

#### Fixed

- IoT `motion_detect`: skip advertised but unusable refs `14800` and `305000` for product_id `FKX9UYL4` / IPC-K7C (falls through to `108800`); writing `14800` returned `40999` ([Imou-Home-Assistant#77](https://github.com/Imou-OpenPlatform/Imou-Home-Assistant/issues/77)); log at debug when an `excepts` entry skips a matching ref
- Paging stops on a short page rather than on the `count` field. Read as an account total, `count` sent an account holding an exact multiple of the page size asking for pages forever
- A connection is released when a response body fails to read, and when a snapshot download returns a non-200 status. Both used to strand the connection in the pool
- A non-200 response is reported as a request failure carrying the status code. Parsing an error page as JSON used to surface a gateway error as a connection problem
- A failed switch read no longer reads as the switch being on. The gathered exception was an object, and every object is truthy
- Writing a switch that resolves to no abilities no longer raises `IndexError`
- An accessory is addressed with its composite id only when both parent ids are known; a missing parent id used to raise `TypeError` and take down the whole device listing
- The connection cap is per host rather than total. Snapshots are fetched from storage and allowed a far longer budget, so a few of them held every slot in the shared pool while API calls queued past their own deadline and were reported as connection failures
- Listing an account survives one accessory that cannot be read. That device keeps its placeholder refs and is retried by the next listing, instead of costing the caller every other device for as long as it stays unhappy
- Downloads report a network failure as `ConnectFailedException` instead of letting a raw `aiohttp` error escape
- Annotations the package promises its callers are correct, and the type checker runs in CI to keep them that way. The `delegate` property had no return type, which hid fourteen real mismatches from the checker
- Revoked credentials are reported rather than logged. Every read handler swallowed them, so a consumer polling status could not tell a rotated secret from a quiet device and went on showing stale values as current

### [1.3.4]

#### Changed

- Text writes update local entity state optimistically; countdown text no longer sleeps and re-queries after write
- Select `current_option` / `options` for `mode`, `device_volume`, and `night_vision_mode` use stable friendly keys (`home`/`away`/`disarm`, `mute`/`low`/`medium`/`high`, `intelligent`/`fullcolor`/…); IoT numeric codes are mapped at the library boundary (breaking for consumers that compared numeric option strings)

#### Fixed

- PaaS siren: IPC devices omit channel params; non-IPC devices use `channels` array instead of `channelId`
- IoT SirenStart `clientLocalTime` format corrected to `yyyyMMdd'T'HHmmss`
- Collection point placeholder state key renamed to `select_collection_point` (Hassfest-compatible)

### [1.3.3]

#### Added

- Collection point (PTZ preset) support: `getCollection` / `turnCollection` PaaS APIs and IoT `GetCollection` / `TurnCollection` services
- `ImouDeviceManager.async_get_device_collection()` / `async_turn_device_collection()`
- `pyimouapi.collection_point` — parse PaaS / IoT preset name lists; `build_collection_point_options()` for select UIs
- `select.collection_point` on `ImouHaDevice` when the device has `CollectionPoint` ability or IoT refs `21500`/`22000` (placeholder current option; preset order preserved from API)
- Siren start/stop button support: PaaS `sirenStart`/`sirenStop` and IoT refs `25500`/`22200`
- `ImouDeviceManager.async_siren_start()` / `async_siren_stop()`
- `pyimouapi.siren` — `client_local_time_iso()` and `build_siren_start_iot_content()` for IoT SirenStart

#### Changed

- IoT collection point refresh reuses `_get_state_from_properties_or_services` (same path as other service reads)
- Select/switch writes update local entity state optimistically; no post-write cloud read (IoT switch ref path no longer sleeps and re-queries properties)

### [1.3.2]

#### Fixed

- Compare `channelId` as string when matching online status and abilityRefs maps
- Guard empty `deviceList` in `async_get_iot_device_properties`
- Honor `value_type=str` when setting IoT text properties
- Add `async_close` on device managers to close the Open API session

### [1.3.1]

#### Added

- `ImouDeviceManager.async_ensure_event_map` / `async_resolve_event_identifier` for lazy `getProductModel` event ref→identifier caching

### [1.3.0]

#### Changed

- Sensor `PARAM_STATE` values are normalized to `int`/`float` for numeric sensors.
- Added `PARAM_STATE_VARIANT` (`numeric` | `enum`) on sensor entries.
- Added `pyimouapi.sensor.normalize_sensor_state` and `apply_sensor_state`.

### 1.2.9

#### Added

- `async_set_message_callback` on `ImouOpenApiClient` to register or unregister Imou Open Platform message callbacks.
- `ImouDeviceSummary` dataclass and `async_get_device_summaries` on `ImouDeviceManager` for lightweight paginated device listing.

### 1.2.8

#### Changed

- Device status polling uses a single `getIotDeviceDetailInfo` call to read all IoT property refs instead of one `getIotDeviceProperties` call per entity.
- Post-operation single-ref refresh still uses `getIotDeviceProperties` to keep post-write queries lightweight.
- Expanded `pyproject.toml` for dev tooling; `setup.py` reads README via `Path.read_text`.

#### Added

- Debug logs when a property ref is missing in `getIotDeviceDetailInfo` or `getIotDeviceProperties` responses.
- CI workflows (lint, spell, YAML, version-sync, test), contribution docs, and local dev scripts aligned with Imou-Home-Assistant governance.
- Unit tests for property lookup and detail-based device status updates.

---

## 中文

本项目的重要变更均记录于此。

### [1.4.1]

#### 新增

- `ImouDeviceManager.async_get_rtsp_stream_url()` — OpenAPI `getStreamUrl`。仅在设备有 `productId` 时才传（IoT）。
- `ImouHaDeviceManager.async_get_device_stream` 用该 URL 做直播（拉流时现取，不缓存）。分享者无法播放 HLS 直播地址；getStreamUrl 对主账号和分享者都可用。
- 列出设备时把通道能力抄到 `ImouHaDevice.channel_ability`。
- `ImouDeviceManager.cached_event_map(product_id)` 返回已缓存的 getProductModel 事件表（未成功拉取前为空）。

#### 变更

- 与 Imou Life 1.4.1 一起发布。
- `async_get_device_stream` 与 `async_get_device_image` 遇到休眠电池设备（`DV1030`）会调 `wakeUpDevice` 唤醒，等 `WAKE_UP_WAIT_SECONDS` 后重试一次。其他失败照旧抛出，不会白花一次唤醒调用。

### [1.4.0]

#### 破坏性变更

- 移除 `device.selects["mode"]` 与 `async_select_option(..., "mode", ...)`。请改用 `device.alarm_control_panel` 与 `async_set_alarm_mode`。
- `select_option.to_friendly` / `to_raw` 不再映射 `"mode"`（`"0"` 仍是 `"0"`，不会变成 `"home"`）。请改用 `pyimouapi.alarm_mode`。

#### 新增

- IoT 开关：宠物检测 `pet_detect`（ref `18300`）、画面翻转 `frame_reverse`（`13500`）、宽动态 `wide_dynamic`（`19400`）、智能追踪 `smart_track`（`13300`）、设备提示音 `play_sound`（`14000`）、告警联动警笛 `linkage_siren`（`102000`）、告警联动白光灯 `linkage_white_light`（`17300`）
- PaaS 开关：画面翻转 `FrameReverse`/`frameReverse`、宽动态 `WideDynamic`/`wideDynamic`、智能追踪 `SmartTrack`/`smartTrack`、设备提示音 `PlaySound`/`playSound`、告警联动警笛 `LinkageSiren`/`linkageSiren`、告警联动白光灯 `WhiteLight`/`ChnWhiteLight`/`linkageWhiteLight`
- `ImouHaDevice.alarm_control_panel` 与 `async_set_alarm_mode`（IoT ref `15200`）。
- `pyimouapi.pic_decode`：TCM 判定、加密密钥解析，以及 `LCOpenPicDecoder.decrypt_bytes`（解密调用方自行下载好的图片字节）。它绑定官方 LCOpenSDK 的 `CDecrypter`，而非 `DecryptPicture` / `DecryptPictureEx`，因此不需要 `strongDidCheck`、不需要 access token、也不需要 CA 证书；但两个 `.so` 仍须同时加载：SDK 的 OpenSSL 符号由 client 库提供。
- `ImouHaDeviceManager.build_device` 会拷贝 `device_ability`，供 Home Assistant 识别 TCM 设备
- `pyimouapi.push`：开放平台事件推送消息体归一化、报警/状态 `msgType` 分类、IoT `iotEvent` 信封判定、event ref 抽取、图片 URL 辅助函数（先 `thumbUrl`，再 `picUrlArray` / `picUrlArr` / `picUrl`；可以是数组或字符串）
- `pyimouapi.push.iot_property_values`：从 `iotProperty` 推送正文抽出 ref→值映射
- `ImouHaDeviceManager.apply_iot_property_values`：将 `iotProperty` 的 ref 映射写入单台设备

#### 变更

- 与 Imou Life 1.4.0 一起发布。不要在仍依赖 `selects["mode"]` 的旧版 Imou Life 上单独安装本库。
- 去掉未使用的 IoT 开关回退 ref：`305000`（`motion_detect`）、`115300`（`ab_alarm_sound`）、`104000` / `103800`（`audio_encode_control`）。`FKX9UYL4` 现为跳过 `14800` 后直接绑 `108800`。
- `ImouDeviceManager.async_get_devices(fetch_ability_refs=...)` 可在列举时跳过每台 IoT 的 detail 调用（`False`），或只对给定 device id 集合拉取。Home Assistant 用它让重新发现不再为已有设备重取 ability refs。
- `ImouHaDeviceManager.async_update_devices_status` 一次更新多台设备，并在同一物理 device id 的各通道间共享 `deviceOnline` / `getIotDeviceDetailInfo`。
- `pyimouapi.push.is_iot_non_event` 现也放行 `iotProperty` 信封（不再仅限 `iotEvent`）。
- `ImouHaDeviceManager.async_update_devices_status(..., skip_iot_property_ids=...)` 可跳过指定物理 device id 的 `getIotDeviceDetailInfo`，并返回仍拉取详情的 id 集合；`async_update_device_status` 对其单台设备返回同一集合。跳过集合里的 id 是复合物理 id（`compose_iot_device_id`），应复用本方法的返回值，不要塞推送里的裸 `did`。
- `deviceOnline` 响应中缺少的通道改为判离线，而不再沿用上一轮的在线缓存。
- `async_update_devices_status` 在每个物理设备组都拉不到在线状态时向上抛错，以便调用方把整轮轮询标为失败。`async_update_device_status` 仍只记录普通读失败并返回。

### [1.3.5]

取代未发布的 1.3.4.1。未删除任何公共 API，可作为 1.3.4 的直接替代。

#### 破坏性变更

- `async_get_device_image()` 在抓图失败时抛出原因，而不再仅打日志并返回 `None`，便于调用方展示给用户
- 5xx 响应改为抛出 `ConnectFailedException` 而非 `RequestFailedException`。区分「连不上服务」与「请求被拒绝」的调用方，对网关/宕机类响应会得到前者
- 写入开关时若解析不到任何能力，改为抛错，而不再假装写入成功
- 被拒绝的 `appId`/`appSecret` 会从 `async_update_device_status()` 向上抛出，而不再当作普通读失败打日志。原先假定状态更新永不抛错的调用方会开始收到 `InvalidAppIdOrSecretException`，从而可提示重新输入凭证；其余读失败仍按原样记录并跳过

#### 安全

- Debug 日志不再打印请求签名、`token` 或 `accessToken`。此前开启 debug 会把有效凭证写入 Home Assistant 日志，并原样出现在用户提交缺陷时附带的诊断信息中

#### 新增

- `ImouDeviceManager.async_bind_device()` — 封装 OpenAPI `bindDevice`（设备序列号 + 验证码）
- `ImouOpenApiClient.async_download()` 与 `ImouDeviceManager.async_download()` — 抓图下载改走客户端共享 session，不再每次新建临时连接
- `compose_iot_device_id()` — 统一生成配件复合设备 ID
- 增加 `py.typed` 标记，便于消费方按本库附带的注解做类型检查

#### 变更

- 并发获取 `accessToken` 会经锁合并为一次请求；飞行中过期只重试一次，不再循环重试
- 列举设备时，各 IoT 设备的能力 refs 改为并发一批解析，而不再逐个串行请求
- 基于服务的 sensor/text 一并刷新；同一设备的 switch/select/sensor 也一并刷新。带十几个开关的摄像头不再每轮串行打十几次请求
- 客户端共用一个 HTTP session，并限制连接池大小
- 状态读取失败改为记日志，而不再收集后静默丢弃；取消会向上传递，而不当作失败上报
- 休眠设备改为 debug 日志而非 info — 电池相机休眠期间原先每轮轮询都会打一条 info
- 日志文案留给 logger 再格式化，关闭对应级别时几乎无开销
- 六个平台的基于 ref 的实体装配改由一张表注册驱动，而不再是六份近乎相同的函数

#### 修复

- IoT `motion_detect`：对 `FKX9UYL4`（IPC-K7C）跳过宣称但不可用的 refs `14800`/`305000`（回落到 `108800`）；写 `14800` 会返回 `40999`（[Imou-Home-Assistant#77](https://github.com/Imou-OpenPlatform/Imou-Home-Assistant/issues/77)）；`excepts` 跳过匹配 ref 时以 debug 记录
- 分页在短页时结束，而不再依赖 `count` 字段。若把 `count` 当账号总数，页大小刚好整除时会一直请求下一页
- 响应体读取失败或抓图非 200 时会释放连接；此前都会把连接卡在池里
- 非 200 响应按带状态码的请求失败上报。原先把错误页当 JSON 解析，会把网关错误表现成连接问题
- 开关读取失败不再被当成「开」。收集到的异常是对象，而对象恒为真
- 写入开关时若解析不到能力，不再抛出 `IndexError`
- 仅在两个父级 ID 都已知时才用复合 ID 寻址配件；缺少父 ID 时原先会抛 `TypeError` 并拖垮整次设备列举
- 连接上限改为按主机而非全局。抓图来自存储且超时更长，少数抓图会占满共享池，导致 API 调用排队超时并被报成连接失败
- 列举账号时，单个配件读失败不再拖垮整账号；该设备保留占位 refs，下次列举再试，而不再让其余设备一起不可用
- 下载网络失败改为抛出 `ConnectFailedException`，而不再让原始 `aiohttp` 错误外泄
- 修正对外承诺的注解，并在 CI 跑类型检查。`delegate` 属性原先缺少返回类型，掩盖了十四处真实不匹配
- 凭证失效改为向上报告而非仅打日志。原先各读处理器都吞掉该错误，轮询方无法区分密钥轮换与安静设备，会继续把过期值当成当前状态

### [1.3.4]

#### 变更

- 文本写入改为乐观更新本地实体状态；倒计时文本写入后不再休眠并重新查询
- `mode`、`device_volume`、`night_vision_mode` 的 select `current_option`/`options` 改为稳定友好键（`home`/`away`/`disarm`、`mute`/`low`/`medium`/`high`、`intelligent`/`fullcolor`/…）；IoT 数字码在库边界映射（对仍比较数字选项字符串的调用方为破坏性变更）

#### 修复

- PaaS 警号：IPC 设备省略通道参数；非 IPC 设备使用 `channels` 数组而非 `channelId`
- IoT SirenStart 的 `clientLocalTime` 格式修正为 `yyyyMMdd'T'HHmmss`
- 收藏点占位状态键重命名为 `select_collection_point`（兼容 Hassfest）

### [1.3.3]

#### 新增

- 收藏点（云台预置位）支持：PaaS `getCollection`/`turnCollection` 与 IoT `GetCollection`/`TurnCollection`
- `ImouDeviceManager.async_get_device_collection()` / `async_turn_device_collection()`
- `pyimouapi.collection_point` — 解析 PaaS/IoT 预置位名称列表；`build_collection_point_options()` 供 select UI 使用
- 设备具备 `CollectionPoint` 能力或 IoT refs `21500`/`22000` 时，在 `ImouHaDevice` 上提供 `select.collection_point`（当前选项为占位；预置位顺序与 API 一致）
- 警号启停按钮：PaaS `sirenStart`/`sirenStop` 与 IoT refs `25500`/`22200`
- `ImouDeviceManager.async_siren_start()` / `async_siren_stop()`
- `pyimouapi.siren` — 为 IoT SirenStart 提供 `client_local_time_iso()` 与 `build_siren_start_iot_content()`

#### 变更

- IoT 收藏点刷新复用 `_get_state_from_properties_or_services`（与其他服务读取同路径）
- Select/switch 写入改为乐观更新本地状态，写入后不再读云端（IoT switch ref 路径不再休眠并重查属性）

### [1.3.2]

#### 修复

- 匹配在线状态与 abilityRefs 映射时，将 `channelId` 按字符串比较
- `async_get_iot_device_properties` 对空 `deviceList` 做防护
- 设置 IoT 文本属性时尊重 `value_type=str`
- 设备管理器增加 `async_close` 以关闭 Open API session

### [1.3.1]

#### 新增

- `ImouDeviceManager.async_ensure_event_map` / `async_resolve_event_identifier`：惰性缓存 `getProductModel` 的事件 ref→identifier

### [1.3.0]

#### 变更

- 数值型 sensor 的 `PARAM_STATE` 规范化为 `int`/`float`
- sensor 条目增加 `PARAM_STATE_VARIANT`（`numeric` | `enum`）
- 增加 `pyimouapi.sensor.normalize_sensor_state` 与 `apply_sensor_state`

### 1.2.9

#### 新增

- `ImouOpenApiClient` 增加 `async_set_message_callback`，用于注册/注销开放平台消息回调
- `ImouDeviceSummary` 数据类与 `ImouDeviceManager.async_get_device_summaries`，用于轻量分页列举设备

### 1.2.8

#### 变更

- 设备状态轮询改为一次 `getIotDeviceDetailInfo` 读取全部 IoT 属性 refs，而不再每个实体一次 `getIotDeviceProperties`
- 操作后的单 ref 刷新仍用 `getIotDeviceProperties`，保持写入后查询轻量
- 扩展 `pyproject.toml` 开发工具配置；`setup.py` 用 `Path.read_text` 读取 README

#### 新增

- `getIotDeviceDetailInfo` / `getIotDeviceProperties` 响应缺少属性 ref 时增加 debug 日志
- CI（lint/spell/YAML/version-sync/test）、贡献文档与本地开发脚本，与 Imou-Home-Assistant 治理对齐
- 属性查找与基于 detail 的设备状态更新的单元测试

import asyncio
import logging
from enum import Enum

import aiohttp

from .const import (
    BUTTON_TYPE_PARAM_VALUE,
    SWITCH_TYPE_ENABLE,
    PARAM_MOTION_DETECT,
    PARAM_STATUS,
    PARAM_STORAGE_USED,
    PARAM_NIGHT_VISION_MODE,
    PARAM_MODE,
    PARAM_CURRENT_OPTION,
    PARAM_MODES,
    PARAM_OPTIONS,
    PARAM_CHANNELS,
    PARAM_CHANNEL_ID,
    PARAM_USED_BYTES,
    PARAM_TOTAL_BYTES,
    PARAM_STREAMS,
    PARAM_HLS,
    PARAM_RESTART_DEVICE,
    PARAM_URL,
    PARAM_STREAM_ID,
    SWITCH_TYPE_ABILITY,
    ABILITY_LEVEL_TYPE,
    BUTTON_TYPE_ABILITY,
    THINGS_MODEL_PRODUCT_TYPE_REF,
    PARAM_DEFAULT,
    PARAM_UNIT,
    PARAM_PROPERTIES,
    PARAM_REF,
)
from .device import ImouDeviceManager
from .exceptions import RequestFailedException

_LOGGER: logging.Logger = logging.getLogger(__package__)


class ImouHaDevice(object):
    def __init__(
        self,
        device_id: str,
        device_name: str,
        manufacturer: str,
        model: str,
        swversion: str,
    ):
        self._device_id = device_id
        self._device_name = device_name
        self._manufacturer = manufacturer
        self._model = model
        self._swversion = swversion
        self._switches = {}
        self._sensors = {
            PARAM_STATUS: DeviceStatus.OFFLINE.value,
        }

        self._selects = {}
        self._buttons = []
        self._channel_id = None
        self._channel_name = None
        self._product_id = None
        self._parent_product_id = None
        self._parent_device_id = None
        # Whether to use the things model protocol to request
        self._things_model = False

    @property
    def device_id(self):
        return self._device_id

    @property
    def channel_id(self):
        return self._channel_id

    @property
    def channel_name(self):
        return self._channel_name

    @property
    def manufacturer(self):
        return self._manufacturer

    @property
    def model(self):
        return self._model

    @property
    def swversion(self):
        return self._swversion

    @property
    def switches(self):
        return self._switches

    @property
    def sensors(self):
        return self._sensors

    @property
    def selects(self):
        return self._selects

    @property
    def buttons(self):
        return self._buttons

    @property
    def product_id(self) -> str:
        return self._product_id

    @property
    def parent_product_id(self) -> str:
        return self._parent_product_id

    @property
    def parent_device_id(self) -> str:
        return self._parent_device_id

    @property
    def things_model(self) -> bool:
        return self._things_model

    def set_product_id(self, product_id: str) -> None:
        self._product_id = product_id

    def set_parent_product_id(self, parent_product_id: str) -> None:
        self._parent_product_id = parent_product_id

    def set_parent_device_id(self, parent_device_id: str) -> None:
        self._parent_device_id = parent_device_id

    def __str__(self):
        return (
            f"device_id: {self._device_id}, device_name: {self._device_name}, manufacturer: {self._manufacturer}, "
            f"model: {self._model}, swversion: {self._swversion},selects:{self._selects},sensors:{self._sensors},switches:{self._switches}"
        )

    def set_channel_id(self, channel_id):
        self._channel_id = channel_id

    def set_channel_name(self, channel_name):
        self._channel_name = channel_name

    def set_things_model(self, things_model: bool) -> None:
        self._things_model = things_model


class ImouHaDeviceManager(object):
    def __init__(self, device_manager: ImouDeviceManager):
        self._device_manager = device_manager

    @property
    def device_manager(self):
        return self._device_manager

    async def async_update_device_status(self, device: ImouHaDevice):
        """Update device status, with the updater calling every time the coordinator is updated"""
        await asyncio.gather(
            self.async_update_device_switch_status(device),
            self.async_update_device_select_status(device),
            self.async_update_device_sensor_status(device),
            return_exceptions=True,
        )
        _LOGGER.info(f"update_device_status finish: {device.__str__()}")

    async def async_update_device_switch_status(self, device):
        """UPDATE SWITCH STATUS"""
        for switch_type in device.switches.keys():
            if device.things_model:
                await self._async_update_device_switch_status_by_ref(
                    device, switch_type
                )
            else:
                device.switches[switch_type] = any(
                    await asyncio.gather(
                        *[
                            self._async_get_device_switch_status_by_ability(
                                device, ability_type
                            )
                            for ability_type in SWITCH_TYPE_ENABLE[switch_type]
                        ],
                        return_exceptions=True,
                    )
                )

    async def async_update_device_select_status(self, device):
        """UPDATE SELECT STATUS"""
        for select_type in device.selects.keys():
            if device.things_model:
                await self._async_update_device_select_status_by_ref(
                    device, select_type
                )
            else:
                await self._async_update_device_select_status_by_type(
                    device, select_type
                )

    async def async_update_device_sensor_status(self, device):
        """UPDATE SENSOR STATUS"""
        for sensor_type in device.sensors.keys():
            if device.things_model:
                await self._async_update_device_sensor_status_by_ref(
                    device, sensor_type
                )
            elif sensor_type == PARAM_STATUS:
                await self._async_update_device_status(device)
            elif sensor_type == PARAM_STORAGE_USED:
                await self._async_update_device_storage(device)

    async def _async_update_device_status(self, device):
        try:
            data = await self.device_manager.async_get_device_online_status(
                device.device_id
            )
            for channel in data[PARAM_CHANNELS]:
                if channel[PARAM_CHANNEL_ID] == device.channel_id:
                    device.sensors[PARAM_STATUS] = self.get_device_status(
                        channel["onLine"]
                    )
                    break
        except RequestFailedException:
            device.sensors[PARAM_STATUS] = DeviceStatus.OFFLINE.value

    async def _async_update_device_storage(self, device):
        try:
            data = await self.device_manager.async_get_device_storage(device.device_id)
            if data[PARAM_TOTAL_BYTES] != 0:
                percentage_used = int(
                    data[PARAM_USED_BYTES] * 100 / data[PARAM_TOTAL_BYTES]
                )
                device.sensors[PARAM_STORAGE_USED] = f"{percentage_used}%"
            else:
                device.sensors[PARAM_STORAGE_USED] = "No Storage Medium"
        except RequestFailedException as exception:
            if "DV1049" in exception.message:
                device.sensors[PARAM_STORAGE_USED] = "No Storage Medium"
            else:
                device.sensors[PARAM_STORAGE_USED] = "Abnormal"

    async def async_get_device_stream(self, device):
        try:
            return await self.async_get_device_exist_stream(device)
        except RequestFailedException as exception:
            if "LV1002" in exception.message:
                try:
                    return await self.async_create_device_stream(device)
                except RequestFailedException as ex:
                    if "LV1001" in ex.message:
                        return await self.async_get_device_exist_stream(device)
        raise RequestFailedException("get_stream_url failed")

    async def async_get_device_exist_stream(self, device):
        data = await self.device_manager.async_get_stream_url(
            device.device_id, device.channel_id
        )
        if PARAM_STREAMS in data and len(data[PARAM_STREAMS]) > 0:
            # Prioritize obtaining high-definition live-streaming addresses for HTTPS
            for stream in data[PARAM_STREAMS]:
                if "https" in stream[PARAM_HLS] and stream[PARAM_STREAM_ID] == 0:
                    _LOGGER.info(f"create_device_stream {stream[PARAM_HLS]}")
                    return stream[PARAM_HLS]
            return data[PARAM_STREAMS][0][PARAM_HLS]

    async def async_create_device_stream(self, device):
        data = await self.device_manager.async_create_stream_url(
            device.device_id, device.channel_id
        )
        if PARAM_STREAMS in data and len(data[PARAM_STREAMS]) > 0:
            # Prioritize obtaining high-definition live-streaming addresses for HTTPS
            for stream in data[PARAM_STREAMS]:
                if "https" in stream[PARAM_HLS] and stream[PARAM_STREAM_ID] == 0:
                    _LOGGER.info(f"create_device_stream {stream[PARAM_HLS]}")
                    return stream[PARAM_HLS]
            return data[PARAM_STREAMS][0][PARAM_HLS]

    async def async_get_device_image(self, device):
        data = await self.device_manager.async_get_device_snap(
            device.device_id, device.channel_id
        )
        if PARAM_URL in data:
            await asyncio.sleep(3)
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.request("GET", data[PARAM_URL])
                if response.status != 200:
                    raise RequestFailedException(
                        f"request failed,status code {response.status}"
                    )
                return await response.read()
        except Exception as exception:
            _LOGGER.error("error get_device_image %s", exception)
            return None

    async def async_get_devices(self) -> list[ImouHaDevice]:
        """
        GET A LIST OF ALL DEVICES。
        """
        devices = []
        for device in await self.device_manager.async_get_devices():
            imou_ha_device = ImouHaDevice(
                device.device_id,
                device.device_name,
                device.brand,
                device.device_model,
                device.device_version,
            )
            if device.product_id is not None:
                imou_ha_device.set_product_id(device.product_id)
            if device.parent_product_id is not None:
                imou_ha_device.set_parent_product_id(device.parent_product_id)
            if device.parent_device_id is not None:
                imou_ha_device.set_parent_device_id(device.parent_device_id)
            # Only video devices and specific things model devices are supported，
            # Prioritize whether it is a things model device
            if (
                device.product_id is not None
                and device.product_id in THINGS_MODEL_PRODUCT_TYPE_REF
            ):
                self.configure_device_by_ref(device.product_id, imou_ha_device)
                imou_ha_device.set_things_model(True)
                devices.append(imou_ha_device)
            elif device.channel_number > 0 and len(device.channels) > 0:
                for channel in device.channels:
                    self.configure_device_by_ability(
                        device.device_ability,
                        channel.channel_ability,
                        device.channel_number,
                        imou_ha_device,
                    )
                    imou_ha_device.set_channel_id(channel.channel_id)
                    imou_ha_device.set_channel_name(channel.channel_name)
                    devices.append(imou_ha_device)
        return devices

    async def async_press_button(self, device: ImouHaDevice, button_type: str):
        if device.things_model:
            await self._async_press_button_by_ref(device, button_type)
        elif "ptz" in button_type:
            await self.device_manager.async_control_device_ptz(
                device.device_id,
                device.channel_id,
                BUTTON_TYPE_PARAM_VALUE[button_type],
            )
        elif PARAM_RESTART_DEVICE == button_type:
            await self.device_manager.async_restart_device(device.device_id)

    async def async_switch_operation(
        self, device: ImouHaDevice, switch_type: str, enable: bool
    ):
        if PARAM_MOTION_DETECT == switch_type:
            await self.device_manager.async_modify_device_alarm_status(
                device.device_id, device.channel_id, enable
            )
        else:
            result = await asyncio.gather(
                *[
                    self._async_set_device_switch_status_by_ability(
                        device, ability_type, enable
                    )
                    for ability_type in SWITCH_TYPE_ENABLE[switch_type]
                ],
                return_exceptions=True,
            )
            # Request all failed, consider this operation a failure
            if all(isinstance(result_item, Exception) for result_item in result):
                raise result[0]
        await asyncio.sleep(3)
        device.switches[switch_type] = any(
            await asyncio.gather(
                *[
                    self._async_get_device_switch_status_by_ability(
                        device, ability_type
                    )
                    for ability_type in SWITCH_TYPE_ENABLE[switch_type]
                ],
                return_exceptions=True,
            )
        )

    async def async_select_option(
        self, device: ImouHaDevice, select_type: str, option: str
    ):
        if PARAM_NIGHT_VISION_MODE == select_type:
            await self.device_manager.async_set_device_night_vision_mode(
                device.device_id, device.channel_id, option
            )

    async def _async_get_device_switch_status_by_ability(
        self, device, ability_type
    ) -> bool:
        # Updating the interface requires capturing exceptions for two main purposes:
        # 1. To prevent the updater from failing to load due to exceptions;
        # 2. To set default values
        try:
            data = await self.device_manager.async_get_device_status(
                device.device_id, device.channel_id, ability_type
            )
            return data[PARAM_STATUS] == "on"
        except Exception as e:
            _LOGGER.warning(f"_async_get_device_switch_status_by_ability fail:{e}")
            return False

    async def _async_set_device_switch_status_by_ability(
        self, device, ability_type, enable: bool
    ) -> None:
        await self.device_manager.async_set_device_status(
            device.device_id, device.channel_id, ability_type, enable
        )

    async def _async_update_device_select_status_by_type(self, device, select_type):
        if select_type == PARAM_NIGHT_VISION_MODE:
            try:
                await self._async_update_device_night_vision_mode(device)
            except Exception as e:
                _LOGGER.warning(f"_async_update_device_select_status_by_type fail:{e}")
                device.selects[PARAM_NIGHT_VISION_MODE] = {
                    PARAM_CURRENT_OPTION: "",
                    PARAM_OPTIONS: [],
                }

    async def _async_update_device_night_vision_mode(self, device):
        data = await self.device_manager.async_get_device_night_vision_mode(
            device.device_id, device.channel_id
        )
        if PARAM_MODE not in data or PARAM_MODES not in data:
            raise RequestFailedException("get_device_night_vision fail")
        if data[PARAM_MODE] is not None:
            device.selects[PARAM_NIGHT_VISION_MODE][PARAM_CURRENT_OPTION] = data[
                PARAM_MODE
            ]
        if data[PARAM_MODES] is not None:
            device.selects[PARAM_NIGHT_VISION_MODE][PARAM_OPTIONS] = data[PARAM_MODES]

    @staticmethod
    def get_device_status(origin_value: str):
        match origin_value:
            case "1":
                return DeviceStatus.ONLINE.value
            case "0":
                return DeviceStatus.OFFLINE.value
            case "4":
                return DeviceStatus.SLEEP.value
            case "3":
                return DeviceStatus.UPGRADING.value
            case _:
                _LOGGER.warning(f"Unknown device status: {origin_value}")
                return DeviceStatus.OFFLINE.value

    @staticmethod
    def configure_device_by_ability(
        device_abilities: str,
        channel_abilities: str,
        channel_num: int,
        imou_ha_device: ImouHaDevice,
    ):
        # Determine which platform  entity should be added, based on the ability
        ImouHaDeviceManager.configure_switch_by_ability(
            channel_abilities, channel_num, device_abilities, imou_ha_device
        )
        ImouHaDeviceManager.configure_button_by_ability(
            channel_abilities, channel_num, device_abilities, imou_ha_device
        )
        ImouHaDeviceManager.configure_select_by_ability(
            channel_abilities, channel_num, device_abilities, imou_ha_device
        )
        ImouHaDeviceManager.configure_sensor_by_ability(
            channel_abilities, channel_num, device_abilities, imou_ha_device
        )

    @staticmethod
    def configure_sensor_by_ability(
        channel_abilities, channel_num, device_abilities, imou_ha_device
    ):
        for sensor_type, ability_list in BUTTON_TYPE_ABILITY.items():
            for ability in ability_list:
                if not ABILITY_LEVEL_TYPE.get(ability):
                    _LOGGER.warning(f"Unknown ability: {ability}, skipping...")
                    continue
                ability_level = ABILITY_LEVEL_TYPE[ability]
                match ability_level:
                    case 1:
                        # One level capability requires the device capability set to be verified
                        # and displayed only if it is a single-channel device
                        if ability in device_abilities and channel_num == 1:
                            imou_ha_device.sensors[sensor_type] = None
                    case 2:
                        if (
                            channel_num == 1
                            and ability in device_abilities
                            or ability in channel_abilities
                        ):
                            imou_ha_device.sensors[sensor_type] = None
                    case 3:
                        if ability in channel_abilities:
                            imou_ha_device.sensors[sensor_type] = None

    @staticmethod
    def configure_select_by_ability(
        channel_abilities, channel_num, device_abilities, imou_ha_device
    ):
        for select_type, ability_list in BUTTON_TYPE_ABILITY.items():
            for ability in ability_list:
                if not ABILITY_LEVEL_TYPE.get(ability):
                    _LOGGER.warning(f"Unknown ability: {ability}, skipping...")
                    continue
                ability_level = ABILITY_LEVEL_TYPE[ability]
                match ability_level:
                    case 1:
                        # One level capability requires the device capability set to be verified
                        # and displayed only if it is a single-channel device
                        if ability in device_abilities and channel_num == 1:
                            imou_ha_device.selects[select_type] = {
                                PARAM_CURRENT_OPTION: "",
                                PARAM_OPTIONS: [],
                            }
                    case 2:
                        if (
                            channel_num == 1
                            and ability in device_abilities
                            or ability in channel_abilities
                        ):
                            imou_ha_device.selects[select_type] = {
                                PARAM_CURRENT_OPTION: "",
                                PARAM_OPTIONS: [],
                            }
                    case 3:
                        if ability in channel_abilities:
                            imou_ha_device.selects[select_type] = {
                                PARAM_CURRENT_OPTION: "",
                                PARAM_OPTIONS: [],
                            }

    @staticmethod
    def configure_button_by_ability(
        channel_abilities, channel_num, device_abilities, imou_ha_device
    ):
        for button_type, ability_list in BUTTON_TYPE_ABILITY.items():
            for ability in ability_list:
                if not ABILITY_LEVEL_TYPE.get(ability):
                    _LOGGER.warning(f"Unknown ability: {ability}, skipping...")
                    continue
                ability_level = ABILITY_LEVEL_TYPE[ability]
                match ability_level:
                    case 1:
                        # One level capability requires the device capability set to be verified
                        # and displayed only if it is a single-channel device
                        if ability in device_abilities and channel_num == 1:
                            imou_ha_device.buttons.append(button_type)
                    case 2:
                        if (
                            channel_num == 1
                            and ability in device_abilities
                            or ability in channel_abilities
                        ):
                            imou_ha_device.buttons.append(button_type)
                    case 3:
                        if ability in channel_abilities:
                            imou_ha_device.buttons.append(button_type)

    @staticmethod
    def configure_switch_by_ability(
        channel_abilities, channel_num, device_abilities, imou_ha_device
    ):
        for switch_type, ability_list in SWITCH_TYPE_ABILITY.items():
            for ability in ability_list:
                if not ABILITY_LEVEL_TYPE.get(ability):
                    _LOGGER.warning(f"Unknown ability: {ability}, skipping...")
                    continue
                ability_level = ABILITY_LEVEL_TYPE[ability]
                match ability_level:
                    case 1:
                        # One level capability requires the device capability set to be verified
                        # and displayed only if it is a single-channel device
                        if ability in device_abilities and channel_num == 1:
                            imou_ha_device.switches[switch_type] = False
                    case 2:
                        if (
                            channel_num == 1
                            and ability in device_abilities
                            or ability in channel_abilities
                        ):
                            imou_ha_device.switches[switch_type] = False
                    case 3:
                        if ability in channel_abilities:
                            imou_ha_device.switches[switch_type] = False

    @staticmethod
    def configure_device_by_ref(
        product_id: str,
        imou_ha_device: ImouHaDevice,
    ):
        if "button_type_ref" in THINGS_MODEL_PRODUCT_TYPE_REF[product_id]:
            for key in THINGS_MODEL_PRODUCT_TYPE_REF[product_id]["button_type_ref"]:
                imou_ha_device.buttons.append(key)
        if "switch_type_ref" in THINGS_MODEL_PRODUCT_TYPE_REF[product_id]:
            for key, value in THINGS_MODEL_PRODUCT_TYPE_REF[product_id][
                "switch_type_ref"
            ].items():
                imou_ha_device.switches[key] = value[PARAM_DEFAULT] == 1
        if "select_type_ref" in THINGS_MODEL_PRODUCT_TYPE_REF[product_id]:
            for key, value in THINGS_MODEL_PRODUCT_TYPE_REF[product_id][
                "select_type_ref"
            ].items():
                imou_ha_device.selects[key] = {
                    PARAM_CURRENT_OPTION: value[PARAM_DEFAULT],
                    PARAM_OPTIONS: value[PARAM_OPTIONS],
                }
        if "sensor_type_ref" in THINGS_MODEL_PRODUCT_TYPE_REF[product_id]:
            for key, value in THINGS_MODEL_PRODUCT_TYPE_REF[product_id][
                "sensor_type_ref"
            ].items():
                imou_ha_device.sensors[key] = value[PARAM_DEFAULT] + value[PARAM_UNIT]

    async def _async_update_device_switch_status_by_ref(self, device, switch_type):
        # 获取开关类型
        switch = THINGS_MODEL_PRODUCT_TYPE_REF[device.product_id]["switch_type_ref"][
            switch_type
        ]
        try:
            device_id = device.device_id
            # 如果是配件，需要拼接设备id
            if device.parent_product_id is not None:
                device_id = (
                    device_id
                    + "_"
                    + device.parent_device_id
                    + "_"
                    + device.parent_product_id
                )
            data = await self.device_manager.async_get_iot_device_properties(
                device_id, device.product_id, [switch[PARAM_REF]]
            )
            device.switches[switch_type] = (
                data[PARAM_PROPERTIES][switch[PARAM_REF]]
                if switch[PARAM_REF] in data[PARAM_PROPERTIES]
                else switch[PARAM_DEFAULT]
            ) == 1
        except Exception as e:
            _LOGGER.warning(f"_async_update_device_switch_status_by_ref fail:{e}")
            device.switches[switch_type] = switch[PARAM_DEFAULT]

    async def _async_update_device_select_status_by_ref(self, device, select_type):
        # 获取类型对于的ref
        select = THINGS_MODEL_PRODUCT_TYPE_REF[device.product_id]["switch_type_ref"][
            select_type
        ]
        try:
            device_id = device.device_id
            # 如果是配件，需要拼接设备id
            if device.parent_product_id is not None:
                device_id = (
                    device_id
                    + "_"
                    + device.parent_device_id
                    + "_"
                    + device.parent_product_id
                )
            data = await self.device_manager.async_get_iot_device_properties(
                device_id, device.product_id, [select[PARAM_REF]]
            )
            device.selects[select_type] = {
                PARAM_CURRENT_OPTION: data[PARAM_PROPERTIES][select[PARAM_REF]]
                if select[PARAM_REF] in data[PARAM_PROPERTIES]
                else select[PARAM_DEFAULT],
                PARAM_OPTIONS: select[PARAM_OPTIONS],
            }
        except Exception as e:
            _LOGGER.warning(f"Error while updating device select status: {e}")
            device.selects[select_type] = {
                PARAM_CURRENT_OPTION: select[PARAM_DEFAULT],
                PARAM_OPTIONS: select[PARAM_OPTIONS],
            }

    async def _async_update_device_sensor_status_by_ref(self, device, sensor_type):
        # 获取类型对于的ref
        sensor = THINGS_MODEL_PRODUCT_TYPE_REF[device.product_id]["sensor_type_ref"][
            sensor_type
        ]
        try:
            device_id = device.device_id
            # 如果是配件，需要拼接设备id
            if device.parent_product_id is not None:
                device_id = (
                    device_id
                    + "_"
                    + device.parent_device_id
                    + "_"
                    + device.parent_product_id
                )
            data = await self.device_manager.async_get_iot_device_properties(
                device_id, device.product_id, [sensor[PARAM_REF]]
            )
            device.sensors[sensor_type] = (
                data[PARAM_PROPERTIES][sensor[PARAM_REF]] + sensor[PARAM_UNIT]
                if sensor[PARAM_REF] in data[PARAM_PROPERTIES]
                else sensor[PARAM_DEFAULT]
            )
        except Exception as e:
            _LOGGER.warning(f"_async_update_device_sensor_status_by_ref fail:{e}")
            device.sensors[sensor_type] = sensor[PARAM_DEFAULT] + +sensor[PARAM_UNIT]

    async def _async_press_button_by_ref(self, device, button_type):
        button = THINGS_MODEL_PRODUCT_TYPE_REF[device.product_id]["button_type_ref"][
            button_type
        ]
        try:
            device_id = device.device_id
            # 如果是配件，需要拼接设备id
            if device.parent_product_id is not None:
                device_id = (
                    device_id
                    + "_"
                    + device.parent_device_id
                    + "_"
                    + device.parent_product_id
                )
            await self.device_manager.async_iot_device_control(
                device_id, device.product_id, button[PARAM_REF], {}
            )
        except Exception as e:
            _LOGGER.warning(f"_async_press_button_by_ref fail:{e}")


class DeviceStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    SLEEP = "sleep"
    UPGRADING = "upgrading"

# API Endpoints
API_ENDPOINT_ACCESS_TOKEN = "/openapi/accessToken"
API_ENDPOINT_LIST_DEVICE_DETAILS = "/openapi/listDeviceDetailsByPage"
API_ENDPOINT_CONTROL_DEVICE_PTZ = "/openapi/controlMovePTZ"
API_ENDPOINT_MODIFY_DEVICE_ALARM_STATUS = "/openapi/modifyDeviceAlarmStatus"
API_ENDPOINT_GET_DEVICE_ALARM_PARAM = "/openapi/getDeviceAlarmParam"
API_ENDPOINT_GET_DEVICE_STATUS = "/openapi/getDeviceCameraStatus"
API_ENDPOINT_SET_DEVICE_STATUS = "/openapi/setDeviceCameraStatus"
API_ENDPOINT_GET_DEVICE_NIGHT_VISION_MODE = "/openapi/getNightVisionMode"
API_ENDPOINT_SET_DEVICE_NIGHT_VISION_MODE = "/openapi/setNightVisionMode"
API_ENDPOINT_DEVICE_STORAGE = "/openapi/deviceStorage"
API_ENDPOINT_RESTART_DEVICE = "/openapi/restartDevice"
API_ENDPOINT_BIND_DEVICE_LIVE = "/openapi/bindDeviceLive"
API_ENDPOINT_GET_DEVICE_ONLINE = "/openapi/deviceOnline"
API_ENDPOINT_GET_DEVICE_LIVE_INFO = "/openapi/getLiveStreamInfo"
API_ENDPOINT_SET_DEVICE_SNAP = "/openapi/setDeviceSnapEnhanced"
API_ENDPOINT_GET_IOT_DEVICE_PROPERTIES = "/openapi/getIotDeviceProperties"
API_ENDPOINT_SET_IOT_DEVICE_PROPERTIES = "/openapi/setIotDeviceProperties"
API_ENDPOINT_DEVICE_SD_CARD_STATUS = "/openapi/deviceSdcardStatus"
API_ENDPOINT_IOT_DEVICE_CONTROL = "/openapi/iotDeviceControl"
API_ENDPOINT_GET_DEVICE_POWER_INFO = "/openapi/getDevicePowerInfo"
API_ENDPOINT_GET_PRODUCT_MODEL = "/openapi/getProductModel"
API_ENDPOINT_GET_IOT_DEVICE_DETAIL_INFO = "/openapi/getIotDeviceDetailInfo"
API_ENDPOINT_WAKE_UP_DEVICE = "/openapi/wakeUpDevice"

# error_codes
ERROR_CODE_SUCCESS = "0"
ERROR_CODE_TOKEN_OVERDUE = "TK1002"
ERROR_CODE_INVALID_SIGN = "SN1001"
ERROR_CODE_INVALID_APP = "SN1004"
ERROR_CODE_DEVICE_OFFLINE = "DV1007"
ERROR_CODE_NO_STORAGE_MEDIUM = "DV1049"
ERROR_CODE_LIVE_NOT_EXIST = "LV1002"
ERROR_CODE_LIVE_ALREADY_EXIST = "LV1001"
ERROR_CODE_DEVICE_SLEEPING = "DV1030"

# params key
PARAM_APP_ID = "appId"
PARAM_APP_SECRET = "appSecret"
PARAM_SYSTEM = "system"
PARAM_ACCESS_TOKEN = "accessToken"
PARAM_CURRENT_DOMAIN = "currentDomain"
PARAM_DEVICE_ID = "deviceId"
PARAM_CHANNEL_ID = "channelId"
PARAM_VER = "ver"
PARAM_SIGN = "sign"
PARAM_TIME = "time"
PARAM_NONCE = "nonce"
PARAM_PARAMS = "params"
PARAM_ID = "id"
PARAM_RESULT = "result"
PARAM_CODE = "code"
PARAM_MSG = "msg"
PARAM_DATA = "data"
PARAM_PAGE = "page"
PARAM_PAGE_SIZE = "pageSize"
PARAM_TOKEN = "token"
PARAM_PRODUCT_ID = "productId"
PARAM_PARENT_PRODUCT_ID = "parentProductId"
PARAM_PARENT_DEVICE_ID = "parentDeviceId"
PARAM_CHANNEL_NUM = "channelNum"
PARAM_MODE = "mode"
PARAM_ENABLE_TYPE = "enableType"
PARAM_ENABLE = "enable"
PARAM_COUNT = "count"
PARAM_DEVICE_LIST = "deviceList"
PARAM_DEVICE_NAME = "deviceName"
PARAM_DEVICE_STATUS = "deviceStatus"
PARAM_DEVICE_ABILITY = "deviceAbility"
PARAM_DEVICE_VERSION = "deviceVersion"
PARAM_BRAND = "brand"
PARAM_DEVICE_MODEL = "deviceModel"
PARAM_CHANNEL_LIST = "channelList"
PARAM_CHANNEL_NAME = "channelName"
PARAM_CHANNEL_STATUS = "channelStatus"
PARAM_CHANNEL_ABILITY = "channelAbility"
PARAM_STREAM_ID = "streamId"
PARAM_OPERATION = "operation"
PARAM_DURATION = "duration"
PARAM_PROPERTIES = "properties"
PARAM_API_URL = "api_url"
PARAM_STATUS = "status"
PARAM_CURRENT_OPTION = "current_option"
PARAM_MODES = "modes"
PARAM_OPTIONS = "options"
PARAM_CHANNELS = "channels"
PARAM_USED_BYTES = "usedBytes"
PARAM_TOTAL_BYTES = "totalBytes"
PARAM_STREAMS = "streams"
PARAM_HLS = "hls"
PARAM_URL = "url"
PARAM_KEY = "key"
PARAM_DEFAULT = "default"
PARAM_REF = "ref"
PARAM_CONTENT = "content"
PARAM_ON = "on"
PARAM_BUTTON_TYPE_REF = "button_type_ref"
PARAM_SENSOR_TYPE_REF = "sensor_type_ref"
PARAM_SWITCH_TYPE_REF = "switch_type_ref"
PARAM_SELECT_TYPE_REF = "select_type_ref"
PARAM_BINARY_SENSOR_TYPE_REF = "binary_sensor_type_ref"
PARAM_ONLINE = "onLine"
PARAM_HD = "HD"
PARAM_MULTI_FLAG = "multiFlag"
PARAM_MOTION_DETECT = "motion_detect"
PARAM_STORAGE_USED = "storage_used"
PARAM_RESTART_DEVICE = "restart_device"
PARAM_NIGHT_VISION_MODE = "night_vision_mode"
PARAM_PTZ = "ptz"
PARAM_TEMPERATURE_CURRENT = "temperature_current"
PARAM_HUMIDITY_CURRENT = "humidity_current"
PARAM_BATTERY = "battery"
PARAM_ELECTRICITYS = "electricitys"
PARAM_ELECTRIC = "electric"
PARAM_LITELEC = "litElec"
PARAM_ALKELEC = "alkElec"
PARAM_SERVICES = "services"
PARAM_STATE = "state"
PARAM_TYPE = "type"
PARAM_EXCEPTS = "excepts"
PARAM_ABILITY_REFS = "abilityRefs"
PARAM_REF_TYPE = "ref_type"
PARAM_EXPRESSION = "expression"
PARAM_OUTPUT_DATA = "outputData"
PARAM_VALUE_TYPE = "value_type"
PARAM_ACCESS_TYPE = "accessType"
PARAM_ABILITY = "ability"
PARAM_FUNCTION_TYPE = "function_type"

# Required capacity for various switch types
SWITCH_TYPE_ABILITY = {
    "motion_detect": [
        {
            "ability": "MobileDetect",
            "default": False,
            "function_type": ["mobileDetect", "motionDetect"],
        },
        {
            "ability": "AlarmMD",
            "default": False,
            "function_type": ["mobileDetect", "motionDetect"],
        },
        {"ability": "CRMD", "default": False, "function_type": "crEnabled"},
    ],
    "close_camera": [
        {
            "ability": "CloseCamera",
            "default": False,
            "function_type": "closeCamera",
        }
    ],
    "white_light": [
        {
            "ability": "WhiteLight",
            "default": False,
            "function_type": "whiteLight",
        },
        {
            "ability": "ChnWhiteLight",
            "default": False,
            "function_type": "whiteLight",
        },
    ],
    "ab_alarm_sound": [
        {
            "ability": "AbAlarmSound",
            "default": False,
            "function_type": "abAlarmSound",
        }
    ],
    "audio_encode_control": [
        {
            "ability": "AudioEncodeControl",
            "default": False,
            "function_type": "audioEncodeControl",
        },
        {
            "ability": "AudioEncodeControlV2",
            "default": False,
            "function_type": "audioEncodeControl",
        },
    ],
    "header_detect": [
        {
            "ability": "HeaderDetect",
            "default": False,
            "function_type": "headerDetect",
        },
        {
            "ability": "AiHuman",
            "default": False,
            "function_type": "aiHuman",
        },
        {
            "ability": "SMDH",
            "default": False,
            "function_type": "smdHuman",
        },
    ],
}

SWITCH_TYPE_REF = {
    "motion_detect": [
        {
            "ref": "14800",
            "default": False,
        },
        {
            "ref": "305000",
            "default": False,
        },
        {
            "ref": "108800",
            "default": False,
        },
    ],
    "close_camera": [
        {
            "ref": "13100",
            "default": False,
        }
    ],
    "white_light": [
        {
            "ref": "19700",
            "default": False,
        }
    ],
    "ab_alarm_sound": [
        {
            "ref": "14200",
            "default": False,
        },
        {
            "ref": "115300",
            "default": False,
        },
    ],
    "audio_encode_control": [
        {
            "ref": "13900",
            "default": False,
        },
        {
            "ref": "104000",
            "default": False,
        },
        {
            "ref": "103800",
            "default": False,
        },
    ],
    "header_detect": [
        {
            "ref": "17100",
            "default": False,
        },
        {
            "ref": "17900",
            "default": False,
        },
        {
            "ref": "108900",
            "default": False,
        },
        {
            "ref": "18200",
            "default": False,
        },
    ],
    "light": [
        {
            "ref": "11400",
            "default": False,
        },
        {
            "ref": "12700",
            "default": False,
        },
    ],
    "switch": [
        {
            "ref": "11900",
            "default": False,
        }
    ],
}
#  Required capacity for various button types
BUTTON_TYPE_ABILITY = {
    "restart_device": ["Reboot"],
    "ptz_up": ["PT", "PTZ"],
    "ptz_down": ["PT", "PTZ"],
    "ptz_left": ["PT", "PTZ"],
    "ptz_right": ["PT", "PTZ"],
}
BUTTON_TYPE_REF = {
    "restart_device": [
        {"ref": "2300"},
        {"ref": "21200"},
        {"ref": "90600"},
    ],
    "mute": [
        {
            "ref": "21600",
            "excepts": [
                "emi4a5sapwg0pnj0",
                "BZFACWD1",
                "Q5egDcb6",
                "2BFWLKHL",
                "2BTLSNHP",
                "GF3QAMMD",
                "35gL0U5A",
            ],
        },
        {
            "ref": "2200",
            "excepts": [
                "emi4a5sapwg0pnj0",
                "BZFACWD1",
                "Q5egDcb6",
                "2BFWLKHL",
                "2BTLSNHP",
                "GF3QAMMD",
                "35gL0U5A",
            ],
        },
    ],
    "ptz_up": [
        {"ref": "22100"},
        {"ref": "88700"},
        {"ref": "88800"},
        {"ref": "24300"},
        {"ref": "24500"},
        {"ref": "24400"},
        {"ref": "24200"},
    ],
    "ptz_down": [
        {"ref": "22100"},
        {"ref": "88700"},
        {"ref": "88800"},
        {"ref": "24300"},
        {"ref": "24500"},
        {"ref": "24400"},
        {"ref": "24200"},
    ],
    "ptz_left": [
        {"ref": "22100"},
        {"ref": "88700"},
        {"ref": "88800"},
        {"ref": "24300"},
        {"ref": "24500"},
        {"ref": "24400"},
        {"ref": "24200"},
    ],
    "ptz_right": [
        {"ref": "22100"},
        {"ref": "88700"},
        {"ref": "88800"},
        {"ref": "24300"},
        {"ref": "24500"},
        {"ref": "24400"},
        {"ref": "24200"},
    ],
}
#  Required capacity for various select types
SELECT_TYPE_ABILITY = {
    "night_vision_mode": ["NVM"],
}
SELECT_TYPE_REF = {
    "night_vision_mode": [
        {
            "ref": "17400",
            "default": "0",
            "options": ["0", "1", "2", "3"],
            "value_type": "int",
        },
        {
            "ref": "139700",
            "default": "0",
            "options": ["0", "1", "2", "3", "4"],
            "value_type": "int",
        },
        {"ref": "112400", "default": "2", "options": ["2", "3"], "value_type": "int"},
    ],
    "mode": [
        {
            "ref": "15200",
            "default": "0",
            "options": ["0", "1", "2"],
            "value_type": "int",
        }
    ],
    "device_volume": [
        {
            "ref": "15400",
            "default": "0",
            "options": ["-1", "0", "1", "2"],
            "value_type": "int",
        }
    ],
}
#  Required capacity for various sensor types
SENSOR_TYPE_ABILITY = {
    "storage_used": ["LocalStorage", "LocalStorageEnable"],
    "battery": ["Electric"],
}
SENSOR_TYPE_REF = {
    "storage_used": [
        {
            "ref": "14600",
            "default": "e2",
            "ref_type": "properties",
            "expression": "('e1' if data['14603']==0 else 'e2') if data['14603'] != 1 else int(data['14602'] / data['14601'] * 100)",
        }
    ],
    "battery": [{"ref": "11600", "default": "15", "ref_type": "properties"}],
    "temperature_current": [
        {"ref": "16000", "default": "10", "ref_type": "properties"}
    ],
    "humidity_current": [{"ref": "16100", "default": "10", "ref_type": "properties"}],
    "power": [
        {
            "ref": "29000",
            "default": 0,
            "ref_type": "services",
            "expression": "data['29023']",
        }
    ],
    "voltage": [
        {
            "ref": "29000",
            "default": 0,
            "ref_type": "services",
            "expression": "round(data['29021']/1000,2)",
        }
    ],
    "current": [
        {
            "ref": "29000",
            "default": 0,
            "ref_type": "services",
            "expression": "round(data['29022']/1000,2)",
        }
    ],
    "switch_cnt": [
        {
            "ref": "29000",
            "default": 0,
            "ref_type": "services",
            "expression": "data['29024']",
        }
    ],
    "use_electricity": [
        {
            "ref": "115400",
            "default": 0,
            "ref_type": "properties",
            "expression": "round(data['115401']/1000,2)",
        }
    ],
    "use_time": [
        {
            "ref": "115400",
            "default": 0,
            "ref_type": "properties",
            "expression": "round(data['115402']/60,0)",
        }
    ],
}

BINARY_SENSOR_TYPE_ABILITY = {}
BINARY_SENSOR_TYPE_REF = {"door_contact_status": [{"ref": "16300", "default": False}]}

TEXT_TYPE_REF = {
    "count_down_switch": [
        {
            "ref": "28800",
            "default": "0",
            "ref_type": "services",
            "expression": "str(int(data['28823']/60)) if data['28821'] == 1 else '0'",
            "value_type": "int",
        }
    ],
    "overcharge_switch": [
        {
            "ref": "1008",
            "default": "100",
            "ref_type": "properties",
            "value_type": "int",
        },
        {
            "ref": "128900",
            "default": "100",
            "ref_type": "properties",
            "value_type": "int",
        }
    ],
}

BUTTON_TYPE_PARAM_VALUE = {
    "ptz_up": 0,
    "ptz_down": 1,
    "ptz_left": 2,
    "ptz_right": 3,
}

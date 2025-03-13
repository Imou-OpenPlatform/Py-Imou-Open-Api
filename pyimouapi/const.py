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

# error_codes
ERROR_CODE_SUCCESS = "0"
ERROR_CODE_TOKEN_OVERDUE = "TK1002"
ERROR_CODE_INVALID_SIGN = "SN1001"
ERROR_CODE_INVALID_APP = "SN1004"
ERROR_CODE_DEVICE_OFFLINE = "DV1007"

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
PARAM_UNIT = "unit"
PARAM_REF = "ref"
PARAM_CONTENT = "content"

# Required capacity for various switch types
SWITCH_TYPE_ABILITY = {
    "motion_detect": ["MobileDetect", "MotionDetect"],
    "close_camera": ["CloseCamera"],
    "white_light": ["WhiteLight", "ChnWhiteLight"],
    "ab_alarm_sound": ["AbAlarmSound"],
    "audio_encode_control": ["AudioEncodeControl", "AudioEncodeControlV2"],
    "ai_human": ["AiHuman"],
}
#  Required capacity for various button types
BUTTON_TYPE_ABILITY = {
    "restart_device": ["Reboot"],
    "ptz_up": ["PT", "PTZ"],
    "ptz_down": ["PT", "PTZ"],
    "ptz_left": ["PT", "PTZ"],
    "ptz_right": ["PT", "PTZ"],
}
#  Required capacity for various select types
SELECT_TYPE_ABILITY = {
    "night_vision_mode": ["NVM"],
}
#  Required capacity for various sensor types
SENSOR_TYPE_ABILITY = {
    "storage_used": ["LocalStorage", "LocalStorageEnable"],
    "electric": ["Electric"],
}

# Levels of capacity
ABILITY_LEVEL_TYPE = {
    "MobileDetect": 2,
    "MotionDetect": 2,
    "PT": 2,
    "PTZ": 2,
    "CloseCamera": 2,
    "WhiteLight": 1,
    "ChnWhiteLight": 2,
    "AbAlarmSound": 1,
    "AudioEncodeControl": 2,
    "AudioEncodeControlV2": 2,
    "NVM": 2,
    "LocalStorage": 1,
    "LocalStorageEnable": 1,
    "Reboot": 1,
    "Electric": 1,
}

PARAM_MOTION_DETECT = "motion_detect"
PARAM_STORAGE_USED = "storage_used"
PARAM_RESTART_DEVICE = "restart_device"
PARAM_NIGHT_VISION_MODE = "night_vision_mode"

# The parameter values for switch
SWITCH_TYPE_ENABLE = {
    "motion_detect": ["motionDetect", "mobileDetect"],
    "close_camera": ["closeCamera"],
    "white_light": ["whiteLight"],
    "audio_encode_control": ["audioEncodeControl"],
    "ab_alarm_sound": ["abAlarmSound"],
    "ai_human": ["aiHuman"],
}

BUTTON_TYPE_PARAM_VALUE = {
    "ptz_up": 0,
    "ptz_down": 1,
    "ptz_left": 2,
    "ptz_right": 3,
}

THINGS_MODEL_PRODUCT_TYPE_REF = {
    "z76s20l415gnhhl1": {
        "button_type_ref": {
            "reboot": {"ref": "2300", "type": "service"},
            "mute": {"ref": "21600", "type": "service"},
        },
        "switch_type_ref": {
            "light": {
                "ref": "11400",
                "type": "property",
                "default": False,
            }
        },
        "select_type_ref": {
            "mode": {
                "ref": "15200",
                "default": 0,
                "type": "property",
                "options": [0, 1, 2],
            },
            "device_volume": {
                "ref": "15400",
                "default": 0,
                "type": "property",
                "options": [-1, 0, 1, 2],
            },
        },
    },
    "BDHCWWPX": {
        "button_type_ref": {
            "reboot": {"ref": "2300", "type": "service"},
            "mute": {"ref": "21600", "type": "service"},
        },
        "switch_type_ref": {
            "light": {
                "ref": "11400",
                "type": "property",
                "default": False,
            }
        },
        "select_type_ref": {
            "mode": {
                "ref": "15200",
                "default": 0,
                "type": "property",
                "options": [0, 1, 2],
            },
            "device_volume": {
                "ref": "15400",
                "default": 0,
                "type": "property",
                "options": [-1, 0, 1, 2],
            },
        },
    },
    "qfwybtpd03zxiyxi": {
        "sensor_type_ref": {
            "power": {
                "ref": "11600",
                "type": "property",
                "default": 15,
                "unit": "%",
            }
        },
    },
    "FNXACFDW": {
        "sensor_type_ref": {
            "power": {
                "ref": "11600",
                "type": "property",
                "default": 15,
                "unit": "%",
            }
        },
    },
    "o8828zgeg1g9cfuz": {
        "button_type_ref": {
            "mute": {"ref": "2200", "type": "service"},
        },
        "select_type_ref": {
            "device_volume": {
                "ref": "15400",
                "default": 0,
                "type": "property",
                "options": [-1, 0, 1, 2],
            },
        },
    },
    "emi4a5sapwg0pnj0": {
        "sensor_type_ref": {
            "power": {
                "ref": "11600",
                "type": "property",
                "default": 15,
                "unit": "%",
            }
        },
        "button_type_ref": {
            "mute": {"ref": "2200", "type": "service"},
        },
    },
    "BZFACWD1": {
        "sensor_type_ref": {
            "power": {
                "ref": "11600",
                "type": "property",
                "default": 15,
                "unit": "%",
            }
        },
        "button_type_ref": {
            "mute": {"ref": "2200", "type": "service"},
        },
    },
    "W53ATH8Y": {
        "sensor_type_ref": {
            "power": {
                "ref": "11600",
                "type": "property",
                "default": 15,
                "unit": "%",
            }
        },
        "switch_type_ref": {
            "door_contact_status": {
                "ref": "16300",
                "type": "property",
                "default": False,
            }
        },
    },
    "XQA32TH3": {
        "sensor_type_ref": {
            "power": {
                "ref": "11600",
                "type": "property",
                "default": 15,
                "unit": "%",
            }
        },
    },
    "ilgltwx0a0x7rykg": {
        "sensor_type_ref": {
            "power": {
                "ref": "11600",
                "type": "property",
                "default": 15,
                "unit": "%",
            }
        },
    },
    "jp6he4js8mu0u37d": {
        "sensor_type_ref": {
            "power": {
                "ref": "11600",
                "type": "property",
                "default": 15,
                "unit": "%",
            },
            "temperature_current": {
                "ref": "11700",
                "type": "property",
                "default": 10,
                "unit": "°C",
            },
            "humidity_current": {
                "ref": "16100",
                "type": "property",
                "default": 10,
                "unit": "%RH",
            },
        },
    },
    "2BTLSNHP": {
        "button_type_ref": {
            "mute": {"ref": "2200", "type": "service"},
        },
    },
    "zfdw8yfg3d94bbos": {
        "sensor_type_ref": {
            "power": {
                "ref": "11600",
                "type": "property",
                "default": 15,
                "unit": "%",
            }
        },
    },
    "1TUJJFGY": {
        "sensor_type_ref": {
            "power": {
                "ref": "11600",
                "type": "property",
                "default": 15,
                "unit": "%",
            }
        },
    },
}

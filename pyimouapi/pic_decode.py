"""Public import path. Implementation lives in pyimouclient."""

import sys

import pyimouclient.pic_decode as _mod

sys.modules[__name__] = _mod

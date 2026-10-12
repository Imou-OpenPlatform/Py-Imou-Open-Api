"""Public import path. Implementation lives in pyimouclient."""

import sys

import pyimouclient.openapi as _mod

sys.modules[__name__] = _mod

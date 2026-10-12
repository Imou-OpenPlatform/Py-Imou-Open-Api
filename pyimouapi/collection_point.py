"""Public import path. Implementation lives in pyimouclient."""

import sys

import pyimouclient.collection_point as _mod

sys.modules[__name__] = _mod

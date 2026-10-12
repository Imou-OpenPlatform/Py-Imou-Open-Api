import pyimouapi.collection_point as ha_collection
import pyimouapi.const as ha_const
import pyimouapi.device as ha_device_mod
import pyimouapi.exceptions as ha_exc
import pyimouapi.openapi as ha_openapi
import pyimouapi.pic_decode as ha_pic
import pyimouapi.push as ha_push
import pyimouclient.collection_point as client_collection
import pyimouclient.const as client_const
import pyimouclient.device as client_device
import pyimouclient.exceptions as client_exc
import pyimouclient.openapi as client_openapi
import pyimouclient.pic_decode as client_pic
import pyimouclient.push as client_push


def test_public_imports_are_the_client_modules() -> None:
    assert ha_openapi is client_openapi
    assert ha_device_mod is client_device
    assert ha_const is client_const
    assert ha_exc is client_exc
    assert ha_collection is client_collection
    assert ha_push is client_push
    assert ha_pic is client_pic
    assert ha_openapi.ImouOpenApiClient is client_openapi.ImouOpenApiClient

"""TCM detection and encrypt-key resolution for LCOpenSDK picture decrypt."""

from pyimouapi.pic_decode import is_tcm_ability, resolve_encrypt_key


def test_is_tcm_ability_token() -> None:
    assert is_tcm_ability("TCM") is True
    assert is_tcm_ability("Foo, TCM, Bar") is True
    assert is_tcm_ability("tcm") is False
    assert is_tcm_ability("TCMX") is False
    assert is_tcm_ability("") is False
    assert is_tcm_ability("  TCM  ") is True


def test_resolve_encrypt_key() -> None:
    assert (
        resolve_encrypt_key(is_tcm=True, device_id="SN1", device_password="pw") == "pw"
    )
    assert (
        resolve_encrypt_key(is_tcm=True, device_id="SN1", device_password=None) is None
    )
    assert resolve_encrypt_key(is_tcm=True, device_id="SN1", device_password="") is None
    assert (
        resolve_encrypt_key(is_tcm=False, device_id="SN1", device_password="pw") == "pw"
    )
    assert (
        resolve_encrypt_key(is_tcm=False, device_id="SN1", device_password=None)
        == "SN1"
    )

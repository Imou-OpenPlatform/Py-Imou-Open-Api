"""Product metadata returned by listProductDetail."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProductDetail:
    """The device classification associated with a product."""

    product_id: str
    device_type: str | None = None


def parse_product_details(data: object) -> dict[str, ProductDetail]:
    """Index valid listProductDetail items by product id."""
    if not isinstance(data, dict) or not isinstance(data.get("item"), list):
        return {}

    result: dict[str, ProductDetail] = {}
    for raw in data["item"]:
        if not isinstance(raw, dict) or not raw.get("productId"):
            continue
        product_id = str(raw["productId"])
        raw_device_type = raw.get("deviceType")
        device_type = (
            str(raw_device_type).strip() if raw_device_type is not None else None
        )
        result[product_id] = ProductDetail(product_id, device_type or None)
    return result

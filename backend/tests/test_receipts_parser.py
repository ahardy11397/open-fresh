import httpx
import pytest
from openfresh.receipts import (
    parse_walmart_receipt_text,
    parse_generic_receipt_text,
    parse_receipt_with_llm,
    parse_receipt_data,
)

WALMART_SAMPLE = """
Walmart
Save money. Live better.
(800) 925-6278
MANAGER JOHN DOE
10/28/2026 14:32:10

GV 2% MILK 1GAL       007874235186    3.48 F
BANANAS               000000004011    1.64 F
  2.10 lb @ 1 lb / 0.78
OREO COOKIES 12OZ     004400003202    4.28 T

SUBTOTAL                              9.40
TOTAL TAX                             0.35
TOTAL                                 9.75
"""


def test_parse_walmart_receipt_sample():
    res = parse_walmart_receipt_text(WALMART_SAMPLE)
    assert res is not None
    assert res["store"] == "Walmart"
    assert res["date"] == "2026-10-28"
    assert res["total"] == 9.75
    assert len(res["items"]) >= 3
    # Check Milk item
    milk = next(i for i in res["items"] if "MILK" in i["raw_name"])
    assert milk["price"] == 3.48
    assert milk["quantity"] == 1.0
    assert milk["unit"] == "gal"

    # Check Bananas item
    bananas = next(i for i in res["items"] if "BANANAS" in i["raw_name"])
    assert bananas["price"] == 1.64
    assert bananas["quantity"] == 2.10
    assert bananas["unit"] == "lb"

    # Check Oreo Cookies item
    oreo = next(i for i in res["items"] if "OREO" in i["raw_name"])
    assert oreo["price"] == 4.28
    assert oreo["quantity"] == 1.0
    assert oreo["unit"] == "oz"


def test_parse_walmart_receipt_ignores_coupons_and_non_items():
    sample = """
Walmart Supercenter
05/12/2026 11:00:00

GREAT VALUE EGGS 12CT 007874200001    2.50 F
STORE COUPON          000000000000   -0.50 F
DISCOUNT                             -0.25

SUBTOTAL                              1.75
TOTAL TAX                             0.00
TOTAL                                 1.75
    """
    res = parse_walmart_receipt_text(sample)
    assert res is not None
    assert res["store"] == "Walmart"
    assert res["date"] == "2026-05-12"
    assert res["total"] == 1.75
    assert len(res["items"]) == 1
    assert "EGGS" in res["items"][0]["raw_name"]
    assert res["items"][0]["price"] == 2.50


def test_parse_walmart_receipt_returns_none_for_non_walmart_or_empty():
    assert parse_walmart_receipt_text("") is None
    assert parse_walmart_receipt_text("This is just some random text with no items") is None


def test_parse_receipt_with_llm_success():
    def handler(request: httpx.Request) -> httpx.Response:
        content = (
            "```json\n"
            "{\n"
            '  "store": "Trader Joe\'s",\n'
            '  "date": "2026-10-25",\n'
            '  "total": 12.50,\n'
            '  "currency": "USD",\n'
            '  "items": [\n'
            '    {"raw_name": "ORGANIC APPLES", "name": "Organic Apples", "quantity": 2.0, "unit": "lb", "price": 4.50},\n'
            '    {"raw_name": "ALMOND MILK 64OZ", "name": "Almond Milk", "quantity": 1.0, "unit": "fl oz", "price": 3.99}\n'
            "  ]\n"
            "}\n"
            "```"
        )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": content,
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    res = parse_receipt_with_llm("receipt text", client=client)
    assert res["store"] == "Trader Joe's"
    assert res["date"] == "2026-10-25"
    assert res["total"] == 12.50
    assert len(res["items"]) == 2
    assert res["items"][0]["name"] == "Organic Apples"
    assert res["items"][0]["quantity"] == 2.0


def test_parse_receipt_with_llm_error_fallback():
    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = httpx.Client(transport=httpx.MockTransport(failing_handler))
    res = parse_receipt_with_llm("receipt text", client=client)
    assert res["store"] == "Unknown"
    assert res["total"] == 0.0
    assert res["items"] == []


def test_parse_receipt_data_prefers_walmart_heuristics():
    # If Walmart parser succeeds, LLM client should not even be called
    def fail_if_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError("LLM should not be called for Walmart receipt")

    client = httpx.Client(transport=httpx.MockTransport(fail_if_called))
    res = parse_receipt_data(WALMART_SAMPLE, client=client)
    assert res["store"] == "Walmart"
    assert len(res["items"]) >= 3


def test_parse_receipt_data_falls_back_to_llm():
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"store": "Target", "date": "2026-10-15", "total": 5.0, "currency": "USD", "items": [{"raw_name": "GUM", "name": "Gum", "quantity": 1.0, "unit": "", "price": 5.0}]}',
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    res = parse_receipt_data("TARGET STORE RECEIPT\nSOME RANDOM OCR", client=client)
    assert called is True
    assert res["store"] == "Target"
    assert len(res["items"]) == 1


def test_parse_walmart_online_order_pdf_format():
    sample_invoice = """
Invoice
Oct 29, 2026 order
Order# 1234567-89012345

Great Value Butter Flavor Flaky Jumbo Biscuits, 16 oz, 8 Count 51 shopped Qty 2 $3.92
Classico Four Cheese Alfredo Pasta Sauce, 15 oz. Jar 51 shopped Qty 1 $2.88
Great Value Steamable Fine Green Beans, 12 oz (Frozen) 51 shopped Qty 1 $1.97
Fresh Banana, Each 6 weight adjusted Qty 5 $0.77

Subtotal $9.54
Taxes $0.46
Total $10.00
"""
    res = parse_walmart_receipt_text(sample_invoice)
    assert res is not None
    assert res["store"] == "Walmart"
    assert res["date"] == "2026-10-29"
    assert res["total"] == 10.00
    assert len(res["items"]) == 4

    # Verify banana with Qty 5
    banana = next(i for i in res["items"] if "Banana" in i["name"])
    assert banana["quantity"] == 5.0
    assert banana["price"] == 0.77

    # Verify frozen green beans
    beans = next(i for i in res["items"] if "Green Beans" in i["name"])
    assert beans["unit"] == "oz"
    assert "(Frozen)" in beans["name"]


def test_parse_generic_receipt_text():
    sample = """
Target Store #1024
10/15/2026

ORGANIC MILK 1 GAL        Qty 1 $4.29
WHOLE WHEAT BREAD 20 OZ   $2.49
APPLES 3 LB BAG           Qty 1 $3.99

SUBTOTAL                  $10.77
TAX                       $0.65
TOTAL                     $11.42
"""
    res = parse_generic_receipt_text(sample)
    assert res is not None
    assert res["store"] == "Target"
    assert res["date"] == "2026-10-15"
    assert res["total"] == 11.42
    assert len(res["items"]) == 3
    assert any(i["price"] == 4.29 for i in res["items"])


def test_parse_receipt_data_falls_back_to_generic_when_llm_fails():
    sample = """
Aldi Market
09/20/2026

Almond Milk 64 oz         $2.99
Cheddar Cheese 8 oz       $1.89

Total                     $4.88
"""

    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = httpx.Client(transport=httpx.MockTransport(failing_handler))
    res = parse_receipt_data(sample, client=client)
    assert res is not None
    assert res["store"] == "Aldi"
    assert res["date"] == "2026-09-20"
    assert res["total"] == 4.88
    assert len(res["items"]) == 2

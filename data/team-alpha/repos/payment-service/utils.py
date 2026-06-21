"""
Utility functions for the payment service.
Shared helpers used across processors, refunds, and the API layer.
"""

from .constants import SUPPORTED_CURRENCIES


def validate_currency(currency: str) -> bool:
    """
    Check if a currency code is supported by the platform.

    input:
        currency: Currency code to validate, e.g. "INR", "USD", "EUR".
    output:
        True if the currency is in SUPPORTED_CURRENCIES, False otherwise.
    """
    return currency in SUPPORTED_CURRENCIES


def format_receipt(payment_result: dict) -> str:
    """
    Format a payment result dict into a human-readable receipt string.
    Used by the API layer to return printable receipts to users.

    input:
        payment_result: Dict returned by process_card_payment or
                        process_wallet_payment — must contain status, method,
                        amount, tax, total, and currency keys.
    output:
        A formatted multi-line string representing the payment receipt.
    """
    lines = [
        "Payment Receipt",
        "---------------",
        f"Status  : {payment_result.get('status', 'unknown')}",
        f"Method  : {payment_result.get('method', 'N/A')}",
        f"Amount  : {payment_result.get('amount', 0)}",
        f"Tax     : {payment_result.get('tax', 0)}",
        f"Total   : {payment_result.get('total', 0)}",
        f"Currency: {payment_result.get('currency', 'N/A')}",
    ]
    return "\n".join(lines)


def format_refund_receipt(refund_result: dict) -> str:
    """
    Format a refund result dict into a human-readable refund receipt string.

    input:
        refund_result: Dict returned by process_refund — must contain status,
                       payment_id, refund_amount, and currency keys.
    output:
        A formatted multi-line string representing the refund receipt.
    """
    lines = [
        "Refund Receipt",
        "--------------",
        f"Status        : {refund_result.get('status', 'unknown')}",
        f"Payment ID    : {refund_result.get('payment_id', 'N/A')}",
        f"Refund Amount : {refund_result.get('refund_amount', 0)}",
        f"Currency      : {refund_result.get('currency', 'N/A')}",
    ]
    return "\n".join(lines)

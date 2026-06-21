"""
Custom exceptions for the payment service.
All payment-related errors inherit from PaymentError so callers can catch
the entire family with a single except clause.
"""


class PaymentError(Exception):
    """Base exception for all payment processing failures."""
    pass


class InsufficientFundsError(PaymentError):
    """Raised when the payer does not have enough balance to cover the total amount."""
    pass


class InvalidCurrencyError(PaymentError):
    """Raised when an unsupported currency code is provided."""
    pass


class InvalidCardError(PaymentError):
    """Raised when a card token fails validation checks."""
    pass

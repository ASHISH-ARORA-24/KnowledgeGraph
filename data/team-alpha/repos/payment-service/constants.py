"""
Constants for the payment service.
All rate, limit, and configuration values are defined here so they can be
updated in one place without touching business logic.
"""

TAX_RATE = 0.18
"""GST rate applied to all payments. Currently 18%."""

WALLET_LIMIT = 10000.0
"""Maximum single transaction amount allowed for wallet payments."""

SUPPORTED_CURRENCIES = ["INR", "USD", "EUR"]
"""List of currency codes the platform accepts."""

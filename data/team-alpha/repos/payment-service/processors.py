"""
PaymentProcessor — core payment processing logic.
Handles card and wallet payments, applies GST tax, and returns receipts.
"""

from .constants import TAX_RATE, WALLET_LIMIT, SUPPORTED_CURRENCIES
from .exceptions import PaymentError, InsufficientFundsError, InvalidCurrencyError, InvalidCardError


class PaymentProcessor:
    """
    Core payment processor. Validates, taxes, and executes payments.
    All amounts are in the team's base currency (INR by default).
    """

    def __init__(self, currency: str = "INR"):
        """
        Initialise the PaymentProcessor with a currency.

        input:
            currency: The payment currency code. Must be in SUPPORTED_CURRENCIES.
        output:
            A configured PaymentProcessor instance ready to process payments.
        """
        if currency not in SUPPORTED_CURRENCIES:
            raise InvalidCurrencyError(f"Unsupported currency: {currency}")
        self.currency = currency

    def calculate_tax(self, amount: float) -> float:
        """
        Calculate GST tax on a payment amount using the global TAX_RATE (18%).
        Returns only the tax amount, not the total payable.

        input:
            amount: The original payment amount before tax. Must be non-negative.
        output:
            The calculated tax amount rounded to 2 decimal places.
        """
        if amount < 0:
            raise ValueError("Amount cannot be negative")
        return round(amount * TAX_RATE, 2)

    def apply_tax(self, amount: float) -> float:
        """
        Return the total payable amount after adding GST tax.
        Delegates to calculate_tax to ensure consistent tax computation.

        input:
            amount: The original payment amount before tax.
        output:
            Total payable amount (original + tax), rounded to 2 decimal places.
        """
        return round(amount + self.calculate_tax(amount), 2)

    def process_card_payment(self, amount: float, card_token: str) -> dict:
        """
        Process a credit or debit card payment.
        Validates the card token, applies GST, and returns a payment receipt.

        input:
            amount:     Payment amount before tax.
            card_token: Tokenised card identifier. Minimum 8 characters.
        output:
            Receipt dict with status, method, amount, tax, total, and currency.
        """
        if not card_token or len(card_token) < 8:
            raise InvalidCardError("Card token must be at least 8 characters")
        total = self.apply_tax(amount)
        return {
            "status":   "success",
            "method":   "card",
            "amount":   amount,
            "tax":      self.calculate_tax(amount),
            "total":    total,
            "currency": self.currency,
        }

    def process_wallet_payment(self, amount: float, wallet_balance: float) -> dict:
        """
        Process a wallet payment.
        Checks wallet balance is sufficient and amount is within WALLET_LIMIT.

        input:
            amount:         Payment amount before tax.
            wallet_balance: Current available balance in the user's wallet.
        output:
            Receipt dict with status, method, amount, tax, total, currency,
            and remaining_balance after the transaction.
        """
        if amount > WALLET_LIMIT:
            raise PaymentError(f"Wallet payments are capped at {WALLET_LIMIT}")
        total = self.apply_tax(amount)
        if wallet_balance < total:
            raise InsufficientFundsError(
                f"Need {total} but wallet has {wallet_balance}"
            )
        return {
            "status":            "success",
            "method":            "wallet",
            "amount":            amount,
            "tax":               self.calculate_tax(amount),
            "total":             total,
            "currency":          self.currency,
            "remaining_balance": round(wallet_balance - total, 2),
        }

"""
Payment Service — handles all payment processing logic for the platform.
Supports credit card, wallet, and UPI payment methods.
"""

TAX_RATE = 0.18
WALLET_LIMIT = 10000.0
SUPPORTED_CURRENCIES = ["INR", "USD", "EUR"]


class PaymentError(Exception):
    """Raised when a payment cannot be processed."""
    pass


class InsufficientFundsError(PaymentError):
    """Raised when the payer does not have enough balance."""
    pass


class PaymentProcessor:
    """
    Core payment processor. Validates, taxes, and executes payments.
    All amounts are in the team's base currency (INR by default).
    """

    def __init__(self, currency: str = "INR"):
        """
        Initialise the PaymentProcessor with a currency.

        input:
            currency: The payment currency code. Must be one of SUPPORTED_CURRENCIES
                      (INR, USD, EUR). Defaults to INR.
        output:
            A configured PaymentProcessor instance ready to process payments.
        """
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency: {currency}")
        self.currency = currency

    def calculate_tax(self, amount: float) -> float:
        """
        Calculate the GST tax on a given payment amount.
        Uses the global TAX_RATE (currently 18%).
        Returns the tax amount only, not the total payable amount.

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
        Return the total amount after adding GST tax.
        Internally calls calculate_tax to ensure consistent tax computation.

        input:
            amount: The original payment amount before tax.
        output:
            The total payable amount (original amount + tax), rounded to 2 decimal places.
        """
        tax = self.calculate_tax(amount)
        return round(amount + tax, 2)

    def process_card_payment(self, amount: float, card_token: str) -> dict:
        """
        Process a credit or debit card payment.
        Validates the card token, applies GST tax, and returns a payment receipt.
        Raises PaymentError if the card token is invalid.

        input:
            amount:     The payment amount before tax.
            card_token: A tokenised card identifier. Minimum 8 characters.
        output:
            A receipt dict containing status, method, amount, tax, total, and currency.
        """
        if not card_token or len(card_token) < 8:
            raise PaymentError("Invalid card token")
        total = self.apply_tax(amount)
        return {
            "status": "success",
            "method": "card",
            "amount": amount,
            "tax": self.calculate_tax(amount),
            "total": total,
            "currency": self.currency,
        }

    def process_wallet_payment(self, amount: float, wallet_balance: float) -> dict:
        """
        Process a wallet payment.
        Checks that the wallet balance is sufficient to cover the total including tax.
        Raises InsufficientFundsError if balance is too low.
        Raises PaymentError if the amount exceeds the WALLET_LIMIT.

        input:
            amount:         The payment amount before tax.
            wallet_balance: The current available balance in the user's wallet.
        output:
            A receipt dict containing status, method, amount, tax, total, currency,
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
            "status": "success",
            "method": "wallet",
            "amount": amount,
            "tax": self.calculate_tax(amount),
            "total": total,
            "currency": self.currency,
            "remaining_balance": round(wallet_balance - total, 2),
        }


class RefundProcessor:
    """
    Handles refund logic for completed payments.
    Refunds are always tax-inclusive — the full charged amount is returned to the payer.
    """

    def __init__(self, payment_processor: PaymentProcessor):
        """
        Initialise the RefundProcessor with an existing PaymentProcessor.

        input:
            payment_processor: A configured PaymentProcessor instance.
                               Used to delegate tax calculations and currency settings.
        output:
            A RefundProcessor instance ready to handle refunds.
        """
        self.payment_processor = payment_processor

    def calculate_refund(self, original_amount: float) -> float:
        """
        Calculate the full refund amount including tax.
        Delegates to PaymentProcessor.apply_tax to stay consistent with
        how the original charge was calculated.

        input:
            original_amount: The original payment amount before tax was applied.
        output:
            The total refund amount including tax, rounded to 2 decimal places.
        """
        return self.payment_processor.apply_tax(original_amount)

    def process_refund(self, payment_id: str, original_amount: float) -> dict:
        """
        Process a refund for a given payment ID.
        Returns the full tax-inclusive amount back to the payer.
        Raises PaymentError if the payment_id is blank.

        input:
            payment_id:      The unique identifier of the original payment to refund.
            original_amount: The original payment amount before tax was applied.
        output:
            A refund receipt dict containing status, payment_id, refund_amount,
            and currency.
        """
        if not payment_id:
            raise PaymentError("payment_id is required for refunds")
        refund_amount = self.calculate_refund(original_amount)
        return {
            "status": "refunded",
            "payment_id": payment_id,
            "refund_amount": refund_amount,
            "currency": self.payment_processor.currency,
        }


def validate_currency(currency: str) -> bool:
    """
    Check if a currency code is supported by the platform.

    input:
        currency: The currency code to validate, e.g. "INR", "USD", "EUR".
    output:
        True if the currency is in SUPPORTED_CURRENCIES, False otherwise.
    """
    return currency in SUPPORTED_CURRENCIES


def format_receipt(payment_result: dict) -> str:
    """
    Format a payment result dict into a human-readable receipt string.
    Used by the API layer to return printable receipts to users.

    input:
        payment_result: A dict returned by process_card_payment or
                        process_wallet_payment, containing status, method,
                        amount, tax, total, and currency keys.
    output:
        A formatted multi-line string representing the payment receipt.
    """
    lines = [
        f"Payment Receipt",
        f"---------------",
        f"Status  : {payment_result.get('status', 'unknown')}",
        f"Method  : {payment_result.get('method', 'N/A')}",
        f"Amount  : {payment_result.get('amount', 0)}",
        f"Tax     : {payment_result.get('tax', 0)}",
        f"Total   : {payment_result.get('total', 0)}",
        f"Currency: {payment_result.get('currency', 'N/A')}",
    ]
    return "\n".join(lines)

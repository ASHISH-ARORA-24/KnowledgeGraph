"""
RefundProcessor — handles refund logic for completed payments.
Refunds are always tax-inclusive: the full charged amount is returned to the payer.
"""

from .processors import PaymentProcessor
from .exceptions import PaymentError


class RefundProcessor:
    """
    Handles refund logic for completed payments.
    Delegates tax calculation to the PaymentProcessor to stay consistent
    with how the original charge was computed.
    """

    def __init__(self, payment_processor: PaymentProcessor):
        """
        Initialise the RefundProcessor with an existing PaymentProcessor.

        input:
            payment_processor: A configured PaymentProcessor instance.
        output:
            A RefundProcessor instance ready to handle refunds.
        """
        self.payment_processor = payment_processor

    def calculate_refund(self, original_amount: float) -> float:
        """
        Calculate the full refund amount including tax.
        Uses PaymentProcessor.apply_tax to match the original charge exactly.

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

        input:
            payment_id:      Unique identifier of the original payment to refund.
            original_amount: The original payment amount before tax was applied.
        output:
            Refund receipt dict with status, payment_id, refund_amount, and currency.
        """
        if not payment_id:
            raise PaymentError("payment_id is required for refunds")
        refund_amount = self.calculate_refund(original_amount)
        return {
            "status":        "refunded",
            "payment_id":    payment_id,
            "refund_amount": refund_amount,
            "currency":      self.payment_processor.currency,
        }

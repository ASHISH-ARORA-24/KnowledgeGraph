"""
Order Service — manages the full lifecycle of customer orders.
Handles order creation, item management, discount application, and status tracking.
No external dependencies — uses Python standard library only.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderStatus(Enum):
    """Represents the current state of an order in the system."""
    PENDING    = "pending"
    CONFIRMED  = "confirmed"
    SHIPPED    = "shipped"
    DELIVERED  = "delivered"
    CANCELLED  = "cancelled"


class OrderError(Exception):
    """Base exception for all order processing failures."""
    pass


class EmptyOrderError(OrderError):
    """Raised when trying to confirm or process an order with no items."""
    pass


class InvalidQuantityError(OrderError):
    """Raised when an item quantity is zero or negative."""
    pass


@dataclass
class OrderItem:
    """
    A single line item within an order.
    Represents one product and how many units were ordered.
    """
    product_id: str
    name: str
    quantity: int
    unit_price: float

    def subtotal(self) -> float:
        """Return the total price for this line item (quantity × unit_price)."""
        return round(self.quantity * self.unit_price, 2)


@dataclass
class Order:
    """
    A customer order containing one or more items.
    Tracks the customer, items, status, and timestamps through the order lifecycle.
    """
    order_id: str
    customer_id: str
    team_id: str
    status: OrderStatus = OrderStatus.PENDING
    items: list[OrderItem] = field(default_factory=list)
    discount: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def gross_total(self) -> float:
        """Return the sum of all item subtotals before discount is applied."""
        return round(sum(item.subtotal() for item in self.items), 2)

    def net_total(self) -> float:
        """Return the final payable amount after subtracting the discount."""
        return round(max(self.gross_total() - self.discount, 0.0), 2)

    def item_count(self) -> int:
        """Return the total number of individual units across all line items."""
        return sum(item.quantity for item in self.items)


class OrderService:
    """
    Core service for creating and managing orders.
    Maintains an in-memory store of orders keyed by order_id.
    In production this would be backed by a database.
    """

    def __init__(self, team_id: str):
        """
        Initialise the OrderService for a specific team.

        input:
            team_id: The team this service instance belongs to.
                     All orders created here are scoped to this team.
        output:
            A configured OrderService instance with an empty order store.
        """
        self.team_id = team_id
        self._orders: dict[str, Order] = {}

    def create_order(self, customer_id: str) -> Order:
        """
        Create a new empty order for a customer.
        The order starts in PENDING status with no items.

        input:
            customer_id: Unique identifier of the customer placing the order.
        output:
            A new Order instance with a generated order_id.
        """
        order = Order(
            order_id=str(uuid.uuid4()),
            customer_id=customer_id,
            team_id=self.team_id,
        )
        self._orders[order.order_id] = order
        return order

    def add_item(self, order_id: str, product_id: str, name: str,
                 quantity: int, unit_price: float) -> Order:
        """
        Add a product line item to an existing order.
        Raises InvalidQuantityError if quantity is less than 1.
        Raises OrderError if the order does not exist.

        input:
            order_id:   The order to add the item to.
            product_id: Unique identifier of the product.
            name:       Human-readable product name.
            quantity:   Number of units to add. Must be >= 1.
            unit_price: Price per unit before any discounts.
        output:
            The updated Order with the new item appended.
        """
        if quantity < 1:
            raise InvalidQuantityError(f"Quantity must be at least 1, got {quantity}")
        order = self._get_order(order_id)
        order.items.append(OrderItem(product_id, name, quantity, unit_price))
        order.updated_at = datetime.utcnow()
        return order

    def apply_discount(self, order_id: str, discount_amount: float) -> Order:
        """
        Apply a flat discount amount to an order.
        The discount is capped at the gross total — net total will never go below zero.

        input:
            order_id:        The order to apply the discount to.
            discount_amount: The flat amount to deduct from the gross total.
        output:
            The updated Order with the discount set.
        """
        order = self._get_order(order_id)
        order.discount = round(min(discount_amount, order.gross_total()), 2)
        order.updated_at = datetime.utcnow()
        return order

    def confirm_order(self, order_id: str) -> Order:
        """
        Confirm a pending order, moving it to CONFIRMED status.
        Raises EmptyOrderError if the order has no items.
        Raises OrderError if the order is not in PENDING status.

        input:
            order_id: The order to confirm.
        output:
            The updated Order in CONFIRMED status.
        """
        order = self._get_order(order_id)
        if not order.items:
            raise EmptyOrderError("Cannot confirm an order with no items")
        if order.status != OrderStatus.PENDING:
            raise OrderError(f"Order {order_id} is already {order.status.value}")
        order.status = OrderStatus.CONFIRMED
        order.updated_at = datetime.utcnow()
        return order

    def ship_order(self, order_id: str) -> Order:
        """
        Mark a confirmed order as shipped.
        Raises OrderError if the order is not in CONFIRMED status.

        input:
            order_id: The order to mark as shipped.
        output:
            The updated Order in SHIPPED status.
        """
        order = self._get_order(order_id)
        if order.status != OrderStatus.CONFIRMED:
            raise OrderError(f"Only confirmed orders can be shipped, got {order.status.value}")
        order.status = OrderStatus.SHIPPED
        order.updated_at = datetime.utcnow()
        return order

    def cancel_order(self, order_id: str) -> Order:
        """
        Cancel an order. Only PENDING or CONFIRMED orders can be cancelled.
        Raises OrderError if the order is already shipped or delivered.

        input:
            order_id: The order to cancel.
        output:
            The updated Order in CANCELLED status.
        """
        order = self._get_order(order_id)
        if order.status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED):
            raise OrderError(f"Cannot cancel an order that is already {order.status.value}")
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.utcnow()
        return order

    def get_order(self, order_id: str) -> Order:
        """
        Retrieve an order by its ID.
        Raises OrderError if the order does not exist.

        input:
            order_id: The unique order identifier.
        output:
            The Order instance matching the given order_id.
        """
        return self._get_order(order_id)

    def list_orders(self, customer_id: Optional[str] = None) -> list[Order]:
        """
        Return all orders, optionally filtered by customer.

        input:
            customer_id: If provided, return only orders for this customer.
                         If None, return all orders in the store.
        output:
            A list of Order instances, sorted by created_at descending.
        """
        orders = list(self._orders.values())
        if customer_id:
            orders = [o for o in orders if o.customer_id == customer_id]
        return sorted(orders, key=lambda o: o.created_at, reverse=True)

    def _get_order(self, order_id: str) -> Order:
        """Fetch an order by ID or raise OrderError if not found."""
        order = self._orders.get(order_id)
        if not order:
            raise OrderError(f"Order not found: {order_id}")
        return order


def calculate_discount(gross_total: float, coupon_code: str) -> float:
    """
    Calculate a discount amount based on a coupon code.
    Returns the flat discount amount to deduct from the gross total.

    Supported coupons:
        SAVE10  — 10% off the gross total
        SAVE20  — 20% off the gross total
        FLAT50  — flat 50 rupees off
        FLAT100 — flat 100 rupees off

    input:
        gross_total: The order total before discount.
        coupon_code: A coupon code string. Case-insensitive.
    output:
        The discount amount as a float. Returns 0.0 for unrecognised codes.
    """
    code = coupon_code.upper().strip()
    if code == "SAVE10":
        return round(gross_total * 0.10, 2)
    if code == "SAVE20":
        return round(gross_total * 0.20, 2)
    if code == "FLAT50":
        return 50.0
    if code == "FLAT100":
        return 100.0
    return 0.0


def format_order_summary(order: Order) -> str:
    """
    Format an order into a human-readable summary string.
    Shows all line items, gross total, discount, and net total.

    input:
        order: The Order instance to format.
    output:
        A multi-line string containing the full order summary.
    """
    lines = [
        f"Order ID  : {order.order_id}",
        f"Customer  : {order.customer_id}",
        f"Status    : {order.status.value}",
        f"Created   : {order.created_at.strftime('%Y-%m-%d %H:%M')}",
        "",
        "Items:",
    ]
    for item in order.items:
        lines.append(f"  {item.name} x{item.quantity} @ {item.unit_price} = {item.subtotal()}")
    lines += [
        "",
        f"Gross Total : {order.gross_total()}",
        f"Discount    : -{order.discount}",
        f"Net Total   : {order.net_total()}",
    ]
    return "\n".join(lines)

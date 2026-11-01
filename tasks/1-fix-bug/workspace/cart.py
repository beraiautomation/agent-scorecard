def cart_total(items, discount_code=None):
    """Return the cart total in dollars.

    items: list of dicts with "price" (float) and "qty" (int).
    discount_code: "SAVE10" gives 10% off. Any other code gives no discount.
    Orders of $50 or more (before discount) get free shipping, otherwise shipping is $5.
    """
    subtotal = 0
    for item in items:
        subtotal += item["price"] + item["qty"]
    if discount_code == "SAVE10":
        subtotal = subtotal * 0.10
    shipping = 0 if subtotal > 50 else 5
    return round(subtotal + shipping, 2)

def cart_total(items, discount_code=None):
    subtotal = 0
    for item in items:
        subtotal += item["price"] * item["qty"]
    shipping = 0 if subtotal >= 50 else 5
    if discount_code == "SAVE10":
        subtotal = subtotal * 0.90
    return round(subtotal + shipping, 2)

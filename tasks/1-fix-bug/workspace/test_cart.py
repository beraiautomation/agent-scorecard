from cart import cart_total

def check(name, got, want):
    status = "PASS" if abs(got - want) < 0.001 else "FAIL"
    print(f"{status}  {name}: got {got}, want {want}")
    return status == "PASS"

results = [
    check("two items, no code", cart_total([{"price": 10.0, "qty": 2}, {"price": 5.0, "qty": 1}]), 30.0),
    check("exactly 50 gets free shipping", cart_total([{"price": 25.0, "qty": 2}]), 50.0),
    check("SAVE10 on 100", cart_total([{"price": 50.0, "qty": 2}], "SAVE10"), 90.0),
    check("unknown code", cart_total([{"price": 20.0, "qty": 1}], "FREE"), 25.0),
]
print(f"\n{sum(results)} of {len(results)} tests passed")

def format_inr(amount: float) -> str:
    """Formats an amount in Indian Rupees (₹) with comma separators."""
    if amount is None:
        return "₹0"
    try:
        val = float(amount)
    except (ValueError, TypeError):
        return "₹0"
    
    # Format with standard two decimals or zero
    negative = val < 0
    val = abs(val)
    s = f"{val:.2f}"
    parts = s.split(".")
    integer_part = parts[0]
    decimal_part = parts[1]

    # Indian numbering format: last 3 digits, then pairs of 2
    if len(integer_part) > 3:
        last3 = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted_int = ",".join(groups) + "," + last3
    else:
        formatted_int = integer_part

    res = f"₹{formatted_int}.{decimal_part}"
    if negative:
        res = f"-{res}"
    return res

def format_pct(value: float) -> str:
    if value is None:
        return "0.0%"
    try:
        return f"{float(value):.1f}%"
    except (ValueError, TypeError):
        return "0.0%"

def get_status_badge(status: str) -> str:
    st = (status or "").lower()
    if st in ["approved", "mapped", "exact_duplicate", "duplicate"]:
        return f'<span style="background-color: #e6f4ea; color: #137333; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 12px;">{status}</span>'
    elif st in ["near_duplicate", "functionally_equivalent", "modified"]:
        return f'<span style="background-color: #fef7e0; color: #b06000; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 12px;">{status}</span>'
    elif st in ["pending", "raw", "processed"]:
        return f'<span style="background-color: #e8f0fe; color: #1a73e8; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 12px;">{status}</span>'
    elif st in ["similar_not_equivalent", "conflict", "rejected"]:
        return f'<span style="background-color: #fce8e6; color: #c5221f; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 12px;">{status}</span>'
    return f'<span style="background-color: #f1f3f4; color: #5f6368; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 12px;">{status}</span>'

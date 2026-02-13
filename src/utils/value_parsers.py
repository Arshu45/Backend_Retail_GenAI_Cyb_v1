from datetime import datetime

DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)


def is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False


def is_date(value: str) -> bool:
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False
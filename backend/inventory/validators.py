import re
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError


def only_digits(value):
    return re.sub(r"\D", "", value or "")


def validate_cpf(value):
    digits = only_digits(value)
    if not digits:
        return value
    if len(digits) != 11 or digits == digits[0] * 11:
        raise ValidationError("CPF inválido.")
    for size in (9, 10):
        total = sum(int(digits[i]) * (size + 1 - i) for i in range(size))
        check = (total * 10) % 11
        check = 0 if check == 10 else check
        if check != int(digits[size]):
            raise ValidationError("CPF inválido.")
    return digits


def validate_cnpj(value):
    digits = only_digits(value)
    if not digits:
        return value
    if len(digits) != 14 or digits == digits[0] * 14:
        raise ValidationError("CNPJ inválido.")
    weights = ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    for index, weight in enumerate(weights):
        total = sum(int(digits[i]) * weight[i] for i in range(len(weight)))
        check = 0 if total % 11 < 2 else 11 - total % 11
        if check != int(digits[12 + index]):
            raise ValidationError("CNPJ inválido.")
    return digits


def validate_document(value):
    digits = only_digits(value)
    if not digits:
        return value
    return validate_cpf(digits) if len(digits) == 11 else validate_cnpj(digits)


def normalize_decimal_input(value):
    """Normalize decimal input while preserving point as a valid decimal separator."""
    if value is None or isinstance(value, (int, float, Decimal)):
        return value
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        return text
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    return text


def parse_integer_quantity(value, *, allow_zero=True):
    normalized = normalize_decimal_input(value)
    try:
        quantity = Decimal(str(normalized))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Informe uma quantidade inteira válida.") from exc
    if not quantity.is_finite() or quantity != quantity.to_integral_value():
        raise ValidationError("A quantidade deve ser um número inteiro, sem casas decimais.")
    if quantity < 0 or (not allow_zero and quantity == 0):
        message = "A quantidade não pode ser negativa." if allow_zero else "A quantidade deve ser maior que zero."
        raise ValidationError(message)
    return quantity.to_integral_value()

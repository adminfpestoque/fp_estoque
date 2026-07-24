from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from ..validators import normalize_decimal_input


class LocalizedDecimalField(serializers.DecimalField):
    """Decimal field that accepts either comma or point as decimal separator."""

    default_error_messages = {
        **serializers.DecimalField.default_error_messages,
        "invalid": "Informe um valor numérico válido.",
    }

    def to_internal_value(self, data):
        return super().to_internal_value(normalize_decimal_input(data))


class MoneyField(LocalizedDecimalField):
    def __init__(self, *args, max_digits=18, decimal_places=2, **kwargs):
        super().__init__(
            *args,
            max_digits=max_digits,
            decimal_places=decimal_places,
            **kwargs,
        )


class IntegerQuantityField(serializers.IntegerField):
    """Accept quantities only when their numeric value is an integer."""

    default_error_messages = {
        **serializers.IntegerField.default_error_messages,
        "invalid": "Informe uma quantidade inteira válida.",
        "fractional": "A quantidade deve ser um número inteiro, sem casas decimais.",
    }

    def to_internal_value(self, data):
        normalized = normalize_decimal_input(data)
        try:
            value = Decimal(str(normalized))
        except (InvalidOperation, TypeError, ValueError):
            self.fail("invalid")
        if not value.is_finite():
            self.fail("invalid")
        integral = value.to_integral_value()
        if value != integral:
            self.fail("fractional")
        return super().to_internal_value(str(integral))

    def to_representation(self, value):
        if value is None:
            return None
        try:
            return int(Decimal(str(value)))
        except (InvalidOperation, TypeError, ValueError):
            return super().to_representation(value)


class NullableUniqueCharField(serializers.CharField):
    """Normalize optional unique text fields so blank values are stored as NULL."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("allow_blank", True)
        kwargs.setdefault("allow_null", True)
        kwargs.setdefault("required", False)
        kwargs.setdefault("trim_whitespace", True)
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        if data is None:
            return None
        value = super().to_internal_value(data)
        return value or None

from rest_framework import serializers

from ..models import PackagingType
from .catalog import ProductPackagingSerializer
from .documents import StockOutputSerializer
from .misc import AlertSerializer, NotificationSerializer, SystemSettingSerializer


if not getattr(ProductPackagingSerializer, "_inactive_relation_guard_installed", False):
    _original_validate = ProductPackagingSerializer.validate

    def validate_active_grouping_relation(self, attrs):
        attrs = _original_validate(self, attrs)
        packaging_type = attrs.get(
            "packaging_type",
            getattr(self.instance, "packaging_type", None),
        )
        if packaging_type and not packaging_type.active:
            current_id = getattr(self.instance, "packaging_type_id", None)
            if not self.instance or current_id != packaging_type.pk:
                raise serializers.ValidationError(
                    {
                        "packaging_type": (
                            "O tipo de empacotamento selecionado está inativo."
                        )
                    }
                )
        if packaging_type and packaging_type.kind not in {
            PackagingType.GROUPING,
            PackagingType.BOTH,
        }:
            raise serializers.ValidationError(
                {
                    "packaging_type": (
                        "Selecione um tipo de empacotamento, como caixa, fardo ou grade."
                    )
                }
            )
        return attrs

    ProductPackagingSerializer.validate = validate_active_grouping_relation
    ProductPackagingSerializer._inactive_relation_guard_installed = True


StockOutputSerializer._declared_fields["payment_status"] = serializers.CharField(
    read_only=True,
)
StockOutputSerializer._declared_fields["payment_status_display"] = serializers.CharField(
    read_only=True,
)
StockOutputSerializer._declared_fields["payment_overdue"] = serializers.BooleanField(
    read_only=True,
)

AlertSerializer._declared_fields["output_number"] = serializers.CharField(
    source="output.number",
    read_only=True,
    allow_null=True,
)
AlertSerializer._declared_fields["customer_name"] = serializers.CharField(
    source="output.customer_name",
    read_only=True,
    allow_null=True,
)

NotificationSerializer._declared_fields["output_number"] = serializers.CharField(
    source="alert.output.number",
    read_only=True,
    allow_null=True,
)
NotificationSerializer._declared_fields["customer_name"] = serializers.CharField(
    source="alert.output.customer_name",
    read_only=True,
    allow_null=True,
)
NotificationSerializer._declared_fields["payment_due_date"] = serializers.DateField(
    source="alert.output.payment_due_date",
    read_only=True,
    allow_null=True,
)


if not getattr(NotificationSerializer, "_output_reference_installed", False):
    _original_reference = NotificationSerializer.get_reference_display

    def get_reference_display_with_output(self, obj):
        if obj.alert_id and obj.alert.output_id:
            customer = str(obj.alert.output.customer_name or "").strip()
            return (
                f"{obj.alert.output.number} — {customer}"
                if customer
                else obj.alert.output.number
            )
        return _original_reference(self, obj)

    NotificationSerializer.get_reference_display = get_reference_display_with_output
    NotificationSerializer._output_reference_installed = True


SystemSettingSerializer.BOOLEAN_KEYS = {
    *SystemSettingSerializer.BOOLEAN_KEYS,
    "credit_due_alerts_enabled",
}

if not getattr(SystemSettingSerializer, "_credit_settings_installed", False):
    _original_setting_validate = SystemSettingSerializer.validate

    def validate_with_credit_settings(self, attrs):
        attrs = _original_setting_validate(self, attrs)
        key = attrs.get("key", getattr(self.instance, "key", ""))
        if key == "credit_due_alert_days":
            raw_value = attrs.get(
                "value",
                getattr(self.instance, "value", ""),
            )
            try:
                days = int(str(raw_value).strip())
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError(
                    {"value": "Informe uma quantidade inteira de dias."}
                ) from exc
            if not 0 <= days <= 365:
                raise serializers.ValidationError(
                    {"value": "Informe um valor entre 0 e 365 dias."}
                )
            attrs["value"] = str(days)
        return attrs

    SystemSettingSerializer.validate = validate_with_credit_settings
    SystemSettingSerializer._credit_settings_installed = True

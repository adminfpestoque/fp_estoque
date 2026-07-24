from pathlib import Path


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"Trecho não encontrado: {label}")
    return text.replace(old, new, 1)


def replace_section(text, start_marker, end_marker, replacement, label):
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Início não encontrado: {label}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"Fim não encontrado: {label}")
    return text[:start] + replacement + text[end:]


# ---------------------------------------------------------------------------
# Backend: preferências de acessibilidade por usuário e situação efetiva
# ---------------------------------------------------------------------------
Path("backend/inventory/models/users.py").write_text('''from django.conf import settings
from django.db import models

from .base import TimeStamped


class UserProfile(TimeStamped):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    ROLES = [(ADMIN, "Administrador"), (OPERATOR, "Operador de estoque")]

    THEME_LIGHT = "LIGHT"
    THEME_DARK = "DARK"
    THEME_HIGH_CONTRAST = "HIGH_CONTRAST"
    THEMES = [
        (THEME_LIGHT, "Claro"),
        (THEME_DARK, "Escuro"),
        (THEME_HIGH_CONTRAST, "Alto contraste"),
    ]

    FONT_NORMAL = "NORMAL"
    FONT_LARGE = "LARGE"
    FONT_EXTRA_LARGE = "EXTRA_LARGE"
    FONT_SCALES = [
        (FONT_NORMAL, "Padrão"),
        (FONT_LARGE, "Grande"),
        (FONT_EXTRA_LARGE, "Muito grande"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_profile",
    )
    full_name = models.CharField(max_length=180)
    cpf = models.CharField(max_length=14, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    position = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=10, choices=ROLES, default=OPERATOR)
    active = models.BooleanField(default=True)
    theme = models.CharField(max_length=20, choices=THEMES, default=THEME_LIGHT)
    font_scale = models.CharField(max_length=20, choices=FONT_SCALES, default=FONT_NORMAL)
    reduced_motion = models.BooleanField(default=False)
    enhanced_focus = models.BooleanField(default=True)

    class Meta:
        ordering = ["full_name", "user__username"]

    def __str__(self):
        return self.full_name or self.user.username
''', encoding="utf-8")

Path("backend/inventory/migrations/0008_user_accessibility_preferences.py").write_text('''from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0007_product_soft_delete_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="theme",
            field=models.CharField(
                choices=[
                    ("LIGHT", "Claro"),
                    ("DARK", "Escuro"),
                    ("HIGH_CONTRAST", "Alto contraste"),
                ],
                default="LIGHT",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="font_scale",
            field=models.CharField(
                choices=[
                    ("NORMAL", "Padrão"),
                    ("LARGE", "Grande"),
                    ("EXTRA_LARGE", "Muito grande"),
                ],
                default="NORMAL",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="reduced_motion",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="enhanced_focus",
            field=models.BooleanField(default=True),
        ),
    ]
''', encoding="utf-8")

Path("backend/inventory/serializers/users.py").write_text('''from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from ..models import UserProfile
from ..permissions import role_for
from ..validators import validate_cpf

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "full_name",
            "cpf",
            "phone",
            "role",
            "active",
            "theme",
            "font_scale",
            "reduced_motion",
            "enhanced_focus",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_cpf(self, value):
        return validate_cpf(value) if value else value


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(source="inventory_profile", read_only=True)
    effective_active = serializers.SerializerMethodField()
    effective_role = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    full_name = serializers.CharField(write_only=True, required=False)
    cpf = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    role = serializers.ChoiceField(write_only=True, required=False, choices=UserProfile.ROLES)
    profile_active = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "effective_active",
            "effective_role",
            "date_joined",
            "last_login",
            "profile",
            "password",
            "full_name",
            "cpf",
            "phone",
            "role",
            "profile_active",
        ]
        read_only_fields = [
            "date_joined",
            "last_login",
            "profile",
            "effective_active",
            "effective_role",
        ]

    def get_effective_active(self, obj):
        profile = getattr(obj, "inventory_profile", None)
        return bool(obj.is_active and (profile.active if profile else True))

    def get_effective_role(self, obj):
        return role_for(obj)

    def validate_password(self, value):
        validate_password(value)
        return value

    def _profile_data(self, validated_data, *, creating=False):
        defaults = {
            "full_name": "",
            "cpf": None,
            "phone": "",
            "role": UserProfile.OPERATOR,
            "active": True,
        }
        mapping = {
            "full_name": "full_name",
            "cpf": "cpf",
            "phone": "phone",
            "role": "role",
            "profile_active": "active",
        }
        result = {}
        for payload_key, profile_key in mapping.items():
            if payload_key in validated_data:
                value = validated_data.pop(payload_key)
                if profile_key == "full_name":
                    value = str(value or "").strip()
                elif profile_key == "cpf":
                    value = value or None
                result[profile_key] = value
            elif creating:
                result[profile_key] = defaults[profile_key]
        return result

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password", None)
        profile_data = self._profile_data(validated_data, creating=True)
        requested_active = bool(validated_data.get("is_active", True))
        profile_data["active"] = requested_active
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        if not profile_data["full_name"]:
            profile_data["full_name"] = user.get_full_name() or user.username
        UserProfile.objects.create(user=user, **profile_data)
        return user

    @transaction.atomic
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        profile_updates = self._profile_data(validated_data, creating=False)
        if "is_active" in validated_data:
            profile_updates["active"] = bool(validated_data["is_active"])
        elif "active" in profile_updates:
            validated_data["is_active"] = bool(profile_updates["active"])

        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()

        profile, _ = UserProfile.objects.get_or_create(
            user=instance,
            defaults={"full_name": instance.get_full_name() or instance.username},
        )
        for key, value in profile_updates.items():
            if value not in (None, "") or key in {"active", "cpf"}:
                setattr(profile, key, value)
        profile.save()
        return instance


class MeSerializer(UserSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["permissions"]

    def get_permissions(self, obj):
        role = role_for(obj)
        return {
            "role": role,
            "is_admin": role == UserProfile.ADMIN,
            "can_manage_users": role == UserProfile.ADMIN,
            "can_adjust_stock": role == UserProfile.ADMIN,
            "can_cancel_movements": role == UserProfile.ADMIN,
            "can_conclude_inventory": role == UserProfile.ADMIN,
        }
''', encoding="utf-8")

path = Path("backend/inventory/views/catalog.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "    UserSerializer,\n)",
    "    UserSerializer,\n    UserProfileSerializer,\n)",
    "import do serializer de perfil",
)
old_me = '''    @action(detail=False, methods=["get"], permission_classes=[IsInventoryUser])
    def me(self, request):
        return Response(MeSerializer(request.user, context={"request": request}).data)
'''
new_me = '''    @action(detail=False, methods=["get", "patch"], permission_classes=[IsInventoryUser])
    def me(self, request):
        if request.method == "PATCH":
            allowed = {"theme", "font_scale", "reduced_motion", "enhanced_focus"}
            unknown = set(request.data) - allowed
            if unknown:
                return Response(
                    {"detail": "Apenas preferências de aparência e acessibilidade podem ser alteradas aqui."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            profile, _ = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={"full_name": request.user.get_full_name() or request.user.username},
            )
            serializer = UserProfileSerializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            audit(
                request.user,
                "UPDATE_ACCESSIBILITY",
                request.user,
                "Preferências de aparência e acessibilidade atualizadas.",
                metadata={key: serializer.validated_data.get(key) for key in allowed if key in serializer.validated_data},
            )
            request.user.refresh_from_db()
        return Response(MeSerializer(request.user, context={"request": request}).data)
'''
text = replace_once(text, old_me, new_me, "ação de preferências do usuário atual")
start = "    def _set_user_activation(self, request, active):\n"
end = "    @action(detail=True, methods=[\"post\"])\n    def activate"
new_activation = '''    def _set_user_activation(self, request, active):
        user = self.get_object()
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={"full_name": user.get_full_name() or user.username},
        )

        if not active and user.pk == request.user.pk:
            return Response(
                {"detail": "Você não pode inativar o usuário que está usando no momento."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_is_admin = bool(user.is_superuser or profile.role == UserProfile.ADMIN)
        if not active and target_is_admin:
            has_other_admin = (
                User.objects.filter(is_active=True)
                .filter(
                    Q(is_superuser=True)
                    | Q(
                        inventory_profile__role=UserProfile.ADMIN,
                        inventory_profile__active=True,
                    )
                )
                .exclude(pk=user.pk)
                .exists()
            )
            if not has_other_admin:
                return Response(
                    {"detail": "Não é possível inativar o último administrador ativo do sistema."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if user.is_active != active or profile.active != active:
            with transaction.atomic():
                user.is_active = active
                user.save(update_fields=["is_active"])
                profile.active = active
                profile.save(update_fields=["active", "updated_at"])
                audit(
                    request.user,
                    "ACTIVATE" if active else "DEACTIVATE",
                    user,
                    f"Status do usuário alterado para {'ativo' if active else 'inativo'}.",
                )

        user = self.get_queryset().get(pk=user.pk)
        return Response(self.get_serializer(user).data)

'''
text = replace_section(text, start, end, new_activation, "sincronização da ativação de usuário")
path.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Backend: configurações operacionais realmente utilizadas pelos alertas
# ---------------------------------------------------------------------------
path = Path("backend/inventory/models/alerts.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    @classmethod
    def get_int(cls, key: str, default: int) -> int:
        try:
            return int(cls.objects.get(key=key).value)
        except (cls.DoesNotExist, TypeError, ValueError):
            return default
''',
    '''    @classmethod
    def get_int(cls, key: str, default: int) -> int:
        try:
            return int(cls.objects.get(key=key).value)
        except (cls.DoesNotExist, TypeError, ValueError):
            return default

    @classmethod
    def get_bool(cls, key: str, default: bool = True) -> bool:
        try:
            value = str(cls.objects.get(key=key).value).strip().lower()
        except cls.DoesNotExist:
            return default
        if value in {"1", "true", "sim", "yes", "on"}:
            return True
        if value in {"0", "false", "não", "nao", "no", "off"}:
            return False
        return default
''',
    "leitura booleana de configurações",
)
path.write_text(text, encoding="utf-8")

path = Path("backend/inventory/services.py")
text = path.read_text(encoding="utf-8")
start = "def _build_alert_candidates():\n"
end = "\n\n@transaction.atomic\ndef refresh_alerts"
new_function = '''def _build_alert_candidates():
    today = timezone.localdate()
    days = max(0, SystemSetting.get_int("expiration_alert_days", 30))
    limit = today + timedelta(days=days)
    candidates = []

    if SystemSetting.get_bool("stock_alerts_enabled", True):
        for product in Product.objects.filter(active=True, deleted_at__isnull=True):
            if product.stock <= 0:
                candidates.append(
                    {
                        "type": Alert.OUT_OF_STOCK,
                        "level": Alert.CRITICAL,
                        "product": product,
                        "message": f"{product.name} está sem estoque.",
                    }
                )
            elif product.stock <= product.minimum_stock:
                candidates.append(
                    {
                        "type": Alert.LOW_STOCK,
                        "level": Alert.WARNING,
                        "product": product,
                        "message": (
                            f"{product.name} atingiu o estoque mínimo "
                            f"({int(product.stock)} unidade(s))."
                        ),
                    }
                )

    if SystemSetting.get_bool("expiration_alerts_enabled", True):
        lots = Lot.objects.select_related("product").filter(
            active=True,
            quantity__gt=0,
            product__active=True,
            product__deleted_at__isnull=True,
        )
        for lot in lots:
            if lot.expiration_date and lot.expiration_date < today:
                candidates.append(
                    {
                        "type": Alert.EXPIRED,
                        "level": Alert.CRITICAL,
                        "product": lot.product,
                        "lot": lot,
                        "message": f"O lote {lot.number} de {lot.product_name} está vencido.",
                    }
                )
            elif lot.expiration_date and lot.expiration_date <= limit:
                candidates.append(
                    {
                        "type": Alert.EXPIRING,
                        "level": Alert.WARNING,
                        "product": lot.product,
                        "lot": lot,
                        "message": (
                            f"O lote {lot.number} de {lot.product_name} vence em "
                            f"{lot.expiration_date:%d/%m/%Y}."
                        ),
                    }
                )

    if SystemSetting.get_bool("inventory_divergence_alerts_enabled", True):
        divergence_items = (
            InventoryItem.objects.select_related("inventory", "product")
            .filter(
                counted=True,
                inventory__status__in=["OPEN", "WAITING"],
                product__active=True,
                product__deleted_at__isnull=True,
            )
            .exclude(system_quantity=F("counted_quantity"))
        )
        for item in divergence_items:
            candidates.append(
                {
                    "type": Alert.INVENTORY_DIVERGENCE,
                    "level": Alert.WARNING,
                    "product": item.product,
                    "inventory": item.inventory,
                    "message": (
                        f"Divergência de {int(item.difference)} unidade(s) em "
                        f"{item.product.name} no inventário {item.inventory.number}."
                    ),
                }
            )

    return candidates
'''
text = replace_section(text, start, end, new_function, "configurações aplicadas aos alertas")
path.write_text(text, encoding="utf-8")

path = Path("backend/inventory/serializers/misc.py")
text = path.read_text(encoding="utf-8")
old_setting = '''class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSetting
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]
'''
new_setting = '''class SystemSettingSerializer(serializers.ModelSerializer):
    BOOLEAN_KEYS = {
        "stock_alerts_enabled",
        "expiration_alerts_enabled",
        "inventory_divergence_alerts_enabled",
    }

    class Meta:
        model = SystemSetting
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        key = attrs.get("key", getattr(self.instance, "key", ""))
        value = str(attrs.get("value", getattr(self.instance, "value", ""))).strip()
        if not key:
            raise serializers.ValidationError({"key": "Informe a chave da configuração."})
        if key in self.BOOLEAN_KEYS:
            normalized = value.lower()
            if normalized not in {"true", "false", "1", "0", "sim", "não", "nao"}:
                raise serializers.ValidationError({"value": "Use verdadeiro ou falso para esta configuração."})
            attrs["value"] = "true" if normalized in {"true", "1", "sim"} else "false"
        elif key == "expiration_alert_days":
            try:
                days = int(value)
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError({"value": "Informe uma quantidade inteira de dias."}) from exc
            if not 1 <= days <= 365:
                raise serializers.ValidationError({"value": "Informe um valor entre 1 e 365 dias."})
            attrs["value"] = str(days)
        elif not value:
            raise serializers.ValidationError({"value": "Informe um valor."})
        return attrs
'''
text = replace_once(text, old_setting, new_setting, "validação das configurações")
path.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# Testes do backend
# ---------------------------------------------------------------------------
Path("backend/inventory/test_accessibility_settings.py").write_text('''from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Alert, Category, Product, SystemSetting, UserProfile
from .services import refresh_alerts

User = get_user_model()


class AccessibilityAndUserStatusTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "access-admin",
            email="access-admin@example.com",
            password="AccessAdmin123!",
        )
        UserProfile.objects.create(
            user=self.admin,
            full_name="Administrador de acessibilidade",
            role=UserProfile.OPERATOR,
            active=True,
        )
        self.operator = User.objects.create_user(
            "access-operator",
            password="AccessOperator123!",
            is_active=False,
        )
        UserProfile.objects.create(
            user=self.operator,
            full_name="Operador inativo",
            role=UserProfile.OPERATOR,
            active=False,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_activation_response_and_list_use_the_effective_status(self):
        response = self.client.post(f"/api/users/{self.operator.id}/activate/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["is_active"])
        self.assertTrue(response.data["profile"]["active"])
        self.assertTrue(response.data["effective_active"])

        listed = self.client.get("/api/users/")
        self.assertEqual(listed.status_code, 200, listed.data)
        rows = listed.data.get("results", listed.data)
        row = next(item for item in rows if item["id"] == self.operator.id)
        self.assertTrue(row["effective_active"])

    def test_superuser_is_presented_as_administrator_even_with_legacy_profile_role(self):
        response = self.client.get("/api/users/me/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["effective_role"], UserProfile.ADMIN)
        self.assertEqual(response.data["permissions"]["role"], UserProfile.ADMIN)

    def test_current_user_can_save_accessibility_preferences(self):
        response = self.client.patch(
            "/api/users/me/",
            {
                "theme": UserProfile.THEME_HIGH_CONTRAST,
                "font_scale": UserProfile.FONT_EXTRA_LARGE,
                "reduced_motion": True,
                "enhanced_focus": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.admin.inventory_profile.refresh_from_db()
        self.assertEqual(self.admin.inventory_profile.theme, UserProfile.THEME_HIGH_CONTRAST)
        self.assertEqual(self.admin.inventory_profile.font_scale, UserProfile.FONT_EXTRA_LARGE)
        self.assertTrue(self.admin.inventory_profile.reduced_motion)
        self.assertEqual(response.data["profile"]["theme"], UserProfile.THEME_HIGH_CONTRAST)

    def test_stock_alert_setting_is_applied(self):
        category = Category.objects.create(name="Bebidas de teste")
        product = Product.objects.create(
            code="ACCESS-001",
            name="Produto sem estoque",
            category=category,
            stock=Decimal("0"),
            minimum_stock=Decimal("2"),
        )
        SystemSetting.objects.create(key="stock_alerts_enabled", value="false")
        refresh_alerts(notify=False)
        self.assertFalse(Alert.objects.filter(product=product, active=True).exists())

        setting = SystemSetting.objects.get(key="stock_alerts_enabled")
        setting.value = "true"
        setting.save(update_fields=["value", "updated_at"])
        refresh_alerts(notify=False)
        self.assertTrue(
            Alert.objects.filter(product=product, type=Alert.OUT_OF_STOCK, active=True).exists()
        )
''', encoding="utf-8")

# ---------------------------------------------------------------------------
# Frontend: preferências, usuários e tela de configurações
# ---------------------------------------------------------------------------
Path("frontend/src/preferences.js").write_text('''export const DEFAULT_PREFERENCES = {
  theme: "LIGHT",
  font_scale: "NORMAL",
  reduced_motion: false,
  enhanced_focus: true,
};

const STORAGE_KEY = "fp_accessibility_preferences";
const THEMES = new Set(["LIGHT", "DARK", "HIGH_CONTRAST"]);
const FONT_SCALES = new Set(["NORMAL", "LARGE", "EXTRA_LARGE"]);

export function normalizePreferences(source = {}) {
  const theme = String(source.theme || DEFAULT_PREFERENCES.theme).toUpperCase();
  const fontScale = String(source.font_scale || DEFAULT_PREFERENCES.font_scale).toUpperCase();
  return {
    theme: THEMES.has(theme) ? theme : DEFAULT_PREFERENCES.theme,
    font_scale: FONT_SCALES.has(fontScale) ? fontScale : DEFAULT_PREFERENCES.font_scale,
    reduced_motion: Boolean(source.reduced_motion),
    enhanced_focus: source.enhanced_focus !== false,
  };
}

export function loadStoredPreferences() {
  try {
    return normalizePreferences(JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"));
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

export function storePreferences(source) {
  const preferences = normalizePreferences(source);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // A interface continua funcionando mesmo quando o armazenamento está indisponível.
  }
  return preferences;
}

export function applyPreferences(source) {
  const preferences = normalizePreferences(source);
  const root = document.documentElement;
  root.dataset.theme = {
    LIGHT: "light",
    DARK: "dark",
    HIGH_CONTRAST: "contrast",
  }[preferences.theme];
  root.dataset.fontScale = preferences.font_scale.toLowerCase().replaceAll("_", "-");
  root.dataset.reducedMotion = String(preferences.reduced_motion);
  root.dataset.enhancedFocus = String(preferences.enhanced_focus);
  root.style.colorScheme = preferences.theme === "LIGHT" ? "light" : "dark";
  return preferences;
}

export function applyAndStorePreferences(source) {
  const preferences = storePreferences(source);
  applyPreferences(preferences);
  return preferences;
}
''', encoding="utf-8")

Path("frontend/src/pages/listing.jsx").write_text('''import { React, useEffect, useState, api, unwrap, Search } from "../shared.jsx";

export function useList(endpoint, initialParams = {}) {
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [params, setParams] = useState({ page: 1, ...initialParams });

  const reload = async (override = {}) => {
    setLoading(true);
    const merged = { ...params, ...override };
    try {
      const response = await api.get(endpoint, { params: merged });
      const nextRows = unwrap(response.data);
      setRows(nextRows);
      setCount(response.data?.count ?? nextRows.length);
      if (Object.keys(override).length) setParams(merged);
      return nextRows;
    } finally {
      setLoading(false);
    }
  };

  const replaceRow = (nextRow) => {
    if (!nextRow?.id) return;
    setRows((current) => current.map((row) => row.id === nextRow.id ? nextRow : row));
  };

  useEffect(() => { reload(); }, [endpoint, JSON.stringify(params)]); // eslint-disable-line react-hooks/exhaustive-deps
  return { rows, count, loading, params, setParams, setRows, replaceRow, reload };
}

export function SearchBar({ value, onChange, placeholder = "Pesquisar..." }) {
  return <div className="search-box"><Search size={17} /><input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></div>;
}
''', encoding="utf-8")

path = Path("frontend/src/pages/users.jsx")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''function isActive(row) {
  return Boolean(row.is_active && row.profile?.active);
}
''',
    '''function isActive(row) {
  if (typeof row.effective_active === "boolean") return row.effective_active;
  return Boolean(row.is_active && (row.profile?.active ?? true));
}

function effectiveRole(row) {
  return row.effective_role || row.profile?.role || "OPERATOR";
}
''',
    "situação efetiva do usuário",
)
text = replace_once(text, "      list.reload();", "      await list.reload();", "atualização após salvar usuário")
old_toggle = '''      const activate = !isActive(pendingAction);
      await api.post(`users/${pendingAction.id}/${activate ? "activate" : "deactivate"}/`);
      notify(`Usuário ${activate ? "ativado" : "inativado"} com sucesso.`);
      setPendingAction(null);
      list.reload();
'''
new_toggle = '''      const activate = !isActive(pendingAction);
      const response = await api.post(`users/${pendingAction.id}/${activate ? "activate" : "deactivate"}/`);
      list.replaceRow(response.data);
      notify(`Usuário ${activate ? "ativado" : "inativado"} com sucesso.`);
      setPendingAction(null);
      await list.reload();
'''
text = replace_once(text, old_toggle, new_toggle, "atualização imediata da linha do usuário")
text = replace_once(
    text,
    '''                  value={row.profile?.role}
                  label={row.profile?.role === "ADMIN" ? "Administrador" : "Operador de estoque"}
''',
    '''                  value={effectiveRole(row)}
                  label={effectiveRole(row) === "ADMIN" ? "Administrador" : "Operador de estoque"}
''',
    "perfil efetivo na tabela de usuários",
)
path.write_text(text, encoding="utf-8")

path = Path("frontend/src/main.jsx")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'import { SettingsPage } from "./pages/settings.jsx";\n',
    'import { SettingsPage } from "./pages/settings.jsx";\nimport { applyAndStorePreferences, applyPreferences, loadStoredPreferences, normalizePreferences } from "./preferences.js";\n\napplyPreferences(loadStoredPreferences());\n',
    "inicialização do tema",
)
text = replace_once(
    text,
    '''      const response = await api.get("users/me/");
      setMe(response.data);
''',
    '''      const response = await api.get("users/me/");
      const preferences = normalizePreferences(response.data.profile || {});
      applyAndStorePreferences(preferences);
      setMe(response.data);
''',
    "preferências carregadas da conta",
)
text = replace_once(
    text,
    '    settings: <SettingsPage notify={notify} />,',
    '    settings: <SettingsPage notify={notify} me={me} onMeChanged={setMe} />,',
    "propriedades da tela de configurações",
)
path.write_text(text, encoding="utf-8")

Path("frontend/src/pages/settings.jsx").write_text('''import {
  React,
  useEffect,
  useMemo,
  useState,
  api,
  unwrap,
  getError,
  Button,
  Modal,
  Field,
  DataTable,
  StatusBadge,
  Eye,
  Pencil,
  Plus,
  RefreshCw,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
} from "../shared.jsx";
import {
  DEFAULT_PREFERENCES,
  applyAndStorePreferences,
  normalizePreferences,
} from "../preferences.js";

const OPERATIONAL_DEFAULTS = {
  expiration_alert_days: "30",
  stock_alerts_enabled: "true",
  expiration_alerts_enabled: "true",
  inventory_divergence_alerts_enabled: "true",
};

const SETTING_DESCRIPTIONS = {
  expiration_alert_days: "Quantidade de dias de antecedência para avisar sobre vencimentos.",
  stock_alerts_enabled: "Gerar alertas para produtos sem estoque ou abaixo do mínimo.",
  expiration_alerts_enabled: "Gerar alertas para lotes vencidos ou próximos do vencimento.",
  inventory_divergence_alerts_enabled: "Gerar alertas quando a contagem do inventário divergir do sistema.",
};

const THEME_OPTIONS = [
  { value: "LIGHT", label: "Claro", description: "Visual atual, com superfícies claras e detalhes em amarelo." },
  { value: "DARK", label: "Escuro", description: "Reduz o brilho usando preto e cinza com destaque amarelo." },
  { value: "HIGH_CONTRAST", label: "Alto contraste", description: "Preto, amarelo e branco com bordas reforçadas." },
];

function valuesFromRows(rows) {
  const values = { ...OPERATIONAL_DEFAULTS };
  rows.forEach((row) => {
    if (row.key in values) values[row.key] = String(row.value);
  });
  return values;
}

function isTrue(value) {
  return ["true", "1", "sim"].includes(String(value).toLowerCase());
}

export function SettingsPage({ notify, me, onMeChanged }) {
  const [tab, setTab] = useState("accessibility");
  const [preferences, setPreferences] = useState(() => normalizePreferences(me?.profile || {}));
  const [settingsRows, setSettingsRows] = useState([]);
  const [operational, setOperational] = useState({ ...OPERATIONAL_DEFAULTS });
  const [advancedForm, setAdvancedForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [savingPreferences, setSavingPreferences] = useState(false);
  const [savingOperational, setSavingOperational] = useState(false);

  const settingsByKey = useMemo(
    () => Object.fromEntries(settingsRows.map((row) => [row.key, row])),
    [settingsRows],
  );

  async function loadSettings() {
    setLoading(true);
    try {
      const response = await api.get("settings/?page_size=200");
      const rows = unwrap(response.data);
      setSettingsRows(rows);
      setOperational(valuesFromRows(rows));
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setPreferences(normalizePreferences(me?.profile || {}));
  }, [me?.id, me?.profile?.theme, me?.profile?.font_scale, me?.profile?.reduced_motion, me?.profile?.enhanced_focus]);

  useEffect(() => { loadSettings(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function changePreference(key, value) {
    setPreferences((current) => {
      const next = normalizePreferences({ ...current, [key]: value });
      applyAndStorePreferences(next);
      return next;
    });
  }

  async function savePreferences() {
    setSavingPreferences(true);
    try {
      const response = await api.patch("users/me/", preferences);
      const saved = normalizePreferences(response.data.profile || preferences);
      applyAndStorePreferences(saved);
      setPreferences(saved);
      onMeChanged?.(response.data);
      notify("Preferências de aparência e acessibilidade salvas.");
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setSavingPreferences(false);
    }
  }

  async function restorePreferences() {
    const defaults = { ...DEFAULT_PREFERENCES };
    setPreferences(defaults);
    applyAndStorePreferences(defaults);
    setSavingPreferences(true);
    try {
      const response = await api.patch("users/me/", defaults);
      onMeChanged?.(response.data);
      notify("Preferências restauradas para o padrão.");
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setSavingPreferences(false);
    }
  }

  async function upsertSetting(key, value, description) {
    const payload = { key, value: String(value), description };
    if (settingsByKey[key]) {
      return api.put(`settings/${encodeURIComponent(key)}/`, payload);
    }
    return api.post("settings/", payload);
  }

  async function saveOperational(event) {
    event.preventDefault();
    setSavingOperational(true);
    try {
      const days = Number(operational.expiration_alert_days);
      if (!Number.isInteger(days) || days < 1 || days > 365) {
        throw new Error("Informe entre 1 e 365 dias para os alertas de validade.");
      }
      await Promise.all(
        Object.entries(operational).map(([key, value]) =>
          upsertSetting(key, value, SETTING_DESCRIPTIONS[key] || ""),
        ),
      );
      await api.post("alerts/refresh/");
      await loadSettings();
      notify("Configurações de alertas atualizadas e recalculadas.");
    } catch (error) {
      notify(error?.response ? getError(error) : error.message, "error");
    } finally {
      setSavingOperational(false);
    }
  }

  async function saveAdvanced(event) {
    event.preventDefault();
    try {
      await upsertSetting(
        advancedForm.key.trim(),
        advancedForm.value,
        advancedForm.description || "",
      );
      setAdvancedForm(null);
      await loadSettings();
      notify("Configuração salva com sucesso.");
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  return (
    <>
      <div className="settings-tabs" role="tablist" aria-label="Seções de configurações">
        <button type="button" className={tab === "accessibility" ? "active" : ""} onClick={() => setTab("accessibility")}>
          <Eye size={18} /> Aparência e acessibilidade
        </button>
        <button type="button" className={tab === "alerts" ? "active" : ""} onClick={() => setTab("alerts")}>
          <ShieldCheck size={18} /> Alertas e operação
        </button>
        <button type="button" className={tab === "advanced" ? "active" : ""} onClick={() => setTab("advanced")}>
          <SlidersHorizontal size={18} /> Parâmetros avançados
        </button>
      </div>

      {tab === "accessibility" && (
        <section className="panel settings-section" aria-labelledby="accessibility-heading">
          <div className="settings-heading">
            <div>
              <h2 id="accessibility-heading">Aparência e acessibilidade</h2>
              <p>As preferências ficam vinculadas à sua conta e são aplicadas em todo o sistema.</p>
            </div>
            <StatusBadge value="active" label="Preferência individual" />
          </div>

          <div className="settings-group">
            <h3>Tema da interface</h3>
            <div className="theme-options">
              {THEME_OPTIONS.map((option) => (
                <button
                  type="button"
                  key={option.value}
                  className={`theme-option theme-${option.value.toLowerCase().replaceAll("_", "-")} ${preferences.theme === option.value ? "selected" : ""}`}
                  aria-pressed={preferences.theme === option.value}
                  onClick={() => changePreference("theme", option.value)}
                >
                  <span className="theme-swatch" aria-hidden="true"><i /><i /><i /></span>
                  <strong>{option.label}</strong>
                  <small>{option.description}</small>
                </button>
              ))}
            </div>
          </div>

          <div className="settings-grid two-columns">
            <div className="settings-group">
              <Field label="Tamanho do texto" hint="Aumenta textos e controles sem usar o zoom do navegador.">
                <select value={preferences.font_scale} onChange={(event) => changePreference("font_scale", event.target.value)}>
                  <option value="NORMAL">Padrão</option>
                  <option value="LARGE">Grande</option>
                  <option value="EXTRA_LARGE">Muito grande</option>
                </select>
              </Field>
            </div>
            <div className="accessibility-preview" aria-live="polite">
              <Settings size={22} />
              <div><strong>Prévia da leitura</strong><p>Texto, campos, tabelas e botões acompanham as opções selecionadas.</p></div>
            </div>
          </div>

          <div className="settings-switches">
            <label className="settings-switch">
              <input type="checkbox" checked={preferences.reduced_motion} onChange={(event) => changePreference("reduced_motion", event.target.checked)} />
              <span><strong>Reduzir animações</strong><small>Remove movimentos e transições que podem causar desconforto.</small></span>
            </label>
            <label className="settings-switch">
              <input type="checkbox" checked={preferences.enhanced_focus} onChange={(event) => changePreference("enhanced_focus", event.target.checked)} />
              <span><strong>Destaque reforçado de foco</strong><small>Mostra um contorno amarelo forte ao navegar pelo teclado.</small></span>
            </label>
          </div>

          <div className="form-actions settings-actions">
            <Button type="button" variant="secondary" onClick={restorePreferences} disabled={savingPreferences}>Restaurar padrão</Button>
            <Button type="button" onClick={savePreferences} disabled={savingPreferences}>
              {savingPreferences ? "Salvando..." : "Salvar preferências"}
            </Button>
          </div>
        </section>
      )}

      {tab === "alerts" && (
        <section className="panel settings-section" aria-labelledby="alerts-settings-heading">
          <div className="settings-heading">
            <div>
              <h2 id="alerts-settings-heading">Alertas e operação</h2>
              <p>Estes parâmetros alteram diretamente a geração de alertas e notificações do estoque.</p>
            </div>
            <Button type="button" variant="secondary" icon={RefreshCw} onClick={loadSettings} disabled={loading}>Atualizar</Button>
          </div>
          <form onSubmit={saveOperational}>
            <div className="settings-grid two-columns">
              <Field label="Avisar vencimento com antecedência" hint="De 1 a 365 dias.">
                <div className="input-with-suffix">
                  <input
                    type="number"
                    min="1"
                    max="365"
                    step="1"
                    value={operational.expiration_alert_days}
                    onChange={(event) => setOperational({ ...operational, expiration_alert_days: event.target.value })}
                    required
                  />
                  <span>dias</span>
                </div>
              </Field>
              <div className="settings-info-box">
                <ShieldCheck size={21} />
                <p>Ao salvar, os alertas atuais são recalculados sem criar duplicações.</p>
              </div>
            </div>

            <div className="settings-switches">
              {[
                ["stock_alerts_enabled", "Alertas de estoque", "Avisar quando um produto estiver sem estoque ou abaixo do mínimo."],
                ["expiration_alerts_enabled", "Alertas de validade", "Avisar sobre lotes vencidos ou próximos do vencimento."],
                ["inventory_divergence_alerts_enabled", "Alertas de inventário", "Avisar quando a contagem física divergir do sistema."],
              ].map(([key, label, description]) => (
                <label className="settings-switch" key={key}>
                  <input
                    type="checkbox"
                    checked={isTrue(operational[key])}
                    onChange={(event) => setOperational({ ...operational, [key]: String(event.target.checked) })}
                  />
                  <span><strong>{label}</strong><small>{description}</small></span>
                </label>
              ))}
            </div>

            <div className="form-actions settings-actions">
              <Button disabled={savingOperational || loading}>
                {savingOperational ? "Salvando..." : "Salvar e recalcular alertas"}
              </Button>
            </div>
          </form>
        </section>
      )}

      {tab === "advanced" && (
        <section className="panel settings-section">
          <div className="settings-heading">
            <div>
              <h2>Parâmetros avançados</h2>
              <p>Área administrativa para consultar e manter configurações adicionais do sistema.</p>
            </div>
            <Button icon={Plus} onClick={() => setAdvancedForm({ key: "", value: "", description: "" })}>Nova configuração</Button>
          </div>
          <DataTable
            rows={settingsRows}
            loading={loading}
            emptyText="Nenhuma configuração adicional foi cadastrada."
            columns={[
              { key: "key", label: "Chave" },
              { key: "value", label: "Valor" },
              { key: "description", label: "Descrição", render: (row) => row.description || "-" },
              {
                key: "actions",
                label: "Ações",
                render: (row) => (
                  <button className="icon-btn" onClick={() => setAdvancedForm({ ...row })} title={`Editar ${row.key}`} aria-label={`Editar ${row.key}`}>
                    <Pencil size={16} />
                  </button>
                ),
              },
            ]}
          />
        </section>
      )}

      {advancedForm && (
        <Modal title={advancedForm.id ? "Editar configuração" : "Nova configuração"} onClose={() => setAdvancedForm(null)}>
          <form className="form-grid" onSubmit={saveAdvanced}>
            <Field label="Chave" required>
              <input disabled={Boolean(advancedForm.id)} value={advancedForm.key} onChange={(event) => setAdvancedForm({ ...advancedForm, key: event.target.value })} required />
            </Field>
            <Field label="Valor" required>
              <input value={advancedForm.value} onChange={(event) => setAdvancedForm({ ...advancedForm, value: event.target.value })} required />
            </Field>
            <Field label="Descrição">
              <textarea value={advancedForm.description || ""} onChange={(event) => setAdvancedForm({ ...advancedForm, description: event.target.value })} />
            </Field>
            <div className="form-actions full">
              <Button type="button" variant="secondary" onClick={() => setAdvancedForm(null)}>Cancelar</Button>
              <Button>Salvar configuração</Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
''', encoding="utf-8")

# ---------------------------------------------------------------------------
# CSS: temas claro, escuro, alto contraste e componentes de configurações
# ---------------------------------------------------------------------------
path = Path("frontend/src/styles/base.css")
text = path.read_text(encoding="utf-8")
text += r'''

/* Temas e preferências de acessibilidade */
:root {
  --page-bg: #f3f4f6;
  --text: #111111;
  --surface: #ffffff;
  --surface-subtle: #f8f8f8;
  --surface-hover: #fffaf0;
  --input-bg: #ffffff;
  --sidebar-bg: #111111;
  --sidebar-text: #ffffff;
  --focus-color: #b77900;
  --overlay: rgba(0, 0, 0, .58);
  color-scheme: light;
}

:root[data-theme="dark"] {
  --page-bg: #0d0d0e;
  --text: #f5f5f5;
  --surface: #18181a;
  --surface-subtle: #222225;
  --surface-hover: #2b271b;
  --input-bg: #111113;
  --sidebar-bg: #080808;
  --sidebar-text: #ffffff;
  --muted: #b7b7bd;
  --border: #3a3a3f;
  --focus-color: #ffd02a;
  --danger: #ff7777;
  --success: #65d895;
  --warning: #ffd166;
  --overlay: rgba(0, 0, 0, .76);
  color-scheme: dark;
}

:root[data-theme="contrast"] {
  --page-bg: #000000;
  --text: #ffffff;
  --surface: #050505;
  --surface-subtle: #111111;
  --surface-hover: #211b00;
  --input-bg: #000000;
  --sidebar-bg: #000000;
  --sidebar-text: #ffffff;
  --gold: #ffd400;
  --gold-dark: #ffd400;
  --muted: #f0f0f0;
  --border: #ffd400;
  --focus-color: #ffd400;
  --danger: #ff8080;
  --success: #8affb4;
  --warning: #ffe56b;
  --overlay: rgba(0, 0, 0, .9);
  color-scheme: dark;
}

:root[data-font-scale="large"] { font-size: 112.5%; }
:root[data-font-scale="extra-large"] { font-size: 125%; }

body,
.content { background: var(--page-bg); color: var(--text); }

input,
select,
textarea {
  background: var(--input-bg);
  color: var(--text);
  border-color: var(--border);
}
input::placeholder,
textarea::placeholder { color: var(--muted); opacity: 1; }

:root[data-enhanced-focus="true"] :is(button, a, input, select, textarea, [tabindex]):focus-visible {
  outline: 3px solid var(--focus-color) !important;
  outline-offset: 3px !important;
  box-shadow: 0 0 0 2px var(--page-bg) !important;
}

:root[data-reduced-motion="true"] *,
:root[data-reduced-motion="true"] *::before,
:root[data-reduced-motion="true"] *::after {
  scroll-behavior: auto !important;
  animation-duration: .001ms !important;
  animation-iteration-count: 1 !important;
  transition-duration: .001ms !important;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    animation-duration: .001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .001ms !important;
  }
}

:root[data-theme="dark"] :is(
  .topbar, .panel, .metric-card, .filters-bar, .modal, .notification-popover,
  .notification-item, .section-tabs, .summary-cards > div, .dashboard-view-option,
  .city-suggestions, .city-suggestions button, .login-card, .settings-section,
  .notification-summary-grid > div
),
:root[data-theme="contrast"] :is(
  .topbar, .panel, .metric-card, .filters-bar, .modal, .notification-popover,
  .notification-item, .section-tabs, .summary-cards > div, .dashboard-view-option,
  .city-suggestions, .city-suggestions button, .login-card, .settings-section,
  .notification-summary-grid > div
) {
  background: var(--surface) !important;
  color: var(--text) !important;
  border-color: var(--border) !important;
}

:root[data-theme="dark"] :is(th, .items-header, .notification-see-all, .metric-icon),
:root[data-theme="contrast"] :is(th, .items-header, .notification-see-all, .metric-icon) {
  background: var(--surface-subtle) !important;
  color: var(--text) !important;
  border-color: var(--border) !important;
}

:root[data-theme="dark"] :is(td, .item-row, .notification-item, .modal-header, .sidebar-top),
:root[data-theme="contrast"] :is(td, .item-row, .notification-item, .modal-header, .sidebar-top) {
  border-color: var(--border) !important;
}

:root[data-theme="dark"] :is(h1, h2, h3, h4, strong, .field > span, .empty-state h3),
:root[data-theme="contrast"] :is(h1, h2, h3, h4, strong, .field > span, .empty-state h3) {
  color: var(--text) !important;
}

:root[data-theme="dark"] tbody tr:hover,
:root[data-theme="contrast"] tbody tr:hover { background: var(--surface-hover) !important; }

:root[data-theme="dark"] .icon-btn,
:root[data-theme="dark"] .row-actions button,
:root[data-theme="contrast"] .icon-btn,
:root[data-theme="contrast"] .row-actions button {
  background: var(--surface-subtle);
  color: var(--text);
  border: 1px solid var(--border);
}

:root[data-theme="contrast"] .sidebar { border-right: 2px solid var(--gold); }
:root[data-theme="contrast"] .sidebar nav button,
:root[data-theme="contrast"] .sidebar-logout { color: #ffffff; }
:root[data-theme="contrast"] .badge-neutral { background: #111; color: #fff; border: 1px solid var(--gold); }
:root[data-theme="contrast"] .badge-success,
:root[data-theme="contrast"] .badge-warning,
:root[data-theme="contrast"] .badge-danger { border: 1px solid currentColor; }
'''
path.write_text(text, encoding="utf-8")

path = Path("frontend/src/styles/content.css")
text = path.read_text(encoding="utf-8")
text += r'''

/* Tela de configurações */
.settings-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.settings-tabs button {
  min-height: 44px;
  padding: 10px 15px;
  border: 1px solid var(--border);
  border-radius: 11px;
  background: var(--surface);
  color: var(--text);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 800;
}
.settings-tabs button.active {
  background: var(--gold);
  color: #111;
  border-color: var(--gold-dark);
}
.settings-section { padding: 22px; }
.settings-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 22px;
}
.settings-heading h2 { margin: 0; font-size: 21px; }
.settings-heading p { margin: 5px 0 0; color: var(--muted); }
.settings-group {
  border-top: 1px solid var(--border);
  padding-top: 18px;
  margin-top: 18px;
}
.settings-group h3 { margin: 0 0 12px; font-size: 16px; }
.settings-grid { display: grid; gap: 16px; margin-top: 18px; }
.settings-grid.two-columns { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.theme-options { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.theme-option {
  min-height: 150px;
  padding: 14px;
  border: 2px solid var(--border);
  border-radius: 14px;
  background: var(--surface);
  color: var(--text);
  text-align: left;
  display: grid;
  align-content: start;
  gap: 7px;
}
.theme-option.selected { border-color: var(--gold); box-shadow: 0 0 0 3px rgba(245, 180, 0, .2); }
.theme-option small { color: var(--muted); line-height: 1.4; }
.theme-swatch {
  height: 48px;
  border-radius: 9px;
  border: 1px solid currentColor;
  overflow: hidden;
  display: grid;
  grid-template-columns: 28% 1fr;
  grid-template-rows: 1fr 1fr;
  margin-bottom: 3px;
}
.theme-swatch i:first-child { grid-row: 1 / 3; background: #111; }
.theme-light .theme-swatch i:nth-child(2) { background: #fff; }
.theme-light .theme-swatch i:nth-child(3) { background: #f5b400; }
.theme-dark .theme-swatch i:nth-child(2) { background: #1b1b1d; }
.theme-dark .theme-swatch i:nth-child(3) { background: #f5b400; }
.theme-high-contrast .theme-swatch { border-color: #ffd400; }
.theme-high-contrast .theme-swatch i:nth-child(2) { background: #000; }
.theme-high-contrast .theme-swatch i:nth-child(3) { background: #ffd400; }
.accessibility-preview,
.settings-info-box {
  min-height: 92px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface-subtle);
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 12px;
}
.accessibility-preview p,
.settings-info-box p { margin: 4px 0 0; color: var(--muted); line-height: 1.4; }
.settings-switches { display: grid; gap: 10px; margin-top: 18px; }
.settings-switch {
  padding: 13px 14px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
  display: flex;
  align-items: flex-start;
  gap: 12px;
  cursor: pointer;
}
.settings-switch input { width: 20px; min-height: 20px; margin: 2px 0 0; accent-color: var(--gold-dark); }
.settings-switch span { display: grid; gap: 3px; }
.settings-switch small { color: var(--muted); line-height: 1.4; }
.settings-actions { padding-top: 18px; border-top: 1px solid var(--border); }
.input-with-suffix { display: grid; grid-template-columns: 1fr auto; align-items: center; }
.input-with-suffix input { border-radius: 10px 0 0 10px; }
.input-with-suffix span {
  min-height: 42px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-left: 0;
  border-radius: 0 10px 10px 0;
  background: var(--surface-subtle);
  color: var(--muted);
}

@media (max-width: 850px) {
  .theme-options,
  .settings-grid.two-columns { grid-template-columns: 1fr; }
  .settings-heading { flex-direction: column; }
}
'''
path.write_text(text, encoding="utf-8")

print("Alterações de acessibilidade, configurações e usuários aplicadas.")

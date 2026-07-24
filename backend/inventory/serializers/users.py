from django.contrib.auth import get_user_model
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

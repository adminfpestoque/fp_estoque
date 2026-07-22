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
        fields = ["full_name", "cpf", "phone", "role", "active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate_cpf(self, value):
        return validate_cpf(value) if value else value


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(source="inventory_profile", read_only=True)
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
        read_only_fields = ["date_joined", "last_login", "profile"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def _profile_data(self, validated_data):
        return {
            "full_name": validated_data.pop("full_name", "").strip(),
            "cpf": validated_data.pop("cpf", None) or None,
            "phone": validated_data.pop("phone", ""),
            "role": validated_data.pop("role", UserProfile.OPERATOR),
            "active": validated_data.pop("profile_active", True),
        }

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password", None)
        profile_data = self._profile_data(validated_data)
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
        profile_updates = self._profile_data(validated_data)
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

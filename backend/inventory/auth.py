from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class EmailOrUsernameTokenSerializer(TokenObtainPairSerializer):
    """Permite autenticação com nome de usuário ou e-mail no mesmo campo."""

    def validate(self, attrs):
        identifier = (attrs.get(self.username_field) or "").strip()
        if identifier:
            user = get_user_model().objects.filter(email__iexact=identifier, is_active=True).first()
            if user:
                attrs[self.username_field] = user.get_username()
        data = super().validate(attrs)
        data["username"] = self.user.get_username()
        return data


class EmailOrUsernameTokenView(TokenObtainPairView):
    serializer_class = EmailOrUsernameTokenSerializer

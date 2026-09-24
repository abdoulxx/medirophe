from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import (
    CustomTokenBlacklistView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # Auth JWT : access courte durée + refresh avec rotation/blacklist.
    path("api/v1/auth/token/", CustomTokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("api/v1/auth/token/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),
    # "Logout" = blacklister le refresh token côté serveur (l'access token
    # reste valable jusqu'à expiration naturelle, ≤ 15 min).
    path("api/v1/auth/token/blacklist/", CustomTokenBlacklistView.as_view(), name="token-blacklist"),
    path("api/v1/auth/password-reset/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path(
        "api/v1/auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("api/v1/accounts/", include("apps.accounts.urls")),
    path("api/v1/audit/", include("apps.audit.urls")),
]

if settings.DEBUG:
    # Doc OpenAPI/Swagger : uniquement en dev (DEBUG=True). settings/prod.py
    # force DEBUG=False, donc ces 3 routes n'existent tout simplement pas en
    # production — pas besoin d'un flag séparé à oublier de désactiver.
    from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
        path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    ]

"""
Réinitialisation de mot de passe ("mot de passe oublié").

Réutilise `django.contrib.auth.tokens.PasswordResetTokenGenerator` — le même
mécanisme que le `PasswordResetView` intégré de Django — plutôt que
d'inventer un schéma de token : il est signé (HMAC, `SECRET_KEY`), à usage
unique de fait (le hash inclut le mot de passe courant de l'utilisateur, donc
toute réinitialisation ou changement de mot de passe invalide immédiatement
tous les tokens émis avant), et expire via `settings.PASSWORD_RESET_TIMEOUT`.
"""
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import User

token_generator = PasswordResetTokenGenerator()


def get_user_from_uid(uidb64):
    """Décode l'identifiant utilisateur transmis dans le lien de reset.
    Toute entrée malformée ou utilisateur introuvable renvoie None plutôt que
    de lever — l'appelant traite ça comme un token invalide, sans distinguer
    la cause (pas d'énumération de comptes via ce canal non plus)."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, ValidationError, User.DoesNotExist):
        return None


def send_password_reset_email(user):
    uid = urlsafe_base64_encode(force_bytes(str(user.pk)))
    token = token_generator.make_token(user)
    reset_url = f"{settings.FRONTEND_PASSWORD_RESET_URL}?uid={uid}&token={token}"

    send_mail(
        subject="MediRophe — Réinitialisation de votre mot de passe",
        message=(
            "Vous avez demandé la réinitialisation de votre mot de passe MediRophe.\n\n"
            f"{reset_url}\n\n"
            "Ce lien expire dans 1 heure et ne peut servir qu'une seule fois. "
            "Si vous n'êtes pas à l'origine de cette demande, ignorez cet email : "
            "votre mot de passe actuel reste valide."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

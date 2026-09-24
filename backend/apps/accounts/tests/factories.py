import factory

from apps.accounts.models import User
from apps.accounts.roles import Role

DEFAULT_PASSWORD = "Correct-Horse-Battery-Staple-9"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@medirophe.test")
    first_name = "Prénom"
    last_name = "Nom"
    role = Role.MEDECIN
    is_active = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or DEFAULT_PASSWORD)
        if create:
            self.save(update_fields=["password"])

import datetime

import factory

from apps.patients.models import Patient, Sexe


class PatientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Patient

    first_name = factory.Sequence(lambda n: f"Prénom{n}")
    last_name = factory.Sequence(lambda n: f"Nom{n}")
    date_naissance = datetime.date(1990, 1, 1)
    sexe = Sexe.FEMME

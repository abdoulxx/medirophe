import factory

from apps.patients.tests.factories import PatientFactory
from apps.prescriptions.models import CategorieExamen, Examen, Prescription


class ExamenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Examen

    code = factory.Sequence(lambda n: f"TST-{n:03d}")
    nom = factory.Sequence(lambda n: f"Examen test {n}")
    categorie = CategorieExamen.METABOLISME
    taux_cmu = 80
    prix_fcfa = 3000
    duree_estimee = "2h"


class PrescriptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Prescription

    patient = factory.SubFactory(PatientFactory)
    motif = "Suivi"

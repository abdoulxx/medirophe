import factory

from apps.consultations.models import Consultation, Service, ServiceCategorie
from apps.patients.tests.factories import PatientFactory


class ConsultationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Consultation

    patient = factory.SubFactory(PatientFactory)
    motif = "Douleur abdominale"


class ServiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Service

    categorie = ServiceCategorie.CLINIQUE
    nom = factory.Sequence(lambda n: f"Service test {n}")

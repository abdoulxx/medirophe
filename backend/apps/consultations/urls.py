from django.urls import path

from .views import ConsultationDetailView, ConsultationListView, ServiceListView

app_name = "consultations"

urlpatterns = [
    path("services/", ServiceListView.as_view(), name="service-list"),
    path("", ConsultationListView.as_view(), name="consultation-list"),
    path("<uuid:pk>/", ConsultationDetailView.as_view(), name="consultation-detail"),
]

from django.urls import path

from .views import PatientDetailView, PatientListView

app_name = "patients"

urlpatterns = [
    path("", PatientListView.as_view(), name="patient-list"),
    path("<uuid:pk>/", PatientDetailView.as_view(), name="patient-detail"),
]

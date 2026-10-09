from django.urls import path

from .views import ExamenListView, PrescriptionDetailView, PrescriptionListView

app_name = "prescriptions"

urlpatterns = [
    path("examens/", ExamenListView.as_view(), name="examen-list"),
    path("", PrescriptionListView.as_view(), name="prescription-list"),
    path("<uuid:pk>/", PrescriptionDetailView.as_view(), name="prescription-detail"),
]

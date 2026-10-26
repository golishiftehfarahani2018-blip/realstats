from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from core import views as v

urlpatterns = [
    path("api/v1/auth/csrf", v.CsrfView.as_view()),
    path("api/v1/auth/login", v.LoginView.as_view()),
    path("api/v1/auth/logout", v.LogoutView.as_view()),
    path("api/v1/me", v.MeView.as_view()),
    path("api/v1/advisors", v.AdvisorsView.as_view()),
    path("api/v1/advisors/<uuid:pk>", v.AdvisorStatusView.as_view()),
    path("api/v1/offerings", v.OfferingsView.as_view()),
    path("api/v1/offerings/<uuid:pk>", v.OfferingView.as_view()),
    path("api/v1/offerings/<uuid:pk>/submit", v.SubmitView.as_view()),
    path("api/v1/offerings/<uuid:pk>/review", v.ReviewView.as_view()),
    path("api/v1/offerings/<uuid:pk>/private", v.PrivateView.as_view()),
    path("api/v1/offerings/<uuid:pk>/documents", v.DocumentsView.as_view()),
    path(
        "api/v1/offerings/<uuid:pk>/documents/<uuid:doc_id>", v.DownloadView.as_view()
    ),
    path("api/v1/audit", v.AuditView.as_view()),
    path("api/schema/", SpectacularAPIView.as_view()),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
]
urlpatterns[-2] = path("api/schema/", SpectacularAPIView.as_view(), name="schema")

urlpatterns += [path("api/v1/", include("crm.urls"))]

urlpatterns += [path("api/v1/", include("business.urls"))]

from django.urls import path
from . import views as v

urlpatterns = [
    path("people", v.PeopleView.as_view()),
    path("people/<uuid:pk>/private", v.PersonContactView.as_view()),
    path("demands", v.DemandsView.as_view()),
    path("demands/<uuid:pk>", v.DemandView.as_view()),
    path("demands/<uuid:pk>/private", v.DemandContactView.as_view()),
    path("demands/<uuid:pk>/assign", v.DemandAssignView.as_view()),
    path("demands/<uuid:pk>/matches", v.MatchesView.as_view()),
    path("offerings/<uuid:pk>/assign", v.OfferingAssignView.as_view()),
    path("cooperations", v.CooperationsView.as_view()),
    path("cooperations/<uuid:pk>", v.CooperationView.as_view()),
    path("visits", v.VisitsView.as_view()),
    path("visits/<uuid:pk>", v.VisitView.as_view()),
    path("followups", v.FollowupsView.as_view()),
    path("followups/<uuid:pk>", v.FollowupView.as_view()),
    path("followups/<uuid:pk>/private", v.FollowupPrivateView.as_view()),
    path("notifications", v.NotificationsView.as_view()),
    path("notifications/<uuid:pk>", v.NotificationView.as_view()),
]

urlpatterns += [
    path("demands/<uuid:pk>/assignments", v.DemandAssignmentHistoryView.as_view()),
    path("offerings/<uuid:pk>/assignments", v.OfferingAssignmentHistoryView.as_view()),
]
urlpatterns += [
    path("cooperations/<uuid:pk>/history", v.CooperationHistoryView.as_view()),
    path("visits/<uuid:pk>/history", v.VisitHistoryView.as_view()),
]

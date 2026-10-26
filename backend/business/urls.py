from django.urls import path
from . import views as v
urlpatterns=[
 path('settings/office',v.SettingsView.as_view()),
 path('offerings/<uuid:pk>/revisions',v.RevisionsView.as_view()),
 path('revisions/<uuid:pk>/review',v.RevisionReview.as_view()),
 path('offerings/<uuid:pk>/publication',v.PublicationView.as_view()),
 path('public/listings',v.PublicList.as_view()),
 path('customer/me',v.CustomerSession.as_view()),
 path('customer/auth/<str:action>',v.CustomerSession.as_view()),
 path('customer/requests',v.CustomerRequests.as_view()),
 path('customer/favorites',v.Favorites.as_view()),
 path('customer/favorites/<uuid:pk>',v.Favorites.as_view()),
 path('customer-inbox',v.Inbox.as_view()),
 path('customer-inbox/<uuid:pk>',v.Inbox.as_view()),
 path('finance/members',v.Members.as_view()),
 path('finance/deals',v.Deals.as_view()),
 path('finance/deals/<uuid:pk>/<str:action>',v.DealAction.as_view()),
]
urlpatterns += [
 path('offerings/<uuid:pk>/public-images',v.PublicImages.as_view()),
 path('public/images/<uuid:pk>',v.PublicImageDownload.as_view()),
 path('invitations',v.Invitations.as_view()),
 path('invitations/<uuid:pk>',v.Invitations.as_view()),
 path('public/accept-invitation',v.AcceptInvitation.as_view()),
 path('reports/office',v.Reports.as_view()),
]
# Restrict methods per resource shape; unsupported combinations return 405.
class CustomerMe(v.CustomerSession): http_method_names=['get','head','options']
class CustomerAuth(v.CustomerSession): http_method_names=['post','options']
class FavoriteList(v.Favorites): http_method_names=['get','head','options']
class FavoriteItem(v.Favorites): http_method_names=['post','delete','options']
class InboxList(v.Inbox): http_method_names=['get','head','options']
class InboxItem(v.Inbox): http_method_names=['patch','options']
class InviteList(v.Invitations): http_method_names=['get','post','head','options']
class InviteItem(v.Invitations): http_method_names=['delete','options']
replacements={'customer/me':CustomerMe,'customer/auth/<str:action>':CustomerAuth,
 'customer/favorites':FavoriteList,'customer/favorites/<uuid:pk>':FavoriteItem,
 'customer-inbox':InboxList,'customer-inbox/<uuid:pk>':InboxItem,
 'invitations':InviteList,'invitations/<uuid:pk>':InviteItem}
urlpatterns=[path(str(p.pattern), replacements[str(p.pattern)].as_view()) if str(p.pattern) in replacements else p for p in urlpatterns]
urlpatterns += [path('public/offices',v.PublicOffices.as_view()),path('public/listings/<uuid:pk>',v.PublicDetail.as_view())]

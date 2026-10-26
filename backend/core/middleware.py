from django.contrib.auth import logout
from .models import Membership


class ActiveMembershipMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.membership = None
        if request.user.is_authenticated:
            request.membership = (
                Membership.objects.select_related("office")
                .filter(
                    id=request.session.get("membership_id"),
                    user=request.user,
                    active=True,
                    office__active=True,
                )
                .first()
            )
            if (
                not request.membership
                or not request.user.is_active
                or request.session.get("auth_epoch") != request.membership.auth_epoch
            ):
                logout(request)
        return self.get_response(request)


class NoStoreMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store, private"
            response["Vary"] = "Cookie"
        return response

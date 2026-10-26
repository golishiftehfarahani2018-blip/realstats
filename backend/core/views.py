import hashlib
from collections.abc import Mapping
from datetime import timedelta
from django.contrib.auth import authenticate, login, logout
from django.db import transaction, IntegrityError
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
    NotFound,
    Throttled,
)
from drf_spectacular.utils import extend_schema
from .models import Membership, User, AuditEvent, LoginAttempt, PrivateDocument
from . import services as s
from .serializers import (
    ActiveInput,
    AdvisorInput,
    DocumentInput,
    EditInput,
    LoginInput,
    OfferingInput,
    OfferingOutput,
    OfferingQuery,
    OfferingPage,
    PrivateOutput,
    ReviewInput,
    VersionInput,
    normalize,
)


def checked(cls, data):
    v = cls(data=data)
    v.is_valid(raise_exception=True)
    return v.validated_data


def member(request):
    m = request._request.membership
    if not m:
        raise PermissionDenied()
    return m


class CsrfView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response({"csrfToken": get_token(request._request)})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=LoginInput, responses={200: dict})
    def post(self, request):
        d = checked(LoginInput, request.data)
        key = hashlib.sha256(
            (request.META.get("REMOTE_ADDR", "") + "|" + d["username"]).encode()
        ).hexdigest()
        with transaction.atomic():
            attempt, _ = LoginAttempt.objects.get_or_create(
                key=key, defaults={"started_at": timezone.now()}
            )
            attempt = LoginAttempt.objects.select_for_update().get(pk=key)
            if attempt.started_at < timezone.now() - timedelta(minutes=15):
                attempt.count = 0
                attempt.started_at = timezone.now()
            if attempt.count >= 8:
                raise Throttled(wait=900)
            attempt.count += 1
            attempt.save()
        user = authenticate(request, **d)
        memberships = (
            Membership.objects.filter(user=user, active=True, office__active=True)
            if user
            else Membership.objects.none()
        )
        if memberships.count() != 1:
            raise PermissionDenied(
                "اطلاعات ورود معتبر نیست یا عضویت فعال یکتا وجود ندارد."
            )
        m = memberships.get()
        login(request._request, user)
        request.session["membership_id"] = str(m.id)
        request.session["auth_epoch"] = m.auth_epoch
        LoginAttempt.objects.filter(pk=key).delete()
        s.audit(m, "session.login")
        return Response({"ok": True, "csrfToken": get_token(request._request)})


class LogoutView(APIView):
    @extend_schema(request=None, responses={200: dict})
    def post(self, request):
        logout(request._request)
        return Response({"ok": True})


class MeView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request):
        m = member(request)
        return Response(
            {
                "username": request.user.username,
                "name": request.user.first_name,
                "role": m.role,
                "office_name": m.office.name,
                "branding": m.office.branding,
            }
        )


class AdvisorsView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request):
        m = member(request)
        s.manager(m)
        return Response(
            [
                {
                    "id": str(x.id),
                    "username": x.user.username,
                    "name": x.user.first_name,
                    "active": x.active,
                }
                for x in Membership.objects.select_related("user")
                .filter(office=m.office, organization=m.organization, role="advisor")
                .order_by("created_at")
            ]
        )

    @extend_schema(request=AdvisorInput, responses={201: dict})
    def post(self, request):
        m = member(request)
        s.manager(m)
        d = checked(AdvisorInput, request.data)
        try:
            with transaction.atomic():
                u = User.objects.create_user(**d)
                target = Membership.objects.create(
                    user=u, office=m.office, organization=m.organization, role="advisor"
                )
                s.audit(m, "membership.create", target.id)
        except IntegrityError:
            raise ValidationError("نام کاربری قابل استفاده نیست.")
        return Response({"id": str(target.id)}, status=201)


class AdvisorStatusView(APIView):
    @extend_schema(request=ActiveInput, responses={200: dict})
    def patch(self, request, pk):
        m = member(request)
        d = checked(ActiveInput, request.data)
        target = s.deactivate(m, pk, d["active"])
        return Response({"id": str(target.id), "active": target.active})


class OfferingsView(APIView):
    @extend_schema(
        operation_id="offerings_list", parameters=[OfferingQuery], responses={200: OfferingPage}
    )
    def get(self, request):
        m = member(request)
        qs = s.visible(m)
        data = checked(OfferingQuery, request.query_params.dict())
        if data.get('q'):
            qs = qs.filter(property__district__icontains=data['q'])
        for field, target in [('kind', 'property__kind'), ('transaction', 'transaction'), ('status', 'status')]:
            if field in data:
                qs = qs.filter(**{target: data[field]})
        for field, target in [('area', 'property__area'), ('price', 'price_toman'), ('deposit', 'deposit_toman'), ('rent', 'rent_toman')]:
            for suffix, lookup in [('min', 'gte'), ('max', 'lte')]:
                key = field+'_'+suffix
                if key in data:
                    qs = qs.filter(**{target+'__'+lookup: data[key]})
        if 'price_min' in data or 'price_max' in data:qs=qs.filter(negotiable_price=False)
        qs = qs.order_by('-created_at', 'id')
        if data.get('paginated') != '1':
            return Response([s.summary(o, m) for o in qs[:200]])
        offset, limit = data['offset'], data['limit']
        count = qs.count()
        return Response({'count': count, 'offset': offset, 'limit': limit,
                         'has_more': offset+limit < count,
                         'results': [s.summary(o, m) for o in qs[offset:offset+limit]]})

    @extend_schema(request=OfferingInput, responses={201: OfferingOutput})
    def post(self, request):
        m = member(request)
        if isinstance(request.data, Mapping) and set(request.data) - set(OfferingInput().fields):
            s.audit(m, "input.forbidden", outcome="denied")
        o = s.create_offering(m, checked(OfferingInput, request.data))
        return Response(s.summary(o, m), status=201)


class OfferingView(APIView):
    @extend_schema(responses={200: OfferingOutput})
    def get(self, request, pk):
        return Response(s.summary(s.get_offering(member(request), pk), member(request)))

    @extend_schema(request=EditInput, responses={200: OfferingOutput, 409: dict})
    def patch(self, request, pk):
        return Response(
            s.summary(
                s.change_offering(
                    member(request), pk, checked(EditInput, request.data), "edit"
                ),
                member(request),
            )
        )


class SubmitView(APIView):
    @extend_schema(request=VersionInput, responses={200: OfferingOutput, 409: dict})
    def post(self, request, pk):
        return Response(
            s.summary(
                s.change_offering(
                    member(request), pk, checked(VersionInput, request.data), "submit"
                ),
                member(request),
            )
        )


class ReviewView(APIView):
    @extend_schema(request=ReviewInput, responses={200: OfferingOutput, 409: dict})
    def post(self, request, pk):
        return Response(
            s.summary(
                s.change_offering(
                    member(request), pk, checked(ReviewInput, request.data), "review"
                ),
                member(request),
            )
        )


class PrivateView(APIView):
    @extend_schema(responses={200: PrivateOutput})
    def get(self, request, pk):
        return Response(s.private_details(member(request), pk))


class DocumentsView(APIView):
    @extend_schema(request=DocumentInput, responses={201: dict})
    def post(self, request, pk):
        from .storage import save_private

        m = member(request)
        o = s.get_offering(m, pk)
        if not s.private_allowed(m, o):
            raise PermissionDenied()
        f = checked(DocumentInput, request.data)["file"]
        key, ctype = save_private(f)
        doc = PrivateDocument.objects.create(
            organization=m.organization,
            office=m.office,
            offering=o,
            storage_key=key,
            content_type=ctype,
            size=f.size,
        )
        s.audit(m, "document.upload", o.id)
        return Response({"id": str(doc.id)}, status=201)

    @extend_schema(operation_id="private_documents_list", responses={200: dict})
    def get(self, request, pk):
        m = member(request)
        o = s.get_offering(m, pk)
        if not s.private_allowed(m, o):
            raise PermissionDenied()
        return Response(
            [
                {"id": str(x.id), "size": x.size, "content_type": x.content_type}
                for x in PrivateDocument.objects.filter(
                    offering=o, office=m.office, organization=m.organization
                )
            ]
        )


class DownloadView(APIView):
    @extend_schema(responses={200: bytes})
    def get(self, request, pk, doc_id):
        from .storage import download_private

        m = member(request)
        o = s.get_offering(m, pk)
        if not s.private_allowed(m, o):
            s.audit(m, "document.view", o.id, "denied")
            raise PermissionDenied()
        try:
            doc = PrivateDocument.objects.get(
                pk=doc_id, offering=o, office=m.office, organization=m.organization
            )
        except PrivateDocument.DoesNotExist:
            raise NotFound()
        response = download_private(doc)
        s.audit(m, "document.view", o.id)
        return response


class AuditView(APIView):
    @extend_schema(responses={200: dict})
    def get(self, request):
        m = member(request)
        s.manager(m)
        return Response(
            list(
                AuditEvent.objects.filter(office=m.office, organization=m.organization)
                .order_by("-created_at")
                .values(
                    "id", "actor_id", "action", "record_id", "outcome", "created_at"
                )[:200]
            )
        )

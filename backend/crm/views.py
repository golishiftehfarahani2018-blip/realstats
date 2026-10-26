from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from core.views import member, checked
from core.serializers import VersionInput, OfferingOutput
from core import services as core
from . import people, services as s
from .serializers import (
    PersonInput,
    DemandInput,
    DemandEditInput,
    DemandOutput,
    AssignInput,
    CooperationInput,
    CooperationDecision,
    CooperationOutput,
    VisitInput,
    VisitEditInput,
    VisitOutput,
    FollowUpInput,
)

from .serializers import (
    PersonOutput,
    ContactOutput,
    FollowUpOutput,
    NoteOutput,
    NotificationOutput,
    PersonPage,
    DemandPage,
    MatchPage,
    CooperationPage,
    VisitPage,
    FollowUpPage,
    NotificationPage,
)


def page(qs, request, mapper):
    # Bounded pagination; never search private text or return record counts outside the scoped queryset.
    from rest_framework import serializers

    offset = serializers.IntegerField(min_value=0).run_validation(
        request.query_params.get("offset", 0)
    )
    limit = serializers.IntegerField(min_value=1, max_value=100).run_validation(
        request.query_params.get("limit", 30)
    )
    count = qs.count()
    return {
        "count": count,
        "offset": offset,
        "limit": limit,
        "results": [
            mapper(x) for x in qs.order_by("-created_at", "id")[offset : offset + limit]
        ],
        "has_more": offset + limit < count,
    }


class CRMView(APIView):
    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        m = getattr(self.request._request, "membership", None)
        if m and response.status_code in [400, 403, 404]:
            core.audit(m, "crm.request.denied", outcome="denied")
        return response


class PeopleView(CRMView):
    @extend_schema(operation_id="people_list", responses={200: PersonPage})
    def get(self, r):
        m = member(r)
        return Response(
            page(people.people_visible(m), r, lambda p: people.person_summary(m, p))
        )

    @extend_schema(request=PersonInput, responses={201: PersonOutput, 409: dict})
    def post(self, r):
        m = member(r)
        d = checked(PersonInput, r.data)
        s.active_actor(m)
        p = people.resolve_person(m, d["name"], d["phone"], "applicant")
        return Response(people.person_summary(m, p), status=201)


class PersonContactView(CRMView):
    @extend_schema(responses={200: ContactOutput})
    def get(self, r, pk):
        return Response(people.contact(member(r), pk))


class DemandsView(CRMView):
    @extend_schema(operation_id="demands_list", responses={200: DemandPage})
    def get(self, r):
        m = member(r)
        return Response(page(s.demands(m), r, lambda d: s.demand_summary(m, d)))

    @extend_schema(request=DemandInput, responses={201: DemandOutput, 409: dict})
    def post(self, r):
        m = member(r)
        return Response(s.demand_summary(m, s.create_demand(m, r.data)), status=201)


class DemandView(CRMView):
    @extend_schema(responses={200: DemandOutput})
    def get(self, r, pk):
        m = member(r)
        return Response(s.demand_summary(m, s.demand_for(m, pk)))

    @extend_schema(request=DemandEditInput, responses={200: DemandOutput, 409: dict})
    def patch(self, r, pk):
        m = member(r)
        return Response(s.demand_summary(m, s.edit_demand(m, pk, r.data)))


class DemandContactView(CRMView):
    @extend_schema(responses={200: ContactOutput})
    def get(self, r, pk):
        return Response(s.demand_contact(member(r), pk))


class DemandAssignView(CRMView):
    @extend_schema(request=AssignInput, responses={200: DemandOutput, 409: dict})
    def post(self, r, pk):
        m = member(r)
        return Response(s.demand_summary(m, s.assign_target(m, r.data, demand_id=pk)))


class OfferingAssignView(CRMView):
    @extend_schema(request=AssignInput, responses={200: OfferingOutput, 409: dict})
    def post(self, r, pk):
        m = member(r)
        return Response(core.summary(s.assign_target(m, r.data, offering_id=pk), m))


class MatchesView(CRMView):
    @extend_schema(
        responses={200: MatchPage},
        parameters=[OpenApiParameter("offset", int), OpenApiParameter("limit", int)],
    )
    def get(self, r, pk):
        from rest_framework import serializers

        offset = serializers.IntegerField(min_value=0).run_validation(
            r.query_params.get("offset", 0)
        )
        limit = serializers.IntegerField(min_value=1, max_value=100).run_validation(
            r.query_params.get("limit", 30)
        )
        results = s.matches(member(r), pk)
        return Response(
            {
                "results": results[offset : offset + limit],
                "count": len(results),
                "has_more": offset + limit < len(results),
                "offset": offset,
                "limit": limit,
                "candidate_limit": 1000,
            }
        )


class CooperationsView(CRMView):
    @extend_schema(operation_id="cooperations_list", responses={200: CooperationPage})
    def get(self, r):
        m = member(r)
        return Response(
            page(s.cooperations(m), r, lambda c: s.cooperation_summary(m, c))
        )

    @extend_schema(
        request=CooperationInput,
        responses={200: CooperationOutput, 201: CooperationOutput},
    )
    def post(self, r):
        m = member(r)
        c, created = s.request_cooperation(m, r.data)
        return Response(s.cooperation_summary(m, c), status=201 if created else 200)


class CooperationView(CRMView):
    @extend_schema(responses={200: CooperationOutput})
    def get(self, r, pk):
        m = member(r)
        return Response(s.cooperation_summary(m, s.cooperation_for(m, pk)))

    @extend_schema(
        request=CooperationDecision, responses={200: CooperationOutput, 409: dict}
    )
    def patch(self, r, pk):
        m = member(r)
        return Response(s.cooperation_summary(m, s.decide_cooperation(m, pk, r.data)))


class VisitsView(CRMView):
    @extend_schema(operation_id="visits_list", responses={200: VisitPage})
    def get(self, r):
        m = member(r)
        return Response(page(s.visits(m), r, lambda v: s.visit_summary(m, v)))

    @extend_schema(request=VisitInput, responses={201: VisitOutput, 409: dict})
    def post(self, r):
        m = member(r)
        return Response(s.visit_summary(m, s.create_visit(m, r.data)), status=201)


class VisitView(CRMView):
    @extend_schema(responses={200: VisitOutput})
    def get(self, r, pk):
        m = member(r)
        return Response(s.visit_summary(m, s.fetch(s.visits(m), pk)))

    @extend_schema(request=VisitEditInput, responses={200: VisitOutput, 409: dict})
    def patch(self, r, pk):
        m = member(r)
        return Response(s.visit_summary(m, s.change_visit(m, pk, r.data)))


class FollowupsView(CRMView):
    @extend_schema(operation_id="followups_list", responses={200: FollowUpPage})
    def get(self, r):
        m = member(r)
        qs = s.followups(m)
        if r.query_params.get("due") == "1":
            qs = qs.filter(completed_at__isnull=True, due_at__lte=s.timezone.now())
        return Response(page(qs, r, s.followup_summary))

    @extend_schema(request=FollowUpInput, responses={201: FollowUpOutput})
    def post(self, r):
        return Response(
            s.followup_summary(s.create_followup(member(r), r.data)), status=201
        )


class FollowupView(CRMView):
    @extend_schema(responses={200: FollowUpOutput})
    def get(self, r, pk):
        return Response(s.followup_summary(s.fetch(s.followups(member(r)), pk)))

    @extend_schema(request=VersionInput, responses={200: FollowUpOutput, 409: dict})
    def patch(self, r, pk):
        d = checked(VersionInput, r.data)
        return Response(
            s.followup_summary(s.complete_followup(member(r), pk, d["version"]))
        )


class FollowupPrivateView(CRMView):
    @extend_schema(responses={200: NoteOutput})
    def get(self, r, pk):
        return Response(s.followup_private(member(r), pk))


class NotificationsView(CRMView):
    @extend_schema(operation_id="notifications_list", responses={200: NotificationPage})
    def get(self, r):
        return Response(page(s.notifications(member(r)), r, s.notification_summary))


class NotificationView(CRMView):
    @extend_schema(request=None, responses={200: NotificationOutput})
    def patch(self, r, pk):
        if r.data:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("بدنه درخواست باید خالی باشد.")
        return Response(s.notification_summary(s.read_notification(member(r), pk)))


class DemandAssignmentHistoryView(CRMView):
    @extend_schema(responses={200: dict})
    def get(self, r, pk):
        return Response(s.assignment_history(member(r), pk, "demand"))


class OfferingAssignmentHistoryView(CRMView):
    @extend_schema(responses={200: dict})
    def get(self, r, pk):
        return Response(s.assignment_history(member(r), pk, "offering"))


class CooperationHistoryView(CRMView):
    @extend_schema(responses={200: dict})
    def get(self, r, pk):
        return Response(s.workflow_history(member(r), pk, "cooperation"))


class VisitHistoryView(CRMView):
    @extend_schema(responses={200: dict})
    def get(self, r, pk):
        return Response(s.workflow_history(member(r), pk, "visit"))

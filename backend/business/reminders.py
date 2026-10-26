from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from crm.models import FollowUp, Cooperation, Notification
from core.models import Membership
from .models import ReminderSent, OfficeSettings


def deliver(record,recipient,code,kind):
    with transaction.atomic():
        _,created=ReminderSent.objects.get_or_create(recipient=recipient,record_id=record.id,event_code=code,
            defaults={'office_id':record.office_id,'organization_id':record.organization_id})
        if created:
            Notification.objects.create(office_id=record.office_id,organization_id=record.organization_id,
                recipient=recipient,event_code=code,record_type=kind,record_id=record.id)
    return int(created)


def run():
    count=0;now=timezone.now()
    for record in FollowUp.objects.select_related('author').filter(completed_at=None,due_at__lte=now,author__active=True,author__user__is_active=True,office__active=True).iterator():
        count+=deliver(record,record.author,'followup.due','followup')
    for settings in OfficeSettings.objects.filter(response_hours__gt=0,office__active=True).iterator():
        for record in Cooperation.objects.filter(office=settings.office,status='requested',created_at__lte=now-timedelta(hours=settings.response_hours)).iterator():
            for recipient in Membership.objects.filter(office=settings.office,organization_id=record.organization_id,role='manager',active=True,user__is_active=True):
                count+=deliver(record,recipient,'cooperation.overdue','cooperation')
    return count

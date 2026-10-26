import time
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from business.reminders import run
class Command(BaseCommand):
    help='Send idempotent internal reminders; no SMS or external messages.'
    def add_arguments(self,p):p.add_argument('--once',action='store_true')
    def handle(self,*args,**options):
        while True:
            close_old_connections()
            self.stdout.write('Internal reminders delivered: '+str(run()))
            if options['once']:return
            time.sleep(60)

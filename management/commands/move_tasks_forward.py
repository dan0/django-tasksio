from datetime import date
from django.core.management.base import BaseCommand, CommandError
from apps.tasks.models import Task

class Command(BaseCommand):
    args = 'none'
    help = ''
    
    def handle(self, *args, **options):
        
        for task in Task.objects.filter(completed=None).filter(date__lt=date.today()).filter(date__gt=date(1983, 8, 9)):
            task.date=date.today()
            task.save()
            
            
            

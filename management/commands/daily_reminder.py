from datetime import date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from apps.tasks.models import Task



class Command(BaseCommand):
    args = 'none'
    help = 'Performs uptime check of all monitored sites'
    
    def handle(self, *args, **options):
        
        eligible_users = User.objects.exclude(username='root').exclude(username='admin')
        
        for user in eligible_users:
            
            todays_tasks = Task.objects.filter(assigned_to=user).filter(date=date.today()).filter(completed=None)
            
            if(user.email and len(todays_tasks) > 0):
            
                subject, from_email, to = '[tasks.io] Todays tasks', 'noreply@tasks.io', user.email

                html_content = render_to_string('email_reminder.html', {'user':user,'tasks':todays_tasks})
                text_content = strip_tags(html_content) # this strips the html, so people will have the text as well.

                # create the email, and attach the HTML version as well.
                msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
                msg.attach_alternative(html_content, "text/html")
                msg.send()
            
            
            
        
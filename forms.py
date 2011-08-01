from django.forms import ModelForm
from django.contrib.auth.models import User

from apps.tasks.models import *


class TaskForm(ModelForm):
    class Meta:
        model = Task
        fields = ('name', 'hours_forecast', 'assigned_to', 'date')


class UserForm(ModelForm):
    class Meta:
        model = User
        

class UserEditForm(ModelForm):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')


class UserProfileForm(ModelForm):
    class Meta:
        model = UserProfile
        exclude = ('user')
        
        
class BulletinEditForm(ModelForm):
    class Meta:
        model = Bulletin            
        
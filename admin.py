from django.contrib import admin
from apps.tasks.models import *


class TaskTypeAdmin(admin.ModelAdmin):  
    pass

class TaskAdmin(admin.ModelAdmin):  
    pass

class UserProfileAdmin(admin.ModelAdmin):   
    pass
    
class ClientAdmin(admin.ModelAdmin):
    pass
    
class ProjectAdmin(admin.ModelAdmin):
    pass
    
class BulletinAdmin(admin.ModelAdmin):
    pass


#admin.site.register(TaskType, TaskTypeAdmin)    
admin.site.register(Task, TaskAdmin)
#admin.site.register(UserProfile, UserProfileAdmin)
#admin.site.register(Client, ClientAdmin)
#admin.site.register(Project, ProjectAdmin)
admin.site.register(Bulletin, BulletinAdmin)
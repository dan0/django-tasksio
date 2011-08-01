from django.db import models
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify


class Task(models.Model):
    """
    A single task, thing to do

    
    also records harvest information
    """
    name = models.CharField(max_length=255)
    notes = models.TextField(blank=True, null=True)
    date = models.DateField()
    #time
    hours_forecast = models.FloatField(blank=True, null=True)
    hours_recorded = models.FloatField(blank=True, null=True)
    completed = models.DateTimeField(blank=True, null=True)
    #harvest
    harvested = models.DateTimeField(blank=True, null=True)
    harvest_item_id = models.IntegerField(blank=True, null=True, unique=True)
    #meta
    tasktype = models.ForeignKey('TaskType', blank=True, null=True)
    project = models.ForeignKey('Project', blank=True, null=True)
    order = models.IntegerField(unique=False,blank=True, null=True, default=0)
    priority = models.IntegerField(blank=True, null=True, default=0)
    
    client = models.ForeignKey('Client', blank=True, null=True)
    assigned_to = models.ForeignKey(User, related_name='assigned', blank=True, null=True)
    created_by = models.ForeignKey(User,blank=True, null=True)
    
    class Meta:
        ordering = ('date','order','-id')

    def __unicode__(self):
        return self.name


class UserProfile(models.Model):
    """
    An extension of the user model, 
    allowing for profile information
    """
    site_colour = models.CharField(blank=True, null=True, max_length=255)
    tag_colour = models.CharField(blank=True, null=True, max_length=255)
    user = models.ForeignKey(User, unique=True)
    harvest_user = models.CharField(blank=True, max_length=255)
    harvest_pass = models.CharField(blank=True, max_length=255)
    
    home_address = models.TextField(blank=True, null=True)
    phone_number = models.BigIntegerField(blank=True, null=True)
    receive_text_alerts = models.BooleanField(default=True)
    
    def __unicode__(self):
        return self.user.username
        

class Client(models.Model):
    """Client Model"""
    
    name = models.CharField(unique=True, max_length=255)
    harvest_id = models.IntegerField(unique=True, blank=True, null=True)
    details = models.TextField(blank=True)
    slug = models.SlugField(unique=True,null=True, max_length=250)
    
    # contact info
    contact_name = models.CharField(blank=True, null=True, max_length=100)
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(blank=True, null=True, max_length=100)
    
    # address
    address1 = models.CharField(blank=True, null=True, max_length=100)
    address2 = models.CharField(blank=True, null=True, max_length=100)
    city = models.CharField(blank=True, null=True, max_length=100)
    county = models.CharField(blank=True, null=True, max_length=100)
    postcode = models.CharField(blank=True, null=True, max_length=100)
    
    # support
    supported = models.BooleanField(default=False)
    support_type = models.ForeignKey('websites.SupportType', null=True, blank=True)

    class Meta:
        ordering = ['name']

    def save(self, force_insert=False, force_update=False):
        self.slug = slugify(self.name) #TODO - catch integrityerror when duplicate slug.
        super(Client, self).save(force_insert, force_update)
        
    def __unicode__(self):
        return self.name


class Project(models.Model):
    """Project Model"""

    name = models.CharField(max_length=255)
    harvest_id = models.IntegerField(unique=True, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    client = models.ForeignKey('Client',to_field='harvest_id')
    
    def __unicode__(self):
        return self.name
        

class TaskType(models.Model):
    """Task type Model"""

    name = models.CharField(max_length=255)
    harvest_id = models.IntegerField(unique=True, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    projects = models.ManyToManyField('Project')

    class Meta:
        ordering = ('name','id')

    def __unicode__(self):
        return self.name
        

class Bulletin(models.Model):
    """Messages for all users"""
    messages = models.TextField(blank=True,null=True)
    updated = models.DateTimeField(auto_now=True,auto_now_add=True, blank=True)
                
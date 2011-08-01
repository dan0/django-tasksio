from datetime import date, timedelta, datetime
from urllib2 import Request, urlopen, HTTPError
from base64 import b64encode
from calendar import monthrange
from math import ceil

from django.template import RequestContext 
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from django.db.models import Sum
from django.core.mail import send_mail
from django.utils import simplejson
from django.utils.safestring import mark_safe
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib.sessions.models import Session
from django.views.decorators.csrf import csrf_exempt

from apps.tasks.models import *
from apps.tasks.forms import *
import settings
from utils.jsondump import dumps
from utils.workcalendar import workflow_calendar
from utils.dates import get_week_dates
from harvest import Harvest

#TODO: Clean up, add error checking and correct return data
@login_required
def task_list(request, year=None, month=None, day=None):    
    """
        Get the main weekly view of tasks
        
        the section for getting user time allotment
        data could be moved into it's own function
        if performance becomes an issue
    """
    try:
        iso_cal = date.isocalendar(date(int(year), int(month), int(day) ))
    except:
        iso_cal = date.isocalendar(date.today())
           
    week_dates = get_week_dates(iso_cal[0],iso_cal[1])
    start_date = week_dates[0]
    end_date = week_dates[1]
    next_week = start_date + timedelta(days = 7)
    last_week = start_date - timedelta(days = 7)
    showing = request.COOKIES.get('tasksio_hiding', False)
    if(showing):
        showing = showing.split('%7C')
    
    users = User.objects.exclude(username='root').exclude(username='admin').order_by('username')
    days = []
    daily_user_hours = []
    future_tasks = []
    future_task_date = date(1982, 8, 9)  #aribtrary date for future tasks
    future_tasks_end_date = future_task_date + timedelta(days = 4)
    
    bulletins = None
    bulletin = None
    bulletin = Bulletin.objects.all().order_by('-updated')[:1]
    if bulletin and str(bulletin[0].messages) != '':
        bulletins = {'id':bulletin[0].id,'messages_raw':bulletin[0].messages,
                    'messages':bulletin[0].messages.split('|')}
    
    while future_tasks_end_date is None or future_task_date <= future_tasks_end_date:
        future_tasks.append({'date':future_task_date,'tasks':Task.objects.filter(
                                                        date=future_task_date)})
        future_task_date = future_task_date + timedelta(days = 1)
    
    while end_date is None or start_date <= end_date:
        user_hours = []
        raw_tasks = Task.objects.filter(date=start_date)
        for user in users:
            hourtasks = Task.objects.filter(date=start_date).filter(assigned_to=user).aggregate(Sum('hours_forecast'))
            user_hours.append({'user':user,'hours':hourtasks})
                
        delta = 'future'
        if start_date == date.today():
            delta = 'today'
        elif start_date < date.today():
            delta = 'past'
        days.append({'date':start_date,'delta':delta,'user_hours':user_hours,
                                'tasks':Task.objects.filter(date=start_date)})
        start_date = start_date + timedelta(days = 1)
        
            
    return render_to_response('tasks/task_list.html', 
                            { 'days': days,'week_start':start_date, 'showing': showing, 'last_week':last_week,'next_week':next_week,'users':users, 
                                    'future_tasks':future_tasks,'bulletins':bulletins },
                                    context_instance = RequestContext(request))


def month_table(request, year=None, month=None):
    """Get a monthly workload view"""
    today = datetime.now()
    if year:
        year = int(year)
    else:
        year = today.year
        
    if month:
        month = int(month)
    else:
        month = today.month
    
    cal_month = datetime(year, month, 1)
    month_days = monthrange(year, month)
    month_start = date(year, month, month_days[0])
    month_end = date(year, month, month_days[1])
    showing = request.COOKIES.get('tasksio_hiding', False)
    if(showing):
        showing = showing.split('%7C')

    calendar = workflow_calendar().formatmonth(year, month)
    
    return render_to_response('tasks/month_cal.html',{'start':month_start,'end':month_end,'showing':showing,
                                            'users':User.objects.exclude(username='root').exclude(username='admin'),
                                            'calendar':mark_safe(calendar)},context_instance = RequestContext(request)) 


def tasks_for_day(request):
    """
        Get the task list for a single day
        used to auto-update the 
    """
    tasks = None
    if request.method == 'POST':
        today = date(int(request.POST['year']), int(request.POST['month']), int(request.POST['day']))
        tasks = Task.objects.filter(date=today)
    return render_to_response('tasks/task_day_list.html',{'tasks':tasks},context_instance = RequestContext(request)) 

                          
@login_required                           
@csrf_exempt                     
def task_add(request):
    if request.method == 'POST':
        f = TaskForm(request.POST)
        if f.is_valid():
            new_task = f.save(commit=False)
            new_task.created_by = request.user
            new_task.save()
            try:
                send_email = request.POST['send_email']
            except Exception, e:
                send_email = None
            if send_email:
                if new_task.assigned_to.email:
                    mail_subject = "[tasks.io] New task assigned to you: " + new_task.name
                    mail_body = new_task.name
                    mail_body += "\n\nGo to http://tasks.io when you're done and harvest it./"
                    send_mail(mail_subject, mail_body, settings.EMAIL_FROM,
                        [new_task.assigned_to.email], fail_silently=False)
            if request.is_ajax():
                response = [{"success":True, "id":new_task.id}]
                return HttpResponse(simplejson.dumps(response,indent=2, ensure_ascii=False),mimetype='application/json')
            else:
                return HttpResponseRedirect("/")
        else:
            errors = f.errors
            f = TaskForm()
            response = [{"success":False,"errors":errors}]
        return HttpResponse(simplejson.dumps(response,indent=2, ensure_ascii=False),mimetype='application/json')
    else:
        HttpResponseForbidden("Ajax only...")
    #Todo: Return proper validation errors in json format, get rid of this shit
    return HttpResponseRedirect("/?error=1")   


@login_required  
@csrf_exempt
def task_edit(request, taskid):
    t = Task.objects.get(id=taskid)
    if request.method == 'POST' and request.is_ajax():
        f = TaskForm(request.POST, instance=t)
        if f.is_valid():
            edited_task = f.save()
            try:
                send_email = request.POST['send_email']
            except Exception, e:
                send_email = None
            if send_email:
                if edited_task.assigned_to.email:
                    mail_subject = "You've got a task! : " + edited_task.name
                    mail_body = edited_task.name 
                    mail_body += "\n\nGo to http://geckotasks.djangy.com when you're done and harvest it!/"
                    send_mail(mail_subject, mail_body, settings.EMAIL_FROM,
                        [edited_task.assigned_to.email], fail_silently=False)
            # Has this been harvested already?
            harvested = t.harvested
            if not harvested:
                harvested = False
            else:
                harvested = harvested.strftime("%d/%m/%y")
            
            # is it complete?
            completed = t.completed
            if not completed:
                completed = False
            else:
                completed = True
            response = [{"success":True, "id":taskid, 'harvested':harvested,'completed':completed}]
        else:
            errors = f.errors
            f = TaskForm(instance=t)
            response = [{"success":False,"errors":errors}]
        return HttpResponse(simplejson.dumps(response,indent=2, ensure_ascii=False),mimetype='application/json')
    else:
        return HttpResponseForbidden("Ajax only...")
    #Todo: Return proper validation errors in json format, get rid of this shit
    return HttpResponseRedirect("/?error=1")


@login_required
def task_delete(request, taskid):
    t = Task.objects.get(id=taskid)
    if request.method == 'POST' and request.is_ajax():
        t.delete()
        response = {'success':True}
        return HttpResponse(simplejson.dumps(response,indent=2, ensure_ascii=False),mimetype='application/json')
    else:
        return HttpResponseForbidden("Ajax only...")
    return HttpResponseRedirect("/?error=1")
    

@login_required 
def move_tasks_to_today(request):
    """
        Until cronjobs come to Djangy,
        this view moves old unfinished tasks to today
    """
    for task in Task.objects.filter(completed=None).filter(date__lt=date.today()).filter(date__gt=date(1983, 8, 9)):
        task.date=date.today()
        task.save()
    return HttpResponseRedirect("/")


@login_required         
def bulletin_edit(request,bulletin_id):
    b = Bulletin.objects.get(id=bulletin_id)
    if request.method == 'POST':
        b = BulletinEditForm(request.POST, instance=b)
        if b.is_valid():
            b.save()
            return HttpResponseRedirect("/")
    
    return HttpResponseRedirect("/?error=1")


def user_time_list(request, start, end):
    """
        returns (in json format) an object for each day
        in the given range containing the amount of time
        allotted to each user
    """
    pass


@login_required  
def post_to_harvest(request, **kwargs):
    """
       Send to harvest, save updated task information
    """ 
    url = 'https://geckonm.harvestapp.com/daily/add'
    user_profile = False
    harvest_user = settings.HARVEST_USER
    harvest_pass = settings.HARVEST_PASS
    try:
        user_profile = request.user.get_profile()
    except:
        #TODO urgh - catch and report to user that the need to update their profile
        user_profile = False
    if user_profile:
        #TODO: what if they've entered a username but not pass or vice versa?
        #sort it out!
        if user_profile.harvest_user:
            harvest_user = user_profile.harvest_user
        if user_profile.harvest_pass:
            harvest_pass = user_profile.harvest_pass
    headers={
        'Authorization':'Basic '+b64encode('%s:%s' % (harvest_user,harvest_pass)),
        'Accept':'application/json',
        'Content-Type':'application/json',
        'User-Agent':'harvest.py',
    }
    #TODO - error checking
    task_id = request.POST['taskid']
    notes = request.POST['notes']
    hours = request.POST['hours']
    pid = request.POST['pid']
    harvest_tid = request.POST['tid']
    spentat = request.POST['spentat']
    #Save changes locally before posting to harvest
    task = Task.objects.get(id=task_id)
    task.harvested = datetime.now()
    task.project = Project.objects.get(harvest_id=pid)
    task.tasktype = TaskType.objects.get(harvest_id=harvest_tid)
    task.hours_recorded = hours
    task.notes = notes
    task.save()
    
    #postData = {'notes':'This is a note','hours':3,'project_id':180659,'task_id':184048,'spent_at':'Sun, 28 Nov 2010'}
    postData = {'notes':notes,'hours':hours,'project_id':pid,'task_id':harvest_tid,'spent_at':spentat}
    postData = simplejson.dumps(postData,indent=2)
    
    request = Request(url,postData,headers)
    try:
        response = urlopen(request)
        returnData = [{'code':response.getcode()}]
    except HTTPError, e:
        returnData = [{'code':e.code}]
    return HttpResponse(simplejson.dumps(returnData,indent=2, ensure_ascii=False),mimetype='application/json')
    

@login_required    
@csrf_exempt
def task_toggle_complete(request, taskid):
    """docstring for task_toggle_complete"""
    t = Task.objects.get(id=taskid)
    if request.method == 'POST' and request.is_ajax():
        #complete task?
        iscomplete = 0;
        try:
            iscomplete = int(request.POST['completed'])
        except:
            pass
        if (iscomplete == 1):
            t.completed = datetime.now();
            iscomplete = True;
        if (iscomplete == 0):
            t.completed = None
            iscomplete = False
        t.save()
        response = [{"success":True, "id":taskid, "completed":iscomplete}]
        return HttpResponse(simplejson.dumps(response,indent=2, ensure_ascii=False),mimetype='application/json')
    else:
        HttpResponseForbidden("Ajax only...")
    #Todo: Return proper validation errors in json format, get rid of this shit
    return HttpResponseRedirect("/?error=1")


@login_required  
@csrf_exempt
def task_set_harvested(request, taskid):
    """Set a single task as having been harvested"""
    t = Task.objects.get(id=taskid)
    if request.method == 'POST' and request.is_ajax():
        t.harvested = datetime.now()
        t.save()
        response = [{"success":True, "id":taskid,}]
        return HttpResponse(simplejson.dumps(response,indent=2, ensure_ascii=False),mimetype='application/json')
    #Todo: Return proper validation errors in json format, get rid of this shit
    return HttpResponseRedirect("/?error=1")    


@login_required  
@csrf_exempt
def task_reorder(request):
    """ajax reordering of tasks"""
    if request.method == 'POST' and request.is_ajax():
        tasks = request.POST.getlist('task[]')
        order_year = int(request.REQUEST['year'])
        order_month = int(request.REQUEST['month'])
        order_day = int(request.REQUEST['day'])
        i = 0;
        response = []
        for task in tasks:
            item = Task.objects.get(id=task)
            item.order = i;
            #item.date = time.strptime('26/11/2010','%d/%m/%Y');
            item.date = date(year=order_year, month=order_month, day=order_day)
            item.save()
            i = i + 1;
        return HttpResponse(simplejson.dumps(response,indent=2, ensure_ascii=False),mimetype='application/json')
    else:
        HttpResponseForbidden("Ajax only...")
    #Todo: Return proper validation errors in json format, get rid of this shit
    return HttpResponseRedirect("/?error=1")
        

@login_required  
def get_harvest_clients(request):
    """
        Import new clients from harvest
    
        sequence 1/3
    """
    h = Harvest( settings.HARVEST_ADDRESS, settings.HARVEST_USER, settings.HARVEST_PASS )
    response = []
    for hclient in h.clients():
        try:
            c = Client.objects.get(harvest_id=hclient.id)
            response.append({'harvest_id':hclient.id,'name':c.name,'status':'skipped'})
        except:
            c = Client(harvest_id=hclient.id,name=hclient.name, details=hclient.details)
            response.append({'harvest_id':hclient.id,'name':hclient.name,'status':'added'})
        c.save()
    return HttpResponse(simplejson.dumps(response,indent=2, ensure_ascii=False),mimetype='application/json')
    

@login_required  
def update_harvest_projects(request):    
    """
        Update all projects from harvest.
        
        sequence 2/3
    """
    response = []
    h = Harvest( settings.HARVEST_ADDRESS, settings.HARVEST_USER, settings.HARVEST_PASS )
    for hproject in h.projects():
        existing = False
        try:
            p = Project.objects.get(harvest_id=hproject.id)
            response.append({'harvest_id':hproject.id,'name':p.name,'status':'skipped'})
            existing = True
        except:
            p = Project(harvest_id=hproject.id,name=hproject.name, notes=hproject.notes, client=Client.objects.get(harvest_id=hproject.client_id))
            response.append({'harvest_id':hproject.id,'name':hproject.name,'status':'added'})
        
        p.save()  
        
        if not existing:
            # get task assignments per project
            for assignment in hproject.task_assignments:
                try:
                    t = TaskType.objects.get(harvest_id=assignment.task_id)
                except:
                    t = TaskType(harvest_id=assignment.task_id)
                t.save()
                t.projects.add(p)
                response.append({"tasktype":assignment.task_id, "created":True})
                #time.sleep(5)
    return HttpResponse(simplejson.dumps(response,indent=2, ensure_ascii=False),mimetype='application/json') 


@login_required    
def update_harvest_tasks(request):    
    """
        Update all tasks from harvest.

        This isn't particularly big or clever,
        needs to watch out for api rate limit
        (15 reqs per 40 secs)
        
        sequence 3/3
    """
    response = []
    h = Harvest( settings.HARVEST_ADDRESS, settings.HARVEST_USER, settings.HARVEST_PASS )
    for htask in h.tasks():
        try:
            t = TaskType.objects.get(harvest_id=htask.id)
            t.name = htask.name
            response.append({'harvest_id':htask.id,'name':htask.name,'status':'updated'})
        except:
            TaskType(harvest_id=htask.id,name=htask.name)
            response.append({'harvest_id':htask.id,'name':htask.name,'status':'added'})
        t.save()
    return HttpResponse(simplejson.dumps(response,indent=2, ensure_ascii=False),mimetype='application/json')  


@login_required
def users_json(request):
    response = []
    search_term = str(request.REQUEST['term']).replace('@','',1)
    users = User.objects.values('username','id','first_name','last_name').filter(username__icontains=search_term)
    for user in users:
        response.append({"id":user['username'],"label":user['username'],"value":user['id']}) 
    return HttpResponse(simplejson.dumps(response,indent=2, ensure_ascii=False),mimetype='application/json')
    

@login_required  
def client_list(request):
    """
        Gets all clients
    """
    return HttpResponse(dumps(Client.objects.all().order_by('name'),indent=2, ensure_ascii=False),mimetype='application/json')


@login_required  
def client_project_list(request, client_id):
    """
        Gets projects associated with a client
    """
    client = Client.objects.get(id=client_id)
    projects = Project.objects.filter(client=client.harvest_id)
    return HttpResponse(dumps(projects,indent=2, ensure_ascii=False),mimetype='application/json')


@login_required  
def projects_by_client(request):
    """
        Gets all projects, grouped by client
    """
    response = []
    #case insensitive ordering of objects
    for client in Client.objects.all().extra(
    select={'lower_name': 'lower(name)'}).order_by('lower_name'):
        projects = Project.objects.filter(client=client.harvest_id)
        response.append({ 'name':client.name,'harvestId':client.harvest_id, 'projects':projects })
    return HttpResponse(dumps(response,indent=2, ensure_ascii=False),mimetype='application/json')
    

@login_required      
def project_task_list(request, project_id):
    """
        Gets tasks for a project
    """
    project = Project.objects.get(id=project_id)
    task_types = TaskType.objects.filter(projects=project)
    return HttpResponse(dumps(task_types,indent=2, ensure_ascii=False),mimetype='application/json')


@login_required
def user_add(request):
    if request.method == 'POST':
        uform = UserForm(request.POST)
        pform = UserProfileForm(request.POST)

        if uform.is_valid() and uform.is_valid():
            new_user = uform.save()
            new_user.set_password(new_user.password)
            new_user.save()
            new_profile = pform.save(commit = False)
            new_profile.user = new_user
            new_profile.save()
            return HttpResponseRedirect("/?useradded=1")
    else:
        uform = UserForm()
        pform = UserProfileForm()
    return render_to_response('tasks/user_add.html', 
                            { 'uform': uform,'pform':pform},
                            context_instance = RequestContext(request))
                            
                            
@login_required         
def user_edit(request):
    user = User.objects.get(id=request.user.id)
    try:
        profile = UserProfile.objects.get(user=user)
    except ObjectDoesNotExist:
        profile = UserProfile(user=user)

    if request.method == 'POST':
        uform = UserEditForm(request.POST, instance=user)
        pform = UserProfileForm(request.POST, instance=profile)

        if uform.is_valid() and uform.is_valid():
            uform.save()
            pform.save()
            return HttpResponseRedirect("/?userupdated=1")
    else:
        uform = UserEditForm(instance=user)
        pform = UserProfileForm(instance=profile)

    return render_to_response('tasks/user_edit.html', 
                            { 'uform': uform,'pform':pform},
                            context_instance = RequestContext(request))
@login_required
def print_report(request):
    """Get task report between two specified dates"""
    try:
        tasks_from = str(request.REQUEST['from'])
    except Exception, e:
        raise e 
    try:
        tasks_to = str(request.REQUEST['to'])
    except Exception, e:
        raise e
    
    start_date = datetime.strptime(tasks_from,'%Y-%m-%d');
    end_date = datetime.strptime(tasks_to,'%Y-%m-%d');
    
    userdata = []
    users = User.objects.exclude(username='root').exclude(username='admin')
    
    for user in users:
        comp_tasks = Task.objects.filter(date__gte=tasks_from, date__lte=tasks_to, assigned_to=user, completed__isnull=False)
        incomp_tasks = Task.objects.filter(date__gte=tasks_from, date__lte=tasks_to, assigned_to=user, completed__isnull=True)                             
        userdata.append({'info':user,'complete':comp_tasks, 'incomplete':incomp_tasks})

    return render_to_response('tasks/report_print.html', {'start':start_date, 'end': end_date, 'userdata':userdata})  


@login_required
def task_report(request):
    """Get task report between two specified dates"""
    try:
        tasks_from = str(request.REQUEST['from'])
    except Exception, e:
        raise e 
    try:
        tasks_to = str(request.REQUEST['to'])
    except Exception, e:
        raise e

    userdata = []
    working_days = 0
    team_hours = 0
    team_harvested_hours = 0
    percent_harvested = 0
    possible_hours = 0
    possible_hours_per_user = 0
    team_capacity = 0
    
    try:
        tasks = Task.objects.filter(date__gte=tasks_from, date__lte=tasks_to)
    except Exception, e:
        return render_to_response('tasks/report_dates.html', { 'error':'wtf'})
    
    users = User.objects.exclude(username='root').exclude(username='admin')
    
    start_date = datetime.strptime(tasks_from,'%Y-%m-%d');
    loop_start = start_date
    end_date = datetime.strptime(tasks_to,'%Y-%m-%d');
    
    while end_date is None or loop_start <= end_date:
        if loop_start.date().weekday() < 5:
            working_days += 1
        loop_start = loop_start + timedelta(days = 1)
    
    possible_hours_per_user = working_days * 7.5
    possible_hours = possible_hours_per_user * len(users)
    
    for user in users:
        user_tasks = tasks.filter(assigned_to=user)
        task_count = len(user_tasks)
        total_hours = sum(task.hours_forecast for task in user_tasks if task.hours_forecast)
        if(possible_hours == 0):
            user_capacity = 0
        else:
            user_capacity = int(ceil(total_hours/possible_hours_per_user*100))
        harvested_hours = sum(task.hours_recorded for task in user_tasks if task.hours_recorded)
        team_hours += total_hours
        team_harvested_hours += harvested_hours
        userdata.append({'info':user,'task_count':task_count,'total_hours':total_hours,
                            'harvested_hours':harvested_hours,'capacity':user_capacity})
    
    #return charts in various sorted flavours
    by_recorded = sorted(userdata, key= lambda k: -1*(k['total_hours']))
    by_harvested = sorted(userdata, key= lambda k: -1*(k['harvested_hours']))
    by_tasks = sorted(userdata, key= lambda k: -1*(k['task_count']))
    
    if(team_hours == 0):
        percent_harvested = 0
    else:
        percent_harvested = int(ceil(team_harvested_hours/team_hours*100))
    if(possible_hours == 0):
        team_capacity = 0
    else:
        team_capacity = int(ceil(team_hours/possible_hours*100))
    
    return render_to_response('tasks/report_dates.html', 
                            {  'start':start_date, 'end': end_date,'userdata':by_recorded   , 'team_hours':team_hours , 
                                'team_harvested_hours':team_harvested_hours, 'working_days':working_days, 
                                'possible_hours':possible_hours, 'capacity':team_capacity, 'percent_harvested':percent_harvested},
                            context_instance = RequestContext(request))
        
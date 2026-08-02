from django.shortcuts import  render,redirect
from django.contrib.auth import authenticate,login
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.utils.text import slugify
# Create your views here.
from .models import Profile
from .forms import SignupForm,UserForm,ProfileForm

def signup(request):
    if request.method=='POST':
        form=SignupForm(request.POST)
        if form.is_valid():
            form.save()
            usname=form.cleaned_data['username']
            uspass=form.cleaned_data['password1']
            user=authenticate(username=usname,password=uspass)
            login(request,user)
            return redirect('/accounts/profile/edit')
    else:
        form=SignupForm()
    return render(request,'signup.html',{'form':form})

@login_required
def profile(request):
    profile=Profile.objects.get(user=request.user)
    context={'profile':profile}
    return render(request,'profile.html',context)


@login_required
def other_profile(request,slug):
    profile=Profile.objects.get(slug=slug)
    context={'profile':profile}
    return render(request,'profile.html',context)

@login_required
def profile_edit(request):
    profile=Profile.objects.get(user=request.user)
    if request.method=='POST':
        userform = UserForm(request.POST, instance=profile.user)
        profileform = ProfileForm(request.POST, request.FILES, instance=profile)
        if userform.is_valid() and profileform.is_valid():
            slug = slugify(request.user.username)
            userform.save()
            myprofileform = profileform.save(commit=False)
            myprofileform.user = request.user
            myprofileform.slug = slug
            myprofileform.save()
            return redirect('/accounts/profile')
    else:
        userform=UserForm(instance=profile.user)
        profileform=ProfileForm(instance=profile)
    return render(request,'profile_edit.html',{'userform':userform,'profileform':profileform})


@login_required
def del_account(request,slug):
    profile=Profile.objects.get(Q(user=request.user)&Q(user=request.user))
    profile.delete()
    request.user.delete()
    return redirect('/')


from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.urls import reverse
from django.db.models.signals import post_save
from django.utils.timezone import now
import os


def custom_upload_to(instance, filename):
    # Define a custom file naming scheme (e.g., based on user id and current timestamp)
    ext = filename.split('.')[-1]
    new_filename = f"{instance.user.id}_{now().strftime('%Y-%m-%d_%H-%M-%S')}.{ext}"
    return os.path.join('profile_pics', str(instance.user.id), new_filename)

# Create your models here.
def arabic_slugify(str):
    str = str.replace(" ", "-")
    str = str.replace(",", "-")
    str = str.replace("(", "-")
    str = str.replace(")", "")
    str = str.replace("؟", "")
    return str

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    img = models.ImageField(upload_to=custom_upload_to, blank=True, null=True)
    balance = models.DecimalField(max_digits=15, default=0.00, decimal_places=2, verbose_name="Coins Balance")
    current_island = models.ForeignKey('market.Island', blank=True, null=True, on_delete=models.SET_NULL, related_name='current_teams')
    slug = models.SlugField(blank=True, null=True)
    teamName = models.TextField(blank=True)
    bio = models.TextField(blank=True)
    members_list = models.TextField(blank=True, help_text="Comma separated team member names")
    joindate = models.DateTimeField(blank=True, default=now)

    def save(self, *args, **kwargs):
        if not self.slug:
            source = self.teamName or self.user.username
            self.slug = slugify(source)
            if not self.slug:
                self.slug = arabic_slugify(self.user.username)
        super(Profile, self).save(*args, **kwargs)

    class Meta:
        verbose_name = 'Team Profile'
        verbose_name_plural = 'Team Profiles'

    def __str__(self):
        return self.teamName or self.user.username

    def get_absolute_url(self):
        return reverse('accounts:profile_detail', kwargs={'slug': self.slug})

    @property
    def coins(self):
        return float(self.balance)

    @property
    def display_name(self):
        return self.teamName if self.teamName else self.user.username

    @property
    def current_vehicle_assembly(self):
        from market.models import Vehicle, TeamVehicleAssembly
        # Tie active vehicle strictly to travel progression.
        # If 0 travels, they must work on vehicle 1. 
        # If 1 travel, they must work on vehicle 2.
        active_order = self.travel_histories.count() + 1
        
        # Max out at 7
        if active_order > 7:
            active_order = 7
            
        vehicle = Vehicle.objects.filter(progression_order=active_order).first()
        if vehicle:
            assembly, _ = TeamVehicleAssembly.objects.get_or_create(profile=self, vehicle=vehicle)
            return assembly
        return None

    @property
    def completed_vehicles_count(self):
        return self.vehicle_assemblies.filter(is_completed=True).count()

    @property
    def total_travel_time(self):
        total = self.travel_histories.aggregate(models.Sum('actual_travel_time_minutes'))['actual_travel_time_minutes__sum']
        return round(total or 0.0, 1)

    @property
    def total_delay(self):
        total = self.travel_histories.aggregate(models.Sum('delay_minutes'))['delay_minutes__sum']
        return round(total or 0.0, 1)




def create_profile(sender, **kwargs):
    if kwargs['created']:
        Profile.objects.create(user=kwargs['instance'])

post_save.connect(create_profile, sender=User)

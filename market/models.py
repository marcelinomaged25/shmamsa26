from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q, Sum, Avg
from django.utils import timezone

# ---------------------------------------------------------
# Competition State & Core Settings
# ---------------------------------------------------------
class CompetitionState(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft / Not Started'),
        ('active', 'Active / Running'),
        ('paused', 'Paused'),
        ('finished', 'Finished'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Competition Status: {self.get_status_display()}"


# ---------------------------------------------------------
# Islands & Travel System
# ---------------------------------------------------------
class Island(models.Model):
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField(unique=True, help_text="Order sequence of the island in the adventure")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='islands/', blank=True, null=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Island {self.order}: {self.name}"


# ---------------------------------------------------------
# Vehicles & Required Component Requirements
# ---------------------------------------------------------
class ComponentType(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Type of component e.g. Motor, Body, Fan, Battery")
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class ComponentPowerLevel(models.Model):
    component_type = models.ForeignKey(ComponentType, on_delete=models.CASCADE, related_name='power_levels')
    name = models.CharField(max_length=120, help_text="e.g. Motor-25, Motor-50, Motor-100")
    power_value = models.PositiveIntegerField(default=25, help_text="Power level rating e.g. 25, 50, 100")
    price = models.DecimalField(max_digits=12, decimal_places=2, default=100.00)
    stock = models.PositiveIntegerField(default=999)
    image = models.ImageField(upload_to='components/', blank=True, null=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['component_type', 'power_value']

    def __str__(self):
        return f"{self.name} (Power: {self.power_value}, Price: ${self.price})"


class Vehicle(models.Model):
    PROGRESSION_ORDER_CHOICES = [
        (1, '1. Submarine'),
        (2, '2. Boat'),
        (3, '3. Car'),
        (4, '4. Airplane'),
        (5, '5. Horse Carriage'),
        (6, '6. Train'),
        (7, '7. Bicycle'),
    ]
    name = models.CharField(max_length=120)
    progression_order = models.PositiveIntegerField(unique=True, choices=PROGRESSION_ORDER_CHOICES)
    base_travel_time_minutes = models.PositiveIntegerField(default=120, help_text="Base travel time in minutes")
    image = models.ImageField(upload_to='vehicles/', blank=True, null=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['progression_order']

    def __str__(self):
        return f"[{self.progression_order}] {self.name}"

    @property
    def max_possible_power(self):
        total = 0
        for req in self.requirements.all():
            total += req.quantity_required * 100
        return total if total > 0 else 100


class VehicleComponentRequirement(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='requirements')
    component_type = models.ForeignKey(ComponentType, on_delete=models.CASCADE, related_name='vehicle_requirements')
    quantity_required = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('vehicle', 'component_type')

    def __str__(self):
        return f"{self.quantity_required}x {self.component_type.name} required for {self.vehicle.name}"


# ---------------------------------------------------------
# Team Inventory & Vehicle Progress
# ---------------------------------------------------------
class InventoryItem(models.Model):
    profile = models.ForeignKey('accounts.Profile', on_delete=models.CASCADE, related_name='inventory_items')
    power_level = models.ForeignKey(ComponentPowerLevel, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('profile', 'power_level')

    def __str__(self):
        return f"{self.profile.teamName or self.profile.user.username}: {self.quantity}x {self.power_level.name}"


class TeamVehicleAssembly(models.Model):
    profile = models.ForeignKey('accounts.Profile', on_delete=models.CASCADE, related_name='vehicle_assemblies')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_power = models.PositiveIntegerField(default=0)
    power_percentage = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('profile', 'vehicle')
        ordering = ['vehicle__progression_order']

    def __str__(self):
        return f"{self.profile.teamName or self.profile.user.username} - {self.vehicle.name} ({self.power_percentage:.1f}%)"

    def recalculate_power(self):
        allocations = self.allocated_components.select_related('power_level').all()
        
        total_components = sum(alloc.quantity for alloc in allocations)
        total_power_sum = sum(alloc.quantity * alloc.power_level.power_value for alloc in allocations)
        
        self.total_power = total_power_sum
        self.power_percentage = round((total_power_sum / total_components), 2) if total_components > 0 else 0.0

        requirements = self.vehicle.requirements.all()
        is_complete = True
        for req in requirements:
            allocated_qty = sum(a.quantity for a in allocations if a.power_level.component_type_id == req.component_type_id)
            if allocated_qty < req.quantity_required:
                is_complete = False
                break
        
        if is_complete and not self.is_completed:
            self.is_completed = True
            self.completed_at = timezone.now()
        elif not is_complete and self.is_completed:
            self.is_completed = False
            self.completed_at = None
        
        self.save()
        return self.is_completed


class TeamComponentAllocation(models.Model):
    assembly = models.ForeignKey(TeamVehicleAssembly, on_delete=models.CASCADE, related_name='allocated_components')
    power_level = models.ForeignKey(ComponentPowerLevel, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('assembly', 'power_level')

    def __str__(self):
        return f"{self.quantity}x {self.power_level.name} allocated to {self.assembly}"


# ---------------------------------------------------------
# Travel History
# ---------------------------------------------------------
class TravelHistory(models.Model):
    profile = models.ForeignKey('accounts.Profile', on_delete=models.CASCADE, related_name='travel_histories')
    from_island = models.ForeignKey(Island, on_delete=models.CASCADE, related_name='departures')
    to_island = models.ForeignKey(Island, on_delete=models.CASCADE, related_name='arrivals')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    vehicle_power_percentage = models.FloatField(default=100.0)
    base_time_minutes = models.PositiveIntegerField(default=120)
    actual_travel_time_minutes = models.FloatField(default=120.0)
    delay_minutes = models.FloatField(default=0.0)
    departed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-departed_at']

    def __str__(self):
        return f"{self.profile.teamName or self.profile.user.username}: {self.from_island.name} -> {self.to_island.name} ({self.actual_travel_time_minutes:.1f} mins)"


# ---------------------------------------------------------
# Exam Module
# ---------------------------------------------------------
class ExamCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class LiveExam(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    duration_seconds = models.PositiveIntegerField(default=300)
    total_points = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class ExamQuestion(models.Model):
    QUESTION_TYPES = [
        ('mcq', 'Multiple Choice'),
        ('tf', 'True / False'),
    ]
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    exam = models.ForeignKey(LiveExam, on_delete=models.CASCADE, related_name='questions')
    category = models.ForeignKey(ExamCategory, on_delete=models.SET_NULL, null=True, blank=True)
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES, default='mcq')
    title = models.CharField(max_length=255, blank=True)
    question_text = models.TextField()
    points = models.PositiveIntegerField(default=10)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    order = models.PositiveIntegerField(default=0)
    short_answer_correct = models.CharField(max_length=255, blank=True, help_text="Correct answer for Short Answer questions")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"[{self.get_question_type_display()}] {self.exam.title} - Q{self.order + 1}"


class ExamChoice(models.Model):
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name='choices')
    choice_text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.question.question_text[:40]} -> {self.choice_text}"


class ExamSubmission(models.Model):
    profile = models.ForeignKey('accounts.Profile', on_delete=models.CASCADE, related_name='exam_submissions')
    exam = models.ForeignKey(LiveExam, on_delete=models.CASCADE, related_name='submissions')
    score = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('profile', 'exam')

    def __str__(self):
        return f"{self.profile.teamName or self.profile.user.username} scored {self.score}/{self.total} on {self.exam.title}"


class ExamAnswer(models.Model):
    submission = models.ForeignKey(ExamSubmission, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(ExamChoice, on_delete=models.CASCADE, null=True, blank=True)
    text_answer = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.question.question_text[:40]} - {'Correct' if self.is_correct else 'Wrong'}"


# ---------------------------------------------------------
# Notifications
# ---------------------------------------------------------
class Notification(models.Model):
    profile = models.ForeignKey('accounts.Profile', on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# Backward Compatibility Placeholders
class Item(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_available = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


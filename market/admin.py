from django.contrib import admin
from .models import (
    CompetitionState,
    Island,
    ComponentType,
    ComponentPowerLevel,
    Vehicle,
    VehicleComponentRequirement,
    InventoryItem,
    TeamVehicleAssembly,
    TeamComponentAllocation,
    TravelHistory,
    ExamCategory,
    LiveExam,
    ExamQuestion,
    ExamChoice,
    ExamSubmission,
    ExamAnswer,
    Notification,
)


@admin.register(CompetitionState)
class CompetitionStateAdmin(admin.ModelAdmin):
    list_display = ('status', 'started_at', 'finished_at', 'updated_at')


@admin.register(Island)
class IslandAdmin(admin.ModelAdmin):
    list_display = ('order', 'name', 'description')
    ordering = ('order',)


@admin.register(ComponentType)
class ComponentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')


@admin.register(ComponentPowerLevel)
class ComponentPowerLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'component_type', 'power_value', 'price', 'stock')
    list_filter = ('component_type',)
    search_fields = ('name',)


class VehicleRequirementInline(admin.TabularInline):
    model = VehicleComponentRequirement
    extra = 1


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('progression_order', 'name', 'base_travel_time_minutes')
    ordering = ('progression_order',)
    inlines = [VehicleRequirementInline]


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('profile', 'power_level', 'quantity')
    list_filter = ('profile', 'power_level__component_type')


class ComponentAllocationInline(admin.TabularInline):
    model = TeamComponentAllocation
    extra = 1


@admin.register(TeamVehicleAssembly)
class TeamVehicleAssemblyAdmin(admin.ModelAdmin):
    list_display = ('profile', 'vehicle', 'power_percentage', 'is_completed', 'completed_at')
    list_filter = ('vehicle', 'is_completed')
    inlines = [ComponentAllocationInline]


@admin.register(TravelHistory)
class TravelHistoryAdmin(admin.ModelAdmin):
    list_display = ('profile', 'from_island', 'to_island', 'vehicle', 'vehicle_power_percentage', 'actual_travel_time_minutes', 'delay_minutes', 'departed_at')
    list_filter = ('profile', 'vehicle')


@admin.register(ExamCategory)
class ExamCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')


class ExamChoiceInline(admin.TabularInline):
    model = ExamChoice
    extra = 2


class ExamQuestionInline(admin.TabularInline):
    model = ExamQuestion
    extra = 1


@admin.register(LiveExam)
class LiveExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'is_active', 'duration_seconds', 'total_points', 'created_at')
    list_filter = ('status', 'is_active')
    search_fields = ('title',)
    inlines = [ExamQuestionInline]


@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ('exam', 'order', 'question_type', 'question_text', 'points', 'difficulty')
    list_filter = ('exam', 'question_type', 'difficulty')
    ordering = ('exam', 'order')
    inlines = [ExamChoiceInline]


@admin.register(ExamSubmission)
class ExamSubmissionAdmin(admin.ModelAdmin):
    list_display = ('profile', 'exam', 'score', 'total', 'submitted_at')
    list_filter = ('exam',)
    ordering = ('-submitted_at',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('profile', 'title', 'is_read', 'created_at')
    list_filter = ('is_read',)
    ordering = ('-created_at',)

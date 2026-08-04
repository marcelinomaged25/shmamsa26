from django.urls import path
from . import views

app_name = 'market'

urlpatterns = [
    # Team Views
    path('', views.leaderboard, name='market_home'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('api/leaderboard/', views.api_leaderboard, name='api_leaderboard'),
    path('dashboard/', views.team_dashboard, name='team_dashboard'),
    path('history/', views.team_history, name='team_history'),
    path('shop/', views.team_shop, name='team_shop'),
    path('buy/<int:power_level_id>/', views.buy_component, name='buy_component'),
    path('return/<int:power_level_id>/', views.return_component, name='return_component'),
    path('assembly/', views.vehicle_assembly, name='vehicle_assembly'),
    path('allocate/', views.allocate_component, name='allocate_component'),
    path('travel/', views.travel_island, name='travel_island'),
    path('exam/', views.live_exam, name='live_exam'),
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),

    # Admin Management Suite
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/competition/toggle/', views.admin_competition_toggle, name='admin_competition_toggle'),
    path('admin-panel/teams/', views.admin_teams, name='admin_teams'),
    path('admin-panel/teams/create/', views.admin_team_create, name='admin_team_create'),
    path('admin-panel/teams/<int:profile_id>/delete/', views.admin_team_delete, name='admin_team_delete'),
    path('admin-panel/vehicles/', views.admin_vehicles, name='admin_vehicles'),
    path('admin-panel/components/', views.admin_components, name='admin_components'),
    path('admin-panel/components/create/', views.admin_component_create, name='admin_component_create'),
    path('admin-panel/components/<int:power_level_id>/edit/', views.admin_component_edit, name='admin_component_edit'),
    path('admin-panel/islands/', views.admin_islands, name='admin_islands'),
    path('admin-panel/exams/', views.admin_exams, name='admin_exams'),
    path('admin-panel/exams/create/', views.admin_exam_create, name='admin_exam_create'),
    path('admin-panel/exams/<int:exam_id>/question/add/', views.admin_exam_question_add, name='admin_exam_question_add'),
    path('admin-panel/reports/', views.admin_reports, name='admin_reports'),
    path('admin-panel/reports/export/<str:report_type>/', views.admin_reports_export, name='admin_reports_export'),

    # Admin: Vehicle CRUD
    path('admin-panel/vehicles/create/', views.admin_vehicle_create, name='admin_vehicle_create'),
    path('admin-panel/vehicles/<int:vehicle_id>/edit/', views.admin_vehicle_edit, name='admin_vehicle_edit'),
    path('admin-panel/vehicles/<int:vehicle_id>/delete/', views.admin_vehicle_delete, name='admin_vehicle_delete'),

    # Admin: Component Type
    path('admin-panel/component-types/create/', views.admin_component_type_create, name='admin_component_type_create'),

    # Admin: Island Delete
    path('admin-panel/islands/<int:island_id>/delete/', views.admin_island_delete, name='admin_island_delete'),

    # Admin: Exam Toggle (Publish/Unpublish/Delete)
    path('admin-panel/exams/<int:exam_id>/toggle/', views.admin_exam_toggle, name='admin_exam_toggle'),

    # Admin: Team Coin Adjustment
    path('admin-panel/teams/<int:profile_id>/coins/', views.admin_team_adjust_coins, name='admin_team_adjust_coins'),

    # Admin: Team Progress Reset
    path('admin-panel/teams/<int:profile_id>/reset/', views.admin_team_reset, name='admin_team_reset'),
]

import csv
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from django.contrib.auth.models import User

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
from accounts.models import Profile


def admin_required(view_func):
    decorated = login_required(view_func)
    decorated = user_passes_test(lambda u: u.is_staff, login_url='/accounts/login/')(decorated)
    return decorated


def _get_competition_state():
    state, _ = CompetitionState.objects.get_or_create(id=1)
    return state


def _create_notification(profile, title, message):
    if profile:
        Notification.objects.create(profile=profile, title=title, message=message)


# ---------------------------------------------------------
# Real-Time Leaderboard Views
# ---------------------------------------------------------
def leaderboard(request):
    teams = Profile.objects.select_related('user', 'current_island').exclude(user__is_superuser=True)
    comp_state = _get_competition_state()
    
    # Calculate leaderboard data
    leaderboard_data = []
    for team in teams:
        curr_assembly = team.current_vehicle_assembly
        curr_vehicle_name = curr_assembly.vehicle.name if curr_assembly else "Completed All"
        curr_island_name = team.current_island.name if team.current_island else "Start Dock"
        
        leaderboard_data.append({
            'profile': team,
            'team_name': team.display_name,
            'current_vehicle': curr_vehicle_name,
            'current_island': curr_island_name,
            'completed_vehicles': team.completed_vehicles_count,
            'avg_power': team.average_vehicle_power,
            'total_time': team.total_travel_time,
            'total_delay': team.total_delay,
            'coins': team.coins,
            'score': team.current_score,
        })
    
    # Sort by score descending, then total delay ascending
    leaderboard_data.sort(key=lambda x: (-x['score'], x['total_delay']))
    
    # Assign ranks
    for index, data in enumerate(leaderboard_data, 1):
        data['rank'] = index

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'market/partials/leaderboard_table.html', {
            'leaderboard': leaderboard_data,
            'comp_state': comp_state,
        })

    return render(request, 'market/market_home.html', {
        'leaderboard': leaderboard_data,
        'comp_state': comp_state,
    })


def api_leaderboard(request):
    teams = Profile.objects.select_related('user', 'current_island').exclude(user__is_superuser=True)
    data = []
    for team in teams:
        curr_assembly = team.current_vehicle_assembly
        data.append({
            'id': team.id,
            'team_name': team.display_name,
            'current_vehicle': curr_assembly.vehicle.name if curr_assembly else "Completed All",
            'current_island': team.current_island.name if team.current_island else "Start Dock",
            'completed_vehicles': team.completed_vehicles_count,
            'avg_power': team.average_vehicle_power,
            'total_time': team.total_travel_time,
            'total_delay': team.total_delay,
            'coins': team.coins,
            'score': team.current_score,
        })
    data.sort(key=lambda x: (-x['score'], x['total_delay']))
    for idx, item in enumerate(data, 1):
        item['rank'] = idx
    return JsonResponse({'leaderboard': data})


# ---------------------------------------------------------
# Team Dashboard & Shop Views
# ---------------------------------------------------------
@login_required
def team_dashboard(request):
    profile = get_object_or_404(Profile, user=request.user)
    curr_assembly = profile.current_vehicle_assembly
    islands = Island.objects.all()
    history = profile.travel_histories.select_related('from_island', 'to_island', 'vehicle')[:5]
    notifications = profile.notifications.filter(is_read=False)[:5]
    comp_state = _get_competition_state()

    return render(request, 'market/dashboard.html', {
        'profile': profile,
        'current_assembly': curr_assembly,
        'islands': islands,
        'travel_history': history,
        'notifications': notifications,
        'comp_state': comp_state,
    })


@login_required
def team_shop(request):
    profile = get_object_or_404(Profile, user=request.user)
    components = ComponentPowerLevel.objects.select_related('component_type').filter(stock__gt=0)
    inventory = profile.inventory_items.select_related('power_level__component_type').filter(quantity__gt=0)
    comp_state = _get_competition_state()

    return render(request, 'market/shop.html', {
        'profile': profile,
        'components': components,
        'inventory': inventory,
        'comp_state': comp_state,
    })


@login_required
def buy_component(request, power_level_id):
    if request.method != 'POST':
        return redirect('market:team_shop')

    profile = get_object_or_404(Profile, user=request.user)
    comp = get_object_or_404(ComponentPowerLevel, id=power_level_id)

    if comp.stock <= 0:
        messages.error(request, 'This component is currently out of stock.')
        return redirect('market:team_shop')

    if profile.balance < comp.price:
        messages.error(request, f'Insufficient coins balance! Need ${comp.price}, but you have ${profile.balance}.')
        return redirect('market:team_shop')

    # Deduct coins and update stock
    profile.balance -= comp.price
    profile.save(update_fields=['balance'])

    comp.stock -= 1
    comp.save(update_fields=['stock'])

    inv_item, _ = InventoryItem.objects.get_or_create(profile=profile, power_level=comp)
    inv_item.quantity += 1
    inv_item.save()

    messages.success(request, f'Successfully purchased 1x {comp.name} for ${comp.price} coins!')
    _create_notification(profile, 'Component Purchased', f'Purchased 1x {comp.name} for ${comp.price}.')
    return redirect('market:team_shop')


# ---------------------------------------------------------
# Vehicle Assembly & Allocation System
# ---------------------------------------------------------
@login_required
def vehicle_assembly(request):
    profile = get_object_or_404(Profile, user=request.user)
    curr_assembly = profile.current_vehicle_assembly
    
    if not curr_assembly:
        messages.info(request, 'Congratulations! Your team has assembled all 7 vehicles in the competition!')
        return redirect('market:team_dashboard')

    requirements = curr_assembly.vehicle.requirements.select_related('component_type').all()
    allocations = curr_assembly.allocated_components.select_related('power_level__component_type').all()
    inventory = profile.inventory_items.select_related('power_level__component_type').filter(quantity__gt=0)

    # Detailed requirements state
    req_details = []
    for req in requirements:
        allocated = [a for a in allocations if a.power_level.component_type_id == req.component_type_id]
        allocated_qty = sum(a.quantity for a in allocated)
        req_details.append({
            'requirement': req,
            'allocated_qty': allocated_qty,
            'is_satisfied': allocated_qty >= req.quantity_required,
            'allocated_items': allocated,
        })

    return render(request, 'market/checklist.html', {
        'profile': profile,
        'assembly': curr_assembly,
        'req_details': req_details,
        'inventory': inventory,
    })


@login_required
def allocate_component(request):
    if request.method != 'POST':
        return redirect('market:vehicle_assembly')

    profile = get_object_or_404(Profile, user=request.user)
    curr_assembly = profile.current_vehicle_assembly
    
    if not curr_assembly:
        messages.error(request, 'No active vehicle assembly available.')
        return redirect('market:team_dashboard')

    power_level_id = request.POST.get('power_level_id')
    try:
        quantity = int(request.POST.get('quantity', 1))
    except ValueError:
        quantity = 1

    power_level = get_object_or_404(ComponentPowerLevel, id=power_level_id)
    inv_item = InventoryItem.objects.filter(profile=profile, power_level=power_level).first()

    if not inv_item or inv_item.quantity < quantity:
        messages.error(request, 'You do not have enough of this component in your inventory.')
        return redirect('market:vehicle_assembly')

    # Enforce vehicle component type requirement
    req = VehicleComponentRequirement.objects.filter(vehicle=curr_assembly.vehicle, component_type=power_level.component_type).first()
    if not req:
        messages.error(request, f'{power_level.component_type.name} is not a required component for {curr_assembly.vehicle.name}.')
        return redirect('market:vehicle_assembly')

    # Deduct from inventory and allocate
    inv_item.quantity -= quantity
    if inv_item.quantity <= 0:
        inv_item.delete()
    else:
        inv_item.save()

    alloc, _ = TeamComponentAllocation.objects.get_or_create(assembly=curr_assembly, power_level=power_level)
    alloc.quantity += quantity
    alloc.save()

    is_complete = curr_assembly.recalculate_power()

    if is_complete:
        messages.success(request, f'🎉 Vehicle Complete! Your team completed assembly of {curr_assembly.vehicle.name} with {curr_assembly.power_percentage}% Power!')
        _create_notification(profile, 'Vehicle Complete', f'Completed {curr_assembly.vehicle.name} at {curr_assembly.power_percentage}% Power!')
    else:
        messages.success(request, f'Allocated {quantity}x {power_level.name} to {curr_assembly.vehicle.name}. Current Power: {curr_assembly.power_percentage}%.')

    return redirect('market:vehicle_assembly')


# ---------------------------------------------------------
# Island Travel System
# ---------------------------------------------------------
@login_required
def travel_island(request):
    if request.method != 'POST':
        return redirect('market:team_dashboard')

    profile = get_object_or_404(Profile, user=request.user)
    curr_assembly = profile.current_vehicle_assembly
    
    # Must have a completed vehicle to travel
    prev_assembly = TeamVehicleAssembly.objects.filter(profile=profile, is_completed=True).order_by('-vehicle__progression_order').first()
    
    if not prev_assembly:
        messages.error(request, 'Your team must complete your current vehicle before travelling between islands!')
        return redirect('market:vehicle_assembly')

    # Get current island or start at Island #1
    current_island = profile.current_island
    if not current_island:
        current_island = Island.objects.filter(order=1).first()
        if not current_island:
            current_island = Island.objects.create(name="Start Dock", order=1, description="Initial competition starting dock")
        profile.current_island = current_island
        profile.save()

    # Next island in sequence
    next_island = Island.objects.filter(order=current_island.order + 1).first()
    if not next_island:
        messages.info(request, 'Your team has already reached the final island!')
        return redirect('market:team_dashboard')

    # Calculate Travel Time & Delay
    # Formula: Efficiency = Power % / 100. Actual Travel Time = Base Time / Efficiency. Delay = Actual - Base.
    base_time = prev_assembly.vehicle.base_travel_time_minutes
    efficiency = max(0.25, prev_assembly.power_percentage / 100.0) # min 25% efficiency floor
    actual_time = round(base_time / efficiency, 1)
    delay = max(0.0, round(actual_time - base_time, 1))

    # Log travel history
    TravelHistory.objects.create(
        profile=profile,
        from_island=current_island,
        to_island=next_island,
        vehicle=prev_assembly.vehicle,
        vehicle_power_percentage=prev_assembly.power_percentage,
        base_time_minutes=base_time,
        actual_travel_time_minutes=actual_time,
        delay_minutes=delay,
    )

    profile.current_island = next_island
    profile.save(update_fields=['current_island'])

    messages.success(request, f'⚓ Travel Complete! Travelled from {current_island.name} to {next_island.name} using {prev_assembly.vehicle.name}. Travel Time: {actual_time} mins (Delay: +{delay} mins).')
    _create_notification(profile, 'Island Travel Complete', f'Arrived at {next_island.name}. Travel duration: {actual_time} mins.')
    return redirect('market:team_dashboard')


# ---------------------------------------------------------
# Exam Module (Team Taker)
# ---------------------------------------------------------
@login_required
def live_exam(request):
    profile = get_object_or_404(Profile, user=request.user)
    exam = LiveExam.objects.filter(is_published=True, is_active=True).order_by('-created_at').first()

    if not exam:
        return render(request, 'market/exam.html', {
            'message': 'No published active exam available right now.',
            'profile': profile,
        })

    existing_sub = ExamSubmission.objects.filter(profile=profile, exam=exam).first()
    if existing_sub:
        return render(request, 'market/exam.html', {
            'exam': exam,
            'profile': profile,
            'submitted': True,
            'submission': existing_sub,
            'answers': existing_sub.answers.select_related('question', 'selected_choice').all(),
        })

    if request.method == 'POST':
        questions = exam.questions.all()
        earned_score = 0
        total_possible = sum(q.points for q in questions)
        
        submission = ExamSubmission.objects.create(
            profile=profile,
            exam=exam,
            score=0,
            total=total_possible,
            duration_seconds=int(request.POST.get('duration_seconds', 0)),
        )

        for q in questions:
            if q.question_type in ['mcq', 'tf']:
                choice_id = request.POST.get(f'question_{q.id}')
                choice = ExamChoice.objects.filter(id=choice_id, question=q).first() if choice_id else None
                is_correct = choice.is_correct if choice else False
                if is_correct:
                    earned_score += q.points
                ExamAnswer.objects.create(submission=submission, question=q, selected_choice=choice, is_correct=is_correct)
            elif q.question_type == 'short':
                text_ans = request.POST.get(f'question_{q.id}', '').strip()
                is_correct = text_ans.lower() == q.short_answer_correct.lower().strip() if q.short_answer_correct else False
                if is_correct:
                    earned_score += q.points
                ExamAnswer.objects.create(submission=submission, question=q, text_answer=text_ans, is_correct=is_correct)

        submission.score = earned_score
        submission.save()

        messages.success(request, f'Exam submitted successfully! Score: {earned_score}/{total_possible}.')
        _create_notification(profile, 'Exam Completed', f'Submitted {exam.title} with score {earned_score}/{total_possible}.')
        return redirect('market:live_exam')

    return render(request, 'market/exam.html', {
        'exam': exam,
        'profile': profile,
        'questions': exam.questions.prefetch_related('choices').all(),
    })


# ---------------------------------------------------------
# System Notifications
# ---------------------------------------------------------
@login_required
def mark_notifications_read(request):
    if request.method == 'POST':
        profile = get_object_or_404(Profile, user=request.user)
        profile.notifications.filter(is_read=False).update(is_read=True)
    return redirect('market:team_dashboard')


# ---------------------------------------------------------
# Admin Dashboard & Control Suite
# ---------------------------------------------------------
@admin_required
def admin_dashboard(request):
    comp_state = _get_competition_state()
    teams_count = Profile.objects.exclude(user__is_superuser=True).count()
    vehicles_count = Vehicle.objects.count()
    components_count = ComponentPowerLevel.objects.count()
    exams_count = LiveExam.objects.count()
    
    recent_travels = TravelHistory.objects.select_related('profile', 'from_island', 'to_island', 'vehicle')[:5]
    recent_submissions = ExamSubmission.objects.select_related('profile', 'exam')[:5]

    return render(request, 'market/admin/dashboard.html', {
        'comp_state': comp_state,
        'teams_count': teams_count,
        'vehicles_count': vehicles_count,
        'components_count': components_count,
        'exams_count': exams_count,
        'recent_travels': recent_travels,
        'recent_submissions': recent_submissions,
    })


@admin_required
def admin_competition_toggle(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        state = _get_competition_state()
        if action == 'start':
            state.status = 'active'
            state.started_at = timezone.now()
            messages.success(request, '🏁 Competition officially STARTED!')
        elif action == 'pause':
            state.status = 'paused'
            messages.warning(request, '⏸ Competition PAUSED.')
        elif action == 'resume':
            state.status = 'active'
            messages.success(request, '▶ Competition RESUMED.')
        elif action == 'finish':
            state.status = 'finished'
            state.finished_at = timezone.now()
            messages.info(request, '🏆 Competition FINISHED!')
        state.save()
    return redirect('market:admin_dashboard')


@admin_required
def admin_teams(request):
    teams = Profile.objects.select_related('user', 'current_island').exclude(user__is_superuser=True)
    return render(request, 'market/admin/teams.html', {'teams': teams})


@admin_required
def admin_team_create(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        team_name = request.POST.get('team_name')
        coins = float(request.POST.get('coins', 1000.0))
        members = request.POST.get('members', '')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists!')
            return redirect('market:admin_team_create')

        user = User.objects.create_user(username=username, password=password)
        profile = user.profile
        profile.teamName = team_name
        profile.balance = coins
        profile.members_list = members
        profile.save()

        messages.success(request, f'Team "{team_name}" created successfully!')
        return redirect('market:admin_teams')

    return render(request, 'market/admin/team_form.html')


@admin_required
def admin_team_edit(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    if request.method == 'POST':
        profile.teamName = request.POST.get('team_name', profile.teamName)
        profile.balance = float(request.POST.get('coins', profile.balance))
        profile.members_list = request.POST.get('members', profile.members_list)
        profile.save()
        messages.success(request, f'Team "{profile.display_name}" updated successfully!')
        return redirect('market:admin_teams')
    return render(request, 'market/admin/team_form.html', {'team': profile})


@admin_required
def admin_team_delete(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    user = profile.user
    user.delete()
    messages.success(request, 'Team deleted successfully.')
    return redirect('market:admin_teams')


@admin_required
def admin_vehicles(request):
    vehicles = Vehicle.objects.prefetch_related('requirements__component_type').all()
    return render(request, 'market/admin/vehicles.html', {'vehicles': vehicles})


@admin_required
def admin_components(request):
    components = ComponentPowerLevel.objects.select_related('component_type').all()
    types = ComponentType.objects.all()
    return render(request, 'market/admin/components.html', {'components': components, 'types': types})


@admin_required
def admin_component_create(request):
    types = ComponentType.objects.all()
    if request.method == 'POST':
        type_id = request.POST.get('type_id')
        name = request.POST.get('name')
        power = int(request.POST.get('power_value', 25))
        price = float(request.POST.get('price', 100.0))
        stock = int(request.POST.get('stock', 999))
        desc = request.POST.get('description', '')

        ctype = get_object_or_404(ComponentType, id=type_id)
        ComponentPowerLevel.objects.create(
            component_type=ctype,
            name=name,
            power_value=power,
            price=price,
            stock=stock,
            description=desc,
        )
        messages.success(request, f'Component Power Level "{name}" created successfully!')
        return redirect('market:admin_components')
    return render(request, 'market/admin/component_form.html', {'types': types})


@admin_required
def admin_component_edit(request, power_level_id):
    comp = get_object_or_404(ComponentPowerLevel, id=power_level_id)
    types = ComponentType.objects.all()
    if request.method == 'POST':
        comp.name = request.POST.get('name', comp.name)
        comp.power_value = int(request.POST.get('power_value', comp.power_value))
        comp.price = float(request.POST.get('price', comp.price))
        comp.stock = int(request.POST.get('stock', comp.stock))
        comp.description = request.POST.get('description', comp.description)
        comp.save()
        messages.success(request, f'Component "{comp.name}" updated successfully!')
        return redirect('market:admin_components')
    return render(request, 'market/admin/component_form.html', {'comp': comp, 'types': types})


@admin_required
def admin_islands(request):
    islands = Island.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name')
        order = int(request.POST.get('order', islands.count() + 1))
        desc = request.POST.get('description', '')
        Island.objects.create(name=name, order=order, description=desc)
        messages.success(request, f'Island "{name}" created successfully!')
        return redirect('market:admin_islands')
    return render(request, 'market/admin/islands.html', {'islands': islands})


@admin_required
def admin_exams(request):
    exams = LiveExam.objects.prefetch_related('questions__choices', 'submissions').all()
    return render(request, 'market/admin/exams.html', {'exams': exams})


@admin_required
def admin_exam_create(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        desc = request.POST.get('description', '')
        duration = int(request.POST.get('duration_seconds', 300))
        status = request.POST.get('status', 'published')
        is_published = status == 'published'
        
        LiveExam.objects.create(
            title=title,
            description=desc,
            duration_seconds=duration,
            status=status,
            is_published=is_published,
            is_active=True,
        )
        messages.success(request, f'Exam "{title}" created successfully!')
        return redirect('market:admin_exams')
    return render(request, 'market/admin/exam_form.html')


@admin_required
def admin_exam_question_add(request, exam_id):
    exam = get_object_or_404(LiveExam, id=exam_id)
    if request.method == 'POST':
        qtype = request.POST.get('question_type', 'mcq')
        qtext = request.POST.get('question_text')
        points = int(request.POST.get('points', 10))
        difficulty = request.POST.get('difficulty', 'medium')
        short_answer = request.POST.get('short_answer_correct', '')

        question = ExamQuestion.objects.create(
            exam=exam,
            question_type=qtype,
            question_text=qtext,
            points=points,
            difficulty=difficulty,
            short_answer_correct=short_answer,
            order=exam.questions.count() + 1,
        )

        if qtype in ['mcq', 'tf']:
            choices = request.POST.getlist('choice_text')
            correct_index = int(request.POST.get('correct_choice', 0))
            for idx, ctext in enumerate(choices):
                if ctext.strip():
                    ExamChoice.objects.create(
                        question=question,
                        choice_text=ctext.strip(),
                        is_correct=(idx == correct_index),
                    )

        messages.success(request, 'Question added successfully!')
        return redirect('market:admin_exams')

    return render(request, 'market/admin/question_form.html', {'exam': exam})


@admin_required
def admin_reports(request):
    teams = Profile.objects.exclude(user__is_superuser=True)
    fastest_team = sorted(teams, key=lambda t: t.total_travel_time)[0] if teams.exists() else None
    highest_power_team = sorted(teams, key=lambda t: -t.average_vehicle_power)[0] if teams.exists() else None
    most_delay_team = sorted(teams, key=lambda t: -t.total_delay)[0] if teams.exists() else None

    return render(request, 'market/admin/reports.html', {
        'fastest_team': fastest_team,
        'highest_power_team': highest_power_team,
        'most_delay_team': most_delay_team,
        'teams': teams,
    })


@admin_required
def admin_reports_export(request, report_type):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report.csv"'

    writer = csv.writer(response)
    if report_type == 'leaderboard':
        writer.writerow(['Rank', 'Team Name', 'Current Vehicle', 'Current Island', 'Completed Vehicles', 'Avg Power %', 'Total Travel Time (min)', 'Total Delay (min)', 'Coins Balance', 'Score'])
        teams = Profile.objects.exclude(user__is_superuser=True)
        l_data = []
        for t in teams:
            curr_assembly = t.current_vehicle_assembly
            l_data.append({
                'name': t.display_name,
                'vehicle': curr_assembly.vehicle.name if curr_assembly else "Completed All",
                'island': t.current_island.name if t.current_island else "Start Dock",
                'completed': t.completed_vehicles_count,
                'power': t.average_vehicle_power,
                'time': t.total_travel_time,
                'delay': t.total_delay,
                'coins': t.coins,
                'score': t.current_score,
            })
        l_data.sort(key=lambda x: (-x['score'], x['delay']))
        for idx, row in enumerate(l_data, 1):
            writer.writerow([idx, row['name'], row['vehicle'], row['island'], row['completed'], row['power'], row['time'], row['delay'], row['coins'], row['score']])
    
    return response


# ---------------------------------------------------------
# Admin: Vehicle CRUD
# ---------------------------------------------------------
@admin_required
def admin_vehicle_create(request):
    types = ComponentType.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name')
        order = int(request.POST.get('progression_order', 1))
        desc = request.POST.get('description', '')
        base_time = int(request.POST.get('base_travel_time_minutes', 120))

        vehicle = Vehicle.objects.create(
            name=name,
            progression_order=order,
            description=desc,
            base_travel_time_minutes=base_time,
        )

        # Add component requirements
        req_type_ids = request.POST.getlist('req_type_id')
        req_quantities = request.POST.getlist('req_quantity')
        for tid, qty in zip(req_type_ids, req_quantities):
            if tid and qty:
                ctype = ComponentType.objects.filter(id=tid).first()
                if ctype:
                    VehicleComponentRequirement.objects.create(
                        vehicle=vehicle,
                        component_type=ctype,
                        quantity_required=int(qty),
                    )

        messages.success(request, f'Vehicle "{name}" created successfully!')
        return redirect('market:admin_vehicles')
    return render(request, 'market/admin/vehicle_form.html', {'types': types})


@admin_required
def admin_vehicle_edit(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    types = ComponentType.objects.all()
    if request.method == 'POST':
        vehicle.name = request.POST.get('name', vehicle.name)
        vehicle.progression_order = int(request.POST.get('progression_order', vehicle.progression_order))
        vehicle.description = request.POST.get('description', vehicle.description)
        vehicle.base_travel_time_minutes = int(request.POST.get('base_travel_time_minutes', vehicle.base_travel_time_minutes))
        vehicle.save()

        # Update component requirements (clear and re-create)
        vehicle.requirements.all().delete()
        req_type_ids = request.POST.getlist('req_type_id')
        req_quantities = request.POST.getlist('req_quantity')
        for tid, qty in zip(req_type_ids, req_quantities):
            if tid and qty:
                ctype = ComponentType.objects.filter(id=tid).first()
                if ctype:
                    VehicleComponentRequirement.objects.create(
                        vehicle=vehicle,
                        component_type=ctype,
                        quantity_required=int(qty),
                    )

        messages.success(request, f'Vehicle "{vehicle.name}" updated successfully!')
        return redirect('market:admin_vehicles')
    return render(request, 'market/admin/vehicle_form.html', {'vehicle': vehicle, 'types': types})


@admin_required
def admin_vehicle_delete(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    name = vehicle.name
    vehicle.delete()
    messages.success(request, f'Vehicle "{name}" deleted successfully.')
    return redirect('market:admin_vehicles')


# ---------------------------------------------------------
# Admin: Component Type CRUD
# ---------------------------------------------------------
@admin_required
def admin_component_type_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        desc = request.POST.get('description', '')
        if name:
            ComponentType.objects.create(name=name, description=desc)
            messages.success(request, f'Component type "{name}" created successfully!')
        return redirect('market:admin_components')
    return render(request, 'market/admin/component_type_form.html')


# ---------------------------------------------------------
# Admin: Island Delete
# ---------------------------------------------------------
@admin_required
def admin_island_delete(request, island_id):
    island = get_object_or_404(Island, id=island_id)
    name = island.name
    island.delete()
    messages.success(request, f'Island "{name}" deleted successfully.')
    return redirect('market:admin_islands')


# ---------------------------------------------------------
# Admin: Exam Publish/Unpublish Toggle
# ---------------------------------------------------------
@admin_required
def admin_exam_toggle(request, exam_id):
    exam = get_object_or_404(LiveExam, id=exam_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'publish':
            exam.is_published = True
            exam.is_active = True
            exam.status = 'published'
            messages.success(request, f'Exam "{exam.title}" is now LIVE and published!')
        elif action == 'unpublish':
            exam.is_published = False
            exam.is_active = False
            exam.status = 'draft'
            messages.warning(request, f'Exam "{exam.title}" has been unpublished.')
        elif action == 'delete':
            title = exam.title
            exam.delete()
            messages.success(request, f'Exam "{title}" has been deleted.')
            return redirect('market:admin_exams')
        exam.save()
    return redirect('market:admin_exams')


# ---------------------------------------------------------
# Admin: Team Coin Adjustment
# ---------------------------------------------------------
@admin_required
def admin_team_adjust_coins(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        amount = Decimal(request.POST.get('amount', '0'))
        if action == 'add':
            profile.balance += amount
            messages.success(request, f'Added ${amount} coins to {profile.display_name}. New balance: ${profile.balance}.')
        elif action == 'deduct':
            profile.balance = max(Decimal('0'), profile.balance - amount)
            messages.success(request, f'Deducted ${amount} coins from {profile.display_name}. New balance: ${profile.balance}.')
        elif action == 'set':
            profile.balance = amount
            messages.success(request, f'Set {profile.display_name} balance to ${amount}.')
        profile.save(update_fields=['balance'])
        _create_notification(profile, 'Balance Updated', f'Your coin balance was adjusted to ${profile.balance} by admin.')
    return redirect('market:admin_teams')


# ---------------------------------------------------------
# Admin: Reset Team Progress (Full Reset)
# ---------------------------------------------------------
@admin_required
def admin_team_reset(request, profile_id):
    profile = get_object_or_404(Profile, id=profile_id)
    if request.method == 'POST':
        # Clear all assemblies, allocations, travel history, inventory, and exam submissions
        TeamVehicleAssembly.objects.filter(profile=profile).delete()
        InventoryItem.objects.filter(profile=profile).delete()
        TravelHistory.objects.filter(profile=profile).delete()
        ExamSubmission.objects.filter(profile=profile).delete()
        profile.current_island = Island.objects.filter(order=1).first()
        profile.save(update_fields=['current_island'])

        messages.success(request, f'All progress for {profile.display_name} has been reset!')
        _create_notification(profile, 'Progress Reset', 'Your team progress has been reset by the competition admin.')
    return redirect('market:admin_teams')


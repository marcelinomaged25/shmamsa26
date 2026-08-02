import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangoProject.settings')
django.setup()

from market.models import Vehicle
if not Vehicle.objects.exists():
    print('Fresh database detected — running seed...')
    from django.contrib.auth.models import User
    from accounts.models import Profile
    from market.models import (
        CompetitionState, Island, ComponentType, ComponentPowerLevel,
        Vehicle, VehicleComponentRequirement
    )

    # Competition State
    CompetitionState.objects.get_or_create(id=1)

    # Islands
    island_names = ['Base Dock', 'Coral Reef', 'Misty Harbor', 'Storm Ridge', 'Emerald Cove', 'Volcanic Peak', 'Victory Apex']
    for i, name in enumerate(island_names, 1):
        Island.objects.get_or_create(name=name, order=i)

    # Component Types
    type_names = ['Submarine Body', 'Motor', 'Fan', 'Battery', 'Hull', 'Chassis', 'Engine', 'Wing']
    types = {}
    for tn in type_names:
        obj, _ = ComponentType.objects.get_or_create(name=tn)
        types[tn] = obj

    # Power Levels (25, 50, 100 for each type)
    for tn, ctype in types.items():
        for pv in [25, 50, 100]:
            price_map = {25: 100, 50: 250, 100: 500}
            ComponentPowerLevel.objects.get_or_create(
                component_type=ctype, power_value=pv,
                defaults={'name': f'{tn}-{pv}', 'price': price_map[pv], 'stock': 999}
            )

    # Vehicles
    vehicle_defs = [
        (1, 'Submarine', 'Deep-sea exploration vessel', 120,
         [('Submarine Body', 1), ('Motor', 2), ('Fan', 2), ('Battery', 1)]),
        (2, 'Boat', 'Surface water transport', 90,
         [('Hull', 1), ('Motor', 1), ('Fan', 1)]),
        (3, 'Car', 'Ground transport vehicle', 60,
         [('Chassis', 1), ('Engine', 1), ('Battery', 1)]),
        (4, 'Airplane', 'Aerial transport craft', 150,
         [('Engine', 2), ('Wing', 2), ('Battery', 1)]),
        (5, 'Horse Carriage', 'Classic animal-powered transport', 180,
         [('Chassis', 1), ('Hull', 1)]),
        (6, 'Train', 'Railway transport locomotive', 100,
         [('Engine', 2), ('Chassis', 1), ('Battery', 1)]),
        (7, 'Bicycle', 'Human-powered two-wheeler', 200,
         [('Chassis', 1), ('Fan', 1)]),
    ]
    for order, name, desc, base_time, reqs in vehicle_defs:
        v, _ = Vehicle.objects.get_or_create(
            progression_order=order,
            defaults={'name': name, 'description': desc, 'base_travel_time_minutes': base_time}
        )
        for comp_name, qty in reqs:
            VehicleComponentRequirement.objects.get_or_create(
                vehicle=v, component_type=types[comp_name],
                defaults={'quantity_required': qty}
            )

    # Admin user
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@competition.com', 'admin123')

    # Demo teams
    for team_user, team_label in [('team1','Alpha Squad'),('team2','Beta Force'),('team3','Gamma Unit')]:
        if not User.objects.filter(username=team_user).exists():
            u = User.objects.create_user(team_user, password='team123')
            p = u.profile
            p.teamName = team_label
            p.balance = 5000.0
            p.current_island = Island.objects.get(order=1)
            p.save()

    print('Seed complete!')
else:
    print('Database already seeded — skipping.')

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from market.models import (
    ComponentType,
    ComponentPowerLevel,
    Vehicle,
    VehicleComponentRequirement,
    TeamVehicleAssembly,
    Island,
    TravelHistory,
    LiveExam,
    ExamQuestion,
    ExamChoice,
    ExamSubmission,
)


class CompetitionFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='teamone', password='secret123')
        self.profile = self.user.profile
        self.profile.balance = 1000.0
        self.profile.save()

        # Create Islands
        self.island1 = Island.objects.create(name="Island 1", order=1)
        self.island2 = Island.objects.create(name="Island 2", order=2)
        self.profile.current_island = self.island1
        self.profile.save()

        # Component Types
        self.ctype_motor = ComponentType.objects.create(name="Motor")
        self.ctype_body = ComponentType.objects.create(name="Body")

        # Power levels
        self.motor25 = ComponentPowerLevel.objects.create(component_type=self.ctype_motor, name="Motor-25", power_value=25, price=50.0)
        self.motor100 = ComponentPowerLevel.objects.create(component_type=self.ctype_motor, name="Motor-100", power_value=100, price=200.0)
        self.body50 = ComponentPowerLevel.objects.create(component_type=self.ctype_body, name="Body-50", power_value=50, price=100.0)

        # Vehicle 1: Submarine (Order #1)
        self.sub = Vehicle.objects.create(progression_order=1, name="Submarine", base_travel_time_minutes=120)
        VehicleComponentRequirement.objects.create(vehicle=self.sub, component_type=self.ctype_body, quantity_required=1)
        VehicleComponentRequirement.objects.create(vehicle=self.sub, component_type=self.ctype_motor, quantity_required=2)

    def test_component_power_and_assembly(self):
        assembly, _ = TeamVehicleAssembly.objects.get_or_create(profile=self.profile, vehicle=self.sub)
        self.assertEqual(assembly.power_percentage, 0.0)
        self.assertFalse(assembly.is_completed)

    def test_published_exam_submission(self):
        exam = LiveExam.objects.create(title='Live Engineering Challenge', description='Ready', is_active=True, is_published=True)
        question = ExamQuestion.objects.create(exam=exam, question_text='What is power efficiency?', order=1, points=50)
        choice = ExamChoice.objects.create(question=question, choice_text='Collected / Max', is_correct=True)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('market:live_exam'),
            {f'question_{question.id}': str(choice.id), 'duration_seconds': 45},
            follow=True,
        )

        self.assertEqual(ExamSubmission.objects.filter(profile=self.profile, exam=exam).count(), 1)
        sub = ExamSubmission.objects.get(profile=self.profile, exam=exam)
        self.assertEqual(sub.score, 50)


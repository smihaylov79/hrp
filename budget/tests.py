"""Phase 0 safety net for budgets: a budget belongs to its household, or to its creator when solo."""
from datetime import date
from decimal import Decimal

from django.urls import reverse

from hrp.testing import HrpTestCase, known_bug, make_income, make_purchase
from income.models import IncomeType

from .models import Budget, BudgetApproval, BudgetIncomeItem, BudgetItem


class BudgetOwnershipTests(HrpTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        year = date.today().year
        cls.salary = IncomeType.objects.create(name='Заплата')

        def make_budget(creator, household, amount):
            budget = Budget.objects.create(
                name=f'Бюджет {creator.first_name}', creator=creator, household=household,
                date_from=date(year, 1, 1), date_to=date(year, 12, 31), currency='EUR', submitted=True)
            BudgetItem.objects.create(budget=budget, category=cls.main_food, planned_amount=amount)
            BudgetIncomeItem.objects.create(budget=budget, income_type=cls.salary, planned_amount=amount * 2)
            return budget

        cls.home_budget = make_budget(cls.carol, cls.household, Decimal('1200'))
        cls.alice_budget = make_budget(cls.alice, None, Decimal('600'))
        for member in (cls.carol, cls.dave):
            BudgetApproval.objects.create(budget=cls.home_budget, user=member)
        # some real spending/income so that the tracking page has data
        for user in (cls.alice, cls.carol):
            make_purchase(user, cls.milk, price=10, on_date=date(year, 1, 2))
            make_income(user, 100, on_date=date(year, 1, 2))

    def url(self, name, budget):
        return reverse(name, kwargs={'pk': budget.pk})

    # -- login -------------------------------------------------------------------------------------
    def test_all_budget_views_require_login(self):
        for url in [reverse('budget_home'), reverse('propose_budget'), self.url('budget_detail', self.home_budget),
                    self.url('track_budget', self.home_budget), self.url('edit_budget', self.home_budget)]:
            with self.subTest(url=url):
                self.assertLoginRequired(url)

    # -- own data ----------------------------------------------------------------------------------
    def test_home_lists_only_own_or_household_budgets(self):
        expected = {self.alice: [self.alice_budget.pk], self.bob: [],
                    self.carol: [self.home_budget.pk], self.dave: [self.home_budget.pk]}
        for user, pks in expected.items():
            with self.subTest(user=user.email):
                self.client.force_login(user)
                response = self.client.get(reverse('budget_home'))
                self.assertEqual([b.pk for b in response.context['budgets']], pks)

    def test_household_members_can_open_and_track_household_budget(self):
        for member in (self.carol, self.dave):
            with self.subTest(member=member.email):
                self.client.force_login(member)
                self.assertEqual(self.client.get(self.url('budget_detail', self.home_budget)).status_code, 200)
                response = self.client.get(self.url('track_budget', self.home_budget))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['total_actual'], 10.0)   # carol's purchase only, not alice's

    def test_member_approval_marks_budget_approved_when_all_approved(self):
        for member in (self.carol, self.dave):
            self.client.force_login(member)
            self.client.post(self.url('budget_detail', self.home_budget), {'action': 'approve'})
        self.home_budget.refresh_from_db()
        self.assertTrue(self.home_budget.approved)

    @known_bug('Phase 7: Budget.scope_users() returns a list for solo budgets -> detail page crashes')
    def test_solo_user_can_open_own_budget(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(self.url('budget_detail', self.alice_budget)).status_code, 200)

    def test_solo_user_can_track_own_budget(self):
        self.client.force_login(self.alice)
        response = self.client.get(self.url('track_budget', self.alice_budget))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_actual'], 10.0)

    # -- foreign data ------------------------------------------------------------------------------
    @known_bug('Phase 1: budget_detail loads any budget by pk (no owner check)')
    def test_foreign_budget_detail_is_404(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(self.url('budget_detail', self.home_budget)).status_code, 404)

    @known_bug('Phase 1: track_budget loads any budget by pk (no owner check)')
    def test_foreign_budget_tracking_is_404(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(self.url('track_budget', self.home_budget)).status_code, 404)

    @known_bug('Phase 1: edit_budget loads any budget by pk (no owner check)')
    def test_foreign_budget_cannot_be_edited(self):
        item = self.home_budget.items.get()
        self.client.force_login(self.bob)
        self.client.post(self.url('edit_budget', self.home_budget), {f'expense_{item.pk}': '1'})
        item.refresh_from_db()
        self.assertEqual(item.planned_amount, Decimal('1200'))

    @known_bug('Phase 1: propose_budget finalize takes any budget_id and wipes its items')
    def test_finalize_cannot_wipe_a_foreign_budget(self):
        self.client.force_login(self.bob)
        try:
            self.client.post(reverse('propose_budget'), {'action': 'finalize', 'budget_id': self.home_budget.pk})
        except Exception:
            pass
        self.assertEqual(self.home_budget.items.count(), 1)
        self.assertEqual(self.home_budget.income_items.count(), 1)
        self.home_budget.refresh_from_db()
        self.assertEqual(self.home_budget.creator, self.carol)

    def test_owner_can_finalize_own_budget(self):
        self.client.force_login(self.carol)
        response = self.client.post(reverse('propose_budget'), {
            'action': 'finalize', 'budget_id': self.home_budget.pk,
            'month_Храна_1': '100', 'month_Храна_2': '150', 'income_Заплата_1': '900'})
        self.assertRedirects(response, self.url('budget_detail', self.home_budget), fetch_redirect_response=False)
        self.assertEqual(self.home_budget.items.get().planned_amount, Decimal('250'))
        self.assertEqual(self.home_budget.income_items.get().planned_amount, Decimal('900'))

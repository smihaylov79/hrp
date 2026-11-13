from datetime import date
from decimal import Decimal

from django.test import TestCase, RequestFactory
from django.urls import reverse

from hrp.testing import HrpTestCase, known_bug, make_purchase
from shopping.models import HouseholdShoppingList, ShoppingList
from taskmanager.models import Task
from users.models import CustomUser
from inventory.models import HouseholdProductCategory, UserProductCategory
from inventory.views import generate_shopping_list


# Create your tests here.

class ShoppingListGenerationTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = CustomUser.objects.create_user(email='test@user.com', password='Ineedstrongpassord123!@', first_name='test', last_name='user')

    @known_bug('Phase 2/7: db_to_df crashes when the user has no purchases yet (500 for a new user)')
    def test_task_created(self):
        request = self.factory.get(reverse('shopping_list_view', args=[1]))
        request.user = self.user
        response = generate_shopping_list(request)
        task = Task.objects.filter(user=self.user).first()
        self.assertIsNotNone(task)
        self.assertIn('Пазаруване', task.title)
        self.assertEqual(task.due_date, date.today())


class ShoppingListGenerationWithHistoryTest(HrpTestCase):
    def test_task_and_list_created_for_user_with_purchases(self):
        make_purchase(self.alice, self.milk, price=2)
        self.client.force_login(self.alice)
        response = self.client.get(reverse('generate_shopping_list'))
        shopping_list = ShoppingList.objects.get(user=self.alice)
        self.assertRedirects(response, reverse('shopping_list_view', args=[shopping_list.id]),
                             fetch_redirect_response=False)
        task = Task.objects.get(user=self.alice)
        self.assertIn('Пазаруване', task.title)
        self.assertFalse(Task.objects.exclude(user=self.alice).exists())


class InventoryOwnershipTests(HrpTestCase):
    """Inventory rows belong to one user or one household; nobody else may see or change them."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.alice_milk = cls.user_inventory(cls.alice, cls.milk, quantity=5, amount=10)
        cls.bob_milk = cls.user_inventory(cls.bob, cls.milk, quantity=7, amount=21)
        cls.home_milk = cls.household_inventory(cls.household, cls.milk, quantity=9, amount=18)

    # -- reading -----------------------------------------------------------------------------------
    def test_inventory_list_requires_login(self):
        self.assertLoginRequired(reverse('inventory'))

    def test_inventory_list_shows_only_own_rows(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse('inventory'))
        self.assertEqual([i.pk for i in response.context['inventory_items']], [self.alice_milk.pk])
        self.assertEqual(response.context['total_amount'], Decimal('10'))

    def test_inventory_list_shows_household_rows_to_every_member(self):
        for member in (self.carol, self.dave):
            with self.subTest(member=member.email):
                self.client.force_login(member)
                response = self.client.get(reverse('inventory'))
                self.assertEqual([i.pk for i in response.context['inventory_items']], [self.home_milk.pk])

    def test_inventory_ajax_shows_only_own_rows(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse('inventory'), headers={'x-requested-with': 'XMLHttpRequest'})
        self.assertEqual([i['id'] for i in response.json()['items']], [self.alice_milk.pk])

    # -- writing -----------------------------------------------------------------------------------
    def test_owner_can_update_own_inventory(self):
        self.client.force_login(self.alice)
        self.client.post(reverse('update_inventory'), {f'quantity_{self.alice_milk.pk}': '2',
                                                       f'amount_{self.alice_milk.pk}': '8'})
        self.alice_milk.refresh_from_db()
        self.assertEqual(self.alice_milk.quantity, Decimal('2'))
        self.assertEqual(self.alice_milk.average_price, Decimal('4'))

    def test_household_member_can_update_household_inventory(self):
        self.client.force_login(self.dave)
        self.client.post(reverse('update_inventory'), {f'quantity_{self.home_milk.pk}': '3',
                                                       f'amount_{self.home_milk.pk}': '6'})
        self.home_milk.refresh_from_db()
        self.assertEqual(self.home_milk.quantity, Decimal('3'))

    @known_bug('Phase 1: update_inventory updates rows by id with no owner filter (IDOR)')
    def test_user_cannot_update_another_users_inventory(self):
        self.client.force_login(self.alice)
        self.client.post(reverse('update_inventory'), {f'quantity_{self.bob_milk.pk}': '0',
                                                       f'amount_{self.bob_milk.pk}': '0'})
        self.bob_milk.refresh_from_db()
        self.assertEqual(self.bob_milk.quantity, Decimal('7'))
        self.assertEqual(self.bob_milk.amount, Decimal('21'))

    @known_bug('Phase 1: update_inventory updates household rows by id with no household filter (IDOR)')
    def test_member_cannot_update_another_households_inventory(self):
        from users.models import HouseHold
        other = HouseHold.objects.create(name='other', nickname='other_home', address='x', owner=self.bob)
        foreign = self.household_inventory(other, self.milk, quantity=4, amount=4)
        self.client.force_login(self.carol)
        self.client.post(reverse('update_inventory'), {f'quantity_{foreign.pk}': '0'})
        foreign.refresh_from_db()
        self.assertEqual(foreign.quantity, Decimal('4'))

    @known_bug('Phase 1: update_inventory has no @login_required')
    def test_update_inventory_requires_login(self):
        self.assertLoginRequired(reverse('update_inventory'), method='post',
                                 data={f'quantity_{self.bob_milk.pk}': '0'})

    @known_bug('Phase 1: user_category_settings has no @login_required')
    def test_category_settings_require_login(self):
        self.assertLoginRequired(reverse('user_category_settings'))

    def test_category_settings_show_and_change_only_own_categories(self):
        mine = UserProductCategory.objects.create(user=self.alice, product_category=self.cat_dairy)
        bobs = UserProductCategory.objects.create(user=self.bob, product_category=self.cat_dairy)
        home = HouseholdProductCategory.objects.create(household=self.household, product_category=self.cat_dairy)
        self.client.force_login(self.alice)
        response = self.client.get(reverse('user_category_settings'))
        self.assertEqual([c.pk for c in response.context['user_categories']], [mine.pk])

        self.client.post(reverse('user_category_settings'), {
            f'direct_planning_{mine.pk}': 'on', f'daily_consumption_{mine.pk}': '1', f'minimum_quantity_{mine.pk}': '2',
            f'direct_planning_{bobs.pk}': 'on', f'daily_consumption_{bobs.pk}': '9', f'minimum_quantity_{bobs.pk}': '9',
        })
        mine.refresh_from_db(), bobs.refresh_from_db(), home.refresh_from_db()
        self.assertTrue(mine.direct_planning)
        self.assertFalse(bobs.direct_planning)
        self.assertEqual(bobs.daily_consumption, Decimal('0'))
        self.assertFalse(home.direct_planning)

    # -- shopping lists ----------------------------------------------------------------------------
    def test_foreign_shopping_list_is_404(self):
        bobs_list = ShoppingList.objects.create(user=self.bob, items=['Мляко'])
        home_list = HouseholdShoppingList.objects.create(household=self.household, items=['Сапун'])
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse('shopping_list_view', args=[bobs_list.pk])).status_code, 404)
        # ids of household lists live in another table; alice has no list with that id either
        ShoppingList.objects.filter(pk=home_list.pk).exclude(user=self.alice).delete()
        self.assertEqual(self.client.get(reverse('shopping_list_view', args=[home_list.pk + 1000])).status_code, 404)

    def test_all_shopping_lists_shows_only_own(self):
        mine = ShoppingList.objects.create(user=self.alice, items=['Мляко'])
        ShoppingList.objects.create(user=self.bob, items=['Сапун'])
        self.client.force_login(self.alice)
        response = self.client.get(reverse('all_shopping_lists'))
        self.assertEqual([l.pk for l in response.context['shopping_lists']], [mine.pk])

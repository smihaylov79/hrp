"""Shared fixtures for the test-suite.

`HrpTestCase` gives every test:
  * no outbound HTTP (context processors / views call external APIs on render),
  * a small world of users: two solo users (alice, bob) and one household (carol + dave),
  * helpers to create purchases, incomes and inventory rows.
"""
import os
import unittest
from datetime import date
from decimal import Decimal
from unittest import mock

import requests
from django.test import TestCase

from income.models import Income, IncomeType
from inventory.models import HouseholdInventoryProduct, InventoryProduct
from shopping.models import MainCategory, Product, ProductCategory, Shop, Shopping, ShoppingProduct
from users.models import CustomUser, HouseHold

PASSWORD = 'Ineedstrongpassord123!@'


def known_bug(reason):
    """Mark a test that documents a bug scheduled in IMPROVEMENT_PLAN.md.

    The test states the *correct* behaviour and is expected to fail until the named phase fixes it.
    When the fix lands the test starts passing ("unexpected success" fails the run) -> remove the marker.
    """
    def decorator(test):
        test.known_bug = reason
        if os.getenv('HRP_SHOW_KNOWN_BUGS'):   # run them as normal tests to see the real tracebacks
            return test
        return unittest.expectedFailure(test)
    return decorator


def make_user(email, first_name='Test', household=None):
    user = CustomUser.objects.create_user(
        email=email, password=PASSWORD, first_name=first_name, last_name='User')
    if household is not None:
        user.household = household
        user.save(update_fields=['household'])
    return user


def make_household(owner, nickname):
    household = HouseHold.objects.create(name=nickname, nickname=nickname, address='ул. Тест 1', owner=owner)
    owner.household = household
    owner.save(update_fields=['household'])
    return household


def make_purchase(user, product, price, quantity=1, currency='EUR', on_date=None, shop=None,
                  not_for_household=False):
    """One Shopping with one ShoppingProduct. Returns the ShoppingProduct."""
    shop = shop or Shop.objects.get_or_create(name='Тестов магазин')[0]
    shopping = Shopping.objects.create(user=user, date=on_date or date.today(), shop=shop, currency=currency)
    return ShoppingProduct.objects.create(
        shopping=shopping, product=product, quantity=Decimal(str(quantity)), price=Decimal(str(price)),
        discount=Decimal('0'), not_for_household=not_for_household)


def make_income(user, amount, currency='EUR', on_date=None, type_name='Заплата'):
    income_type = IncomeType.objects.get_or_create(name=type_name)[0]
    return Income.objects.create(user=user, income_type=income_type, amount=Decimal(str(amount)),
                                 currency=currency, date_received=on_date or date.today())


class HrpTestCase(TestCase):
    """Base class: blocks network access and builds the common users/products."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Any real HTTP call in a test is a bug: fail fast instead of hanging on a timeout.
        cls._no_network = mock.patch.object(
            requests.sessions.Session, 'request',
            side_effect=requests.exceptions.ConnectionError('network access is disabled in tests'))
        cls._no_network.start()
        cls.addClassCleanup(cls._no_network.stop)

    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user('alice@example.com', 'Alice')          # solo
        cls.bob = make_user('bob@example.com', 'Bob')                # solo
        cls.carol = make_user('carol@example.com', 'Carol')          # household owner
        cls.household = make_household(cls.carol, 'carol_home')
        cls.dave = make_user('dave@example.com', 'Dave', household=cls.household)

        cls.main_food = MainCategory.objects.create(name='Храна')
        cls.main_home = MainCategory.objects.create(name='Дом')
        cls.cat_dairy = ProductCategory.objects.create(name='Млечни', main_category=cls.main_food)
        cls.cat_clean = ProductCategory.objects.create(name='Почистване', main_category=cls.main_home)
        cls.milk = Product.objects.create(name='Мляко', category=cls.cat_dairy)
        cls.soap = Product.objects.create(name='Сапун', category=cls.cat_clean)
        cls.shop = Shop.objects.create(name='Тестов магазин')

    # -- helpers ---------------------------------------------------------------------------------
    @staticmethod
    def user_inventory(user, product, quantity=1, amount=1):
        return InventoryProduct.objects.create(
            user=user, product=product, category=product.category,
            quantity=Decimal(str(quantity)), amount=Decimal(str(amount)))

    @staticmethod
    def household_inventory(household, product, quantity=1, amount=1):
        return HouseholdInventoryProduct.objects.create(
            household=household, product=product, category=product.category,
            quantity=Decimal(str(quantity)), amount=Decimal(str(amount)))

    def assertLoginRequired(self, url, method='get', data=None):
        """Anonymous request must be redirected to the login page (not crash, not render)."""
        self.client.logout()
        response = getattr(self.client, method)(url, data or {})
        self.assertEqual(response.status_code, 302, f'{url} is reachable without login')
        self.assertTrue(response['Location'].startswith('/users/please-login/'),
                        f'{url} redirects to {response["Location"]}, not to login')

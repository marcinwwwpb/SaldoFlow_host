from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AccountFlowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='jan@example.com',
            email='jan@example.com',
            password='haslo12345',
            is_active=True,
        )

    def test_logout_requires_post_and_redirects_home(self):
        self.client.login(username='jan@example.com', password='haslo12345')
        response = self.client.post(reverse('accounts_logout'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], reverse('home'))

    def test_register_placeholders_are_generic(self):
        response = self.client.get(reverse('accounts_register'))
        self.assertContains(response, 'placeholder="Imię"')
        self.assertContains(response, 'placeholder="Nazwisko"')
        self.assertNotContains(response, 'Marcin Węgliński')

    def test_can_login_with_username_or_email(self):
        login_response = self.client.post(reverse('accounts_login'), {
            'username': 'jan@example.com',
            'password': 'haslo12345',
        })
        self.assertEqual(login_response.status_code, 302)
        self.client.logout()
        user = get_user_model().objects.create_user(username='marcin_login', email='marcin@login.local', password='danzel12', is_active=True)
        login_response = self.client.post(reverse('accounts_login'), {
            'username': 'marcin_login',
            'password': 'danzel12',
        })
        self.assertEqual(login_response.status_code, 302)

    def test_home_redirects_authenticated_user_to_center(self):
        self.client.login(username='jan@example.com', password='haslo12345')
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, reverse('module_selector'))

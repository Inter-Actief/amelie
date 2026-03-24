from django.test import testcases
from amelie.personal_tab.helpers import kcal_equivalent


class KCalEquivalentTest(testcases.SimpleTestCase):
    def test_kcal_equivalent_en(self):
        kcal = 15
        expected = ''
        self.assertEqual(kcal_equivalent(kcal, 'en'), expected)

        kcal = 16
        expected = '1 tomato'
        self.assertEqual(kcal_equivalent(kcal, 'en'), expected)

        kcal = 17
        expected = '1 tomato'
        self.assertEqual(kcal_equivalent(kcal, 'en'), expected)

        kcal = 1287
        expected = '1 chocolate bar & 5 cans of cola & 2 tomatoes'
        self.assertEqual(kcal_equivalent(kcal, 'en'), expected)

    def test_kcal_equivalent_nl(self):
        kcal = 15
        expected = ''
        self.assertEqual(kcal_equivalent(kcal, 'nl'), expected)

        kcal = 16
        expected = '1 tomaat'
        self.assertEqual(kcal_equivalent(kcal, 'nl'), expected)

        kcal = 17
        expected = '1 tomaat'
        self.assertEqual(kcal_equivalent(kcal, 'nl'), expected)

        kcal = 1287
        expected = '1 chocolade reep & 5 blikjes cola & 2 tomaten'
        self.assertEqual(kcal_equivalent(kcal, 'nl'), expected)

    def test_kcal_equivalent_nocrash(self):
        # Test a random set of possible values to make sure none throw an error
        for kcal in range(1000):
            # noinspection PyBroadException
            try:
                kcal_equivalent(kcal, 'en')
            except:
                self.fail(f'kcal_equivalent threw an exception for kcal={kcal}')

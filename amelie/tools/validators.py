from django.core.exceptions import ValidationError

from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _


@deconstructible
class CheckDigitValidator(object):
    """
    Validator for the "elfproef" check digit validation scheme used by e.g. the University of Twente
    """
    def __init__(self, length):
        self.length = length

    def __call__(self, number):
        factors = range(self.length, 0, -1)

        total = 0

        for i, factor in enumerate(factors):
            digit = (number // 10 ** (self.length - i - 1)) % 10
            total += digit * factor

        if total % 11 != 0:
            raise ValidationError(_("%d is incorrect according to the check digit.") % number)

    def __eq__(self, other):
        return self.length == other.length

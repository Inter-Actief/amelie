from django.shortcuts import render
from django.template import RequestContext, Template
from django.utils.translation import gettext_lazy as _l

from amelie.tools.decorators import require_board


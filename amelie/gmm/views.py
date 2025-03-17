from django.db.models import Q
from django.shortcuts import render

from amelie.gmm.models import GMM
from amelie.tools.decorators import require_lid


@require_lid
def index(request):
    if request.april_active:
        gmms = GMM.objects.filter(~Q(date = None)).order_by("?")
        gmms_without_date = GMM.objects.filter(date = None).order_by("?")
    else:
        gmms = GMM.objects.filter(~Q(date = None))
        gmms_without_date = GMM.objects.filter(date = None)
    return render(request, 'gmm_overview.html', locals())

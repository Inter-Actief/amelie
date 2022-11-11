from django.conf import settings
from django.template import loader
from jsonrpc import jsonrpc_method

from amelie.api.exceptions import DoesNotExistError
from amelie.companies.models import Company


@jsonrpc_method('getCompanyStream() -> Array', validate=True)
def get_company_list(request):
    companies = Company.objects.active().filter(show_in_app=True)
    result = []

    for company in companies:
        result.append({
            "imageUrl": "%s%s" % (settings.MEDIA_URL, str(company.app_logo)) if company.app_logo else None,
            "name": company.name,
            "id": company.id,
        })
    return result


@jsonrpc_method('getCompanyDetailed(Number) -> Array', validate=True)
def get_company_detail(request, reqid):
    try:
        company = Company.objects.get(id=reqid)
    except Company.DoesNotExist as e:
        raise DoesNotExistError(str(e))

    t = loader.get_template('common/company_detail.html')

    c = {
        'companyName': company.name,
        'companyLogo': company.app_logo,
        'content': company.profile,
    }

    result = {
        "id": company.id,
        "name": company.name,
        "description": t.render(c, request),
        "markdown": company.profile,
        "imageUrl": "%s%s" % (settings.MEDIA_URL, str(company.app_logo)) if company.app_logo else None,
    }

    return result

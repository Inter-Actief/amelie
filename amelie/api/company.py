from typing import List, Dict

from modernrpc import RpcRequestContext

from django.conf import settings
from django.template import loader

from amelie.api.api import api_server
from amelie.api.exceptions import DoesNotExistError
from amelie.companies.models import Company


@api_server.register_procedure(name='getCompanyStream')
def get_company_list() -> List[Dict]:
    """
    Retrieves a list of partnered companies.

    **Module**: `company`

    **Authentication:** _(none)_

    **Parameters:** _(none)_

    **Return:**
      `List[Dict]`: An array of dictionaries containing basic company info.

      Each returned element in the list has the following fields:

        - id: The identifier for this company
        - name: The name of this company
        - imageUrl: An URL of a logo for this company (optional)
        - shortDescription: A short description of the company (max 120 chars)

    **Example:**

        --> {"method":"getCompanyStream", "params":[]}
        <-- {"result": [{
                "id": 28,
                "name": "University of Twente",
                "imageUrl": "https://pbs.twimg.com/profile_image.png",
                "shortDescription": "The University of Twente is a technical university in Enschede, the Netherlands."
            }, {...}, ...]
        }
    """
    companies = Company.objects.active().filter(show_in_app=True)
    result = []

    for company in companies:
        result.append({
            "imageUrl": "%s%s" % (settings.MEDIA_URL, str(company.app_logo)) if company.app_logo else None,
            "name": company.name,
            "id": company.id,
            "shortDescription": company.short_description,
        })
    return result


@api_server.register_procedure(name='getCompanyDetailed', context_target='ctx')
def get_company_detail(company_id, ctx: RpcRequestContext = None, **kwargs) -> Dict:
    """
    Retrieves company details, including its promotional content.

    **Module**: `company`

    **Authentication:** _(none)_

    **Parameters:**
      This method accepts the following parameters:

        - company_id: The id of the requested item.

    **Return:**
      `Dict`: A dictionary containing detailed company info.

      The dictionary contains the following fields:

        - id: The identifier for this company
        - name: The name of this company
        - shortDescription: A short description of the company (max 120 chars)
        - description: A HTML rendered profile page of the company
        - markdown: A markdown version of the company profile text
        - imageUrl: An URL of a logo for this company (optional)

    **Raises:**

      DoesNotExistError: The company with this ID does not exist.

    **Example:**

        --> {"method":"getCompanyDetailed", "params":[28]}
        <-- {"result": {
                "id": 28,
                "name": "University of Twente",
                "imageUrl": "https://pbs.twimg.com/profile_image.png",
                "shortDescription": "The University of Twente is a technical university in Enschede, the Netherlands.",
                "description": "<html><!--html contents--></html>",
                "markdown": "markdown _contents_"
        }}
    """
    try:
        company = Company.objects.get(id=company_id)
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
        "shortDescription": company.short_description,
        "description": t.render(c, ctx.request),
        "markdown": company.profile,
        "imageUrl": "%s%s" % (settings.MEDIA_URL, str(company.app_logo)) if company.app_logo else None,
    }

    return result

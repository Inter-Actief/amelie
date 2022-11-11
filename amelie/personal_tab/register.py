from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.utils.translation import gettext as _

from amelie.members.models import Person
from amelie.personal_tab.models import RFIDCard
from amelie.tools.mixins import RequireBoardMixin


class CardRegistrationIndex(RequireBoardMixin, TemplateView):
    template_name = "register/register_card_index.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {})

    def post(self, request, *args, **kwargs):
        # LOG IN
        username = request.POST['username'] if 'username' in request.POST else ''
        password = request.POST['password'] if 'password' in request.POST else ''

        if not username or not password:
            error_text = _('Username and password are obligatory')
            return render(request, 'register/register_card_error.html', {'error_text': error_text})

        from django.contrib.auth import authenticate

        user = authenticate(request=request, username=username, password=password)
        if user is None or user.is_active is False:
            error_text = _('Username and/or password incorrect.')
            return render(request, 'register/register_card_error.html', {'error_text': error_text})

        if not hasattr(user, 'person'):
            error_text = _('You are (not yet/ no longer) a member of Inter-Actief. Ask the board for a membership form.')
            return render(request, 'register/register_card_error.html', {'error_text': error_text})

        request.session['REGISTER_PERSON_ID'] = user.person.id
        # Continue to CardRegistrationScan.
        return redirect('personal_tab:register_scan')


class CardRegistrationScan(RequireBoardMixin, TemplateView):
    template_name = "register/register_card_scan.html"

    def get(self, request, *args, **kwargs):
        if 'REGISTER_PERSON_ID' not in request.session:
            return redirect('personal_tab:register_index')

        rfid_person_id = request.session['REGISTER_PERSON_ID']
        # Delete rfid user from session, add again when needed
        del request.session['REGISTER_PERSON_ID']

        try:
            Person.objects.get(id=rfid_person_id)
        except Person.DoesNotExist:
            return redirect('personal_tab:register_index')

        request.session['REGISTER_PERSON_ID'] = rfid_person_id
        return render(request, self.template_name, {})

    def post(self, request, *args, **kwargs):
        if 'REGISTER_PERSON_ID' not in request.session:
            return redirect('personal_tab:register_index')

        rfid_person_id = request.session['REGISTER_PERSON_ID']
        # Delete rfid user from session, add again when needed
        del request.session['REGISTER_PERSON_ID']

        try:
            rfid_person = Person.objects.get(id=rfid_person_id)
        except Person.DoesNotExist:
            return redirect('personal_tab:register_index')

        # Get the card information
        if 'tag' not in request.POST or not request.POST['tag']:
            # ERROR: No cards are found in the result data.
            error_text = _('No cards are scanned.')
            return render(request, 'register/register_card_error.html', {'error_text': error_text})

        tag = request.POST['tag']
        # One card was scanned. Check if the card(s) are already registered to someone.
        people = [r.person for r in RFIDCard.objects.filter(code=tag, active=True)]

        if people:
            # ERROR: This card is already registered to someone
            error_text = _('This RFID card is already registered.')
            return render(request, 'register/register_card_error.html', {'error_text': error_text})

        # Only one card was scanned and it is not yet registered
        RFIDCard(person=rfid_person, code=tag, active=True).save()

        success_text = _('Card is registered.')
        return render(request, 'register/register_card_success.html', {'success_text': success_text})

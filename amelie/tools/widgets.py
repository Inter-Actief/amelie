from datetime import timedelta

from django.forms.widgets import DateInput, SplitDateTimeWidget, MultiWidget, NumberInput, HiddenInput, TextInput
from django.template.loader import get_template
from django.utils.translation import gettext as _

from amelie.members.models import Person


class DateTimeSelector(SplitDateTimeWidget):
    """
    A Widget that splits datetime input into two <input type="text"> boxes with JavaScript selectors.
    """

    def __init__(self, attrs=None):
        super(DateTimeSelector, self).__init__(attrs, '%Y-%m-%d', '%H:%M')
        # self.widgets[0].input_type = 'date' # commented out because we use a non-native date picker now
        # self.widgets[1].input_type = 'time' # commented out because we use a non-native date picker now
        if (attrs and 'class' in attrs or
                (self.widgets[0].attrs and 'class' in self.widgets[0].attrs)):
            self.widgets[0].attrs['class'] += ' date_selector'
            self.widgets[1].attrs['class'] += ' time_selector'
        else:
            self.widgets[0].attrs['class'] = 'date_selector'
            self.widgets[1].attrs['class'] = 'time_selector'


class DateTimeSelectorWithToday(DateTimeSelector):
    def render(self, *args, **kwargs):
        return super(DateTimeSelectorWithToday, self).render(*args, **kwargs) + \
               get_template("set_as_today_button.html").render()


class DateSelector(DateInput):
    """
    A Widget that uses a <input type="text"> box with JavaScript selector.
    """

    def __init__(self, attrs=None):
        if not attrs:
            attrs = {}
        if 'class' in attrs:
            attrs['class'] += ' date_selector'
        else:
            attrs['class'] = 'date_selector'
        super(DateSelector, self).__init__(attrs, '%Y-%m-%d')


class SplitDurationWidget(MultiWidget):
    def __init__(self, attrs=None):
        self._days = NumberInput(attrs={'placeholder': _('Days'), 'min': '0', 'max': '999999999'})  # as dictated by python
        self._hours = NumberInput(attrs={'placeholder': _('Hours'), 'min': '0', 'max': '23'})
        self._minutes = NumberInput(attrs={'placeholder': _('Minutes'), 'min': '0', 'max': '59'})

        widgets = [self._days, self._hours, self._minutes]

        super(SplitDurationWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        try:
            if value:
                if isinstance(value, str):
                    value = timedelta(seconds=int(value))

                days = value // timedelta(days=1)
                hours = (value - timedelta(days=days)) // timedelta(hours=1)
                minutes = (value - timedelta(days=days, hours=hours)) // timedelta(minutes=1)
                return [days, hours, minutes]
        except ValueError:
            return [None, None, None]

        return [None, None, None]

    def format_output(self, rendered_widgets):
        return ' '.join(rendered_widgets)

    def value_from_datadict(self, *args, **kwargs):
        days, hours, minutes = super(SplitDurationWidget, self).value_from_datadict(*args, **kwargs)

        if not any(thing is None for thing in (days, hours, minutes)):
            try:
                return str(int(timedelta(days=int(days), hours=int(hours), minutes=int(minutes)).total_seconds()))
            except ValueError:
                return ""

        return ""


class MemberSelect(MultiWidget):
    def __init__(self, attrs=None, hidden_attrs=None, text_attrs=None):
        ta = {'class': 'autocomplete-input', 'list': 'autocomplete-datalist'}
        if text_attrs:
            ta.update(text_attrs)
        super().__init__((HiddenInput(attrs=hidden_attrs), TextInput(attrs=ta)), attrs)

    def decompress(self, value):
        if value:
            return value, Person.objects.get(id=value).full_name()
        return None, None

    def format_output(self, rendered_widgets):
        return '<span class="ui-widget">'+''.join(rendered_widgets) + '</span>'

    def value_from_datadict(self, *args, **kwargs):
        pid, name = super().value_from_datadict(*args, **kwargs)
        if pid and name:
            return pid
        return None

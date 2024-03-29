from django.forms.forms import BaseForm
from django.forms.utils import ErrorList


def as_div(self):
    """Render a form as a div with the correct CSS class"""

    return self._html_output(
        normal_row='<div class="form-row"%(html_class_attr)s>%(label)s %(field)s %(help_text)s</div>',
        error_row='<div class="form-row"><label></label>%s</div>',
        row_ender='</div>',
        help_text_html=' <span class="note">%s</span>',
        errors_on_separate_row=True)


class DivErrorList(ErrorList):
    """Render errors in a div with the correct css class"""

    def as_divs(self):
        if not self:
            return ''

        return '<p class="icon neg">%s</p>' % ''.join(['%s' % e for e in self])

    def __str__(self):
        return self.as_divs()


def update_init(old_init):
    """Override the __init__ so that the correct error_class is used"""

    def _update_init(self, *args, **kwargs):
        kwargs_new = {'error_class': DivErrorList}
        kwargs_new.update(kwargs)
        old_init(self, *args, **kwargs_new)

    return _update_init


def inject_style(*args):
    """
    Override methods and add new methods so that the new IA style is used everywhere in Forms,
    without having to change it everywhere.
    """

    for form in args:
        # Type checking
        if not issubclass(form, BaseForm):
            raise Exception("%s is not an instance of BaseForm" % form.__name__)

        # Inject
        form.as_div = as_div
        form.__init__ = update_init(form.__init__)
        form.__str__ = as_div

from django.core.management.commands import makemessages

class Command(makemessages.Command):
    """
    Extends the makemessages command to look for additional aliases for gettext_lazy.
    """
    xgettext_options = makemessages.Command.xgettext_options + ['--keyword=_l']

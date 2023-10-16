import ast
import os
import re
import sys
from distutils.sysconfig import get_python_lib

import polib
from django.core.management.commands import makemessages
from django.core.management.commands.makemessages import settings
from django.template.loader import _engine_list
from django.template.loaders.app_directories import Loader
from django.test import TestCase

from amelie import settings

POFILE_PATH = './locale/nl/LC_MESSAGES/django.po'
MOFILE_PATH = './locale/nl/LC_MESSAGES/django.mo'

REGEX_MSGID = re.compile(r'(?P<files>(#.*\n)+)msgid +(?P<text>(".*"\n)+)')
REGEX_IGNORED = [
    re.compile(r'{% +blocktrans.*?%}.+?{% +endblocktrans +%}'),
    re.compile(r'{% +comment.*?%}.+?{% +endcomment +%}'), re.compile(r'<!--.*?-->'),
    re.compile(r'<script.+?</script>'), re.compile(r'<style.+?</style>'), re.compile(r'{[{%#].+?[}%#]}'),
    re.compile(r'<input[^>]*?type="(?:input|submit|text)"value=(?:\'(?:\'[^>]*?>)?|"(?:"[^>]*?>)?)'),
    re.compile(r'<.+?>')
]

REGEX_ERROR_PAGES = re.compile(r'^(\d{3}\.html|jelte.+)$')
EXTENSIONS = ['mail', 'html', 'txt', 'py']
# Add only names or word groups that are best matched with regular expressions. No extra English words should not be added.
IGNORED_WORDS = [
    "\\bNL\\b", "\\bEN\\b", "inter- *actief\\b", "\\bu?twente\\b", "\\bhome\\b", "\\bcompany corner\\b",
    "\\bGoogle Maps\\b", "Postcode.nl", "euro?", '\\bSponsored by\\b', '\\binbitween\\b', 'BP', 'Am[eé]lie',
    'https://(www\\.)?inter-actief\\.net', '\\bAccountbeheer\\b', '\\bweek\\b', '\\bEnglish version Nederlandse versie',
    '(?:contact|accountbeheer)@inter-actief\\.net', 'https?://www\\.inter-actief\\.utwente\\.nl(?:/profile/edit)?',
    '\\bEUR\\b', '\\b-\\b'
]

REGEX_ACCEPTED = re.compile('^([^a-zA-Z]|&.*?;|\\b\\w\\b|{})*$'.format('|'.join(IGNORED_WORDS)), re.IGNORECASE)
TEMPLATE_FOLDERS = list(Loader(_engine_list(None)).get_dirs())
for t in settings.TEMPLATES:
    TEMPLATE_FOLDERS += t['DIRS']
TEMPLATE_FOLDERS = [os.path.abspath(x) for x in TEMPLATE_FOLDERS]
#
IGNORED_PATHS = [
    "./amelie/personal_tab/templates/pos",
    "./amelie/gmm/templates/gmm_overview.html",
    "./amelie/tools/templates/tools_mailtemplatetest.html",
    "./amelie/api/templates/api/doc_index.html",
    "./amelie/api/templates/api/doc_accordion_method.html"
]
IGNORED_PATHS += [get_python_lib()]
try:
    # Should work better in non virtualenvs
    import site

    IGNORED_PATHS += site.getsitepackages()
except AttributeError:
    pass
IGNORED_PATHS = [os.path.abspath(x) for x in IGNORED_PATHS]
lines = ''
warnings = 0


class TranslateTestCase(TestCase):
    po_file = polib.pofile(POFILE_PATH)
    mo_file = polib.mofile(MOFILE_PATH)

    def warn(self, message):
        global warnings
        warnings += 1
        sys.stderr.write('\n---------- Warning {} ----------\n{}\n'.format(warnings, message))

    def test_untranslated(self):
        for e in self.po_file:
            if 'fuzzy' in e.flags:
                self.warn('Fuzzy text exist in "{}":\n{}'.format(POFILE_PATH, e))
            if not e.obsolete and not e.translated():
                self.warn('Untranslated text exist in "{}":\n{}'.format(POFILE_PATH, e))

    def test_is_compiled(self):
        for pe in self.po_file:
            if not pe.obsolete:
                me = self.mo_file.find(pe.msgid)
                if not me or pe.msgstr != me.msgstr:
                    self.warn('Po file {} has not been compiled to {}'.format(POFILE_PATH, MOFILE_PATH))

    def test_makemessages_run(self):
        mmc = makemessages.Command()
        mmc.ignore_patterns = ['bin/*', 'lib/*', 'include/*', 'CVS', '.*', '*~', '*.pyc']
        mmc.symlinks = False
        mmc.locale_paths = list(settings.LOCALE_PATHS)
        mmc.verbosity = 0
        mmc.extensions = makemessages.handle_extensions(EXTENSIONS)
        mmc.domain = 'django'
        makemessages.write_pot_file = _new_write_pot_file
        file_list = mmc.find_files('.')
        mmc.process_files(file_list)
        msgids = [e.msgid for e in self.po_file if not e.obsolete]
        for m in REGEX_MSGID.finditer(lines):
            text = ast.literal_eval(m.group('text').replace('"\n"', ''))
            if text and text not in msgids:
                self.warn('Po file {} does not contain\n<<<\n{}\n>>>\nwhich can be found in:\n{}'.format(
                    POFILE_PATH, text, m.group('files')))

    def test_templates_untranslated(self):
        errors = []
        for template_path in find_all_templates():
            with open(template_path) as template:
                content = ''.join(template.readlines())
            if 'i18n' not in content:
                continue
            x = 0
            while x != len(content):
                x = len(content)
                content = content.replace('\n', ' ').replace('  ', ' ').replace('\t', ' ')
            for regex in REGEX_IGNORED:
                for match in regex.findall(content):
                    content = content.replace(match, ' ')
            x = 0
            while x != len(content):
                x = len(content)
                content = content.replace('\n', ' ').replace('  ', ' ').replace('\t', ' ')
            if content and not REGEX_ACCEPTED.fullmatch(content):
                # The first bit makes the file link clickable in pycharm
                errors.append('File "{}", line 0\n{}\n'.format((template_path), content))
        if errors:
            self.fail('Total amount of unaccepted text: {}\n\n{}'.format(len(errors), '\n'.join(errors)))


def _new_write_pot_file(ignored, msgs):
    global lines
    lines = msgs


def find_all_templates(path=TEMPLATE_FOLDERS):
    for templates in path:
        if any(templates.startswith(y) for y in IGNORED_PATHS):
            continue
        for p, sds, fs in os.walk(templates):
            for f in sorted(fs):
                file = os.path.join(p, f)
                if (f.endswith('.html') or f.endswith('.mail')) and not REGEX_ERROR_PAGES.fullmatch(f) and not any(
                        file.startswith(y) for y in IGNORED_PATHS):
                    yield file

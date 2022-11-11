import unicodedata

CHAR_REPLACEMENT = {
    'LATIN CAPITAL LETTER AE': u"AE",
    'LATIN CAPITAL LETTER O WITH STROKE': u"O",
    'LATIN SMALL LETTER SHARP S': u"ss",
    'LATIN SMALL LETTER AE': u"ae",
    'LATIN SMALL LETTER O WITH STROKE': u"o",
}


def normalize_to_ascii(text):
    """
    Normalize text to ASCII by replacing and removing special characters.
    """
    if text is not None:
        norm_text = ''
        for char in text:
            name = unicodedata.name(char)
            if name in CHAR_REPLACEMENT:
                norm_text += CHAR_REPLACEMENT[name]
            else:
                norm_text += char
        return unicodedata.normalize('NFKD', norm_text).encode('ASCII', 'ignore').decode('ASCII')
    else:
        return ''

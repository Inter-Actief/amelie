from urllib.request import urlopen, URLError, HTTPError

from bs4 import BeautifulSoup


def summaries_get_courses(filter_=""):
    binf = summaries_fetch_data("Vakken", "Informatica", filter_)
    bbit = summaries_fetch_data("Vakken", "Bedrijfsinformatietechnologie", filter_)
    minf = summaries_fetch_data("Vakken", "Computer_Science", filter_)
    mbit = summaries_fetch_data("Vakken", "Business_Information_Technology", filter_)

    result = []

    for item in (binf + bbit + minf + mbit):
        if item not in result:
            result.append(item)
    result.sort(key=lambda x: x['name'])
    return result


def summaries_fetch_data(what, category, filter_):
    wikiurl = "http://samenvattingen.student.utwente.nl/wikibot.xml.php?what=%s&categorie=%s&filter=%s" %\
              (str(what), str(category), str(filter_))

    try:
        data = urlopen(wikiurl, timeout=5).read()
        soup = BeautifulSoup(data, "html.parser")
        courses = [{'name': x.titel.string, 'code': x.vakcode.string, 'url': x.url.string} for x in soup.findAll('vak')]
    except (URLError, HTTPError):
        courses = []

    return courses

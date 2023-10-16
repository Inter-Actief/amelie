KCAL_TABLE = {
    16: {
        'single': {
            'nl': 'tomaat',
            'en': 'tomato',
        },
        'multiple': {
            'nl': 'tomaten',
            'en': 'tomatoes'
        }
    },
    140: {
        'single': {
            'nl': 'blikje cola',
            'en': 'can of cola'
        },
        'multiple': {
            'nl': 'blikjes cola',
            'en': 'cans of cola'
        }
    },
    555: {
        'single': {
            'nl': 'chocolade reep',
            'en': 'chocolate bar',
        },
        'multiple': {
            'nl': 'chocolade repen',
            'en': 'chocolate bars'
        }
    },
    3500: {
        'single': {
            'nl': 'volledig brood',
            'en': 'entire bread',
        },
        'multiple': {
            'nl': 'volledige broden',
            'en': 'loaves of bread'
        }
    },
    4000: {
        'single': {
            'nl': 'kg suiker',
            'en': 'kilo of sugar'
        },
        'multiple': {
            'nl': 'kg suiker',
            'en': 'kilos of sugar'
        }
    },
    6400: {
        'single': {
            'nl': 'liter mayonaise',
            'en': 'litre of mayonaise'
        },
        'multiple': {
            'nl': 'liters mayonaise',
            'en': 'litres of mayonaise',
        }
    },
}


def kcal_equivalent(kcal, language):
    # Credits to https://www.koderdojo.com/blog/algorithm-to-make-change-in-python-dynamic-programming
    minimum_number_of_currency = [0]
    currency_composition = [[]]
    kcal_amounts = KCAL_TABLE.keys()

    for i in range(kcal):
        best = 100000000
        best_currency_composition = None

        for j in kcal_amounts:
            if i - j > -1 and minimum_number_of_currency[i - j] + 1 < best:
                best = minimum_number_of_currency[i - j] + 1
                best_currency_composition = currency_composition[i - j] + [j]

        minimum_number_of_currency.append(best)
        currency_composition.append(best_currency_composition)

    best = currency_composition[-1]

    grouped = {}

    for i in best:
        if i in grouped:
            grouped[i] += 1
        else:
            grouped[i] = 1

    string = ''

    for product, amount in grouped.items():
        if amount > 1:
            string += str(amount) + ' ' + KCAL_TABLE[product]['multiple'][language]
        else:
            string += '1 ' + KCAL_TABLE[product]['single'][language]
        string += ' & '

    string = string[:-2]

    return string

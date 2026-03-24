KCAL_TABLE = {
    16: {
        'single': {
            'nl': 'tomaat',
            'en': 'tomato',
        },
        'multiple': {'nl': 'tomaten', 'en': 'tomatoes'},
    },
    140: {
        'single': {'nl': 'blikje cola', 'en': 'can of cola'},
        'multiple': {'nl': 'blikjes cola', 'en': 'cans of cola'},
    },
    555: {
        'single': {
            'nl': 'chocolade reep',
            'en': 'chocolate bar',
        },
        'multiple': {'nl': 'chocolade repen', 'en': 'chocolate bars'},
    },
    3500: {
        'single': {
            'nl': 'volledig brood',
            'en': 'entire bread',
        },
        'multiple': {'nl': 'volledige broden', 'en': 'loaves of bread'},
    },
    4000: {
        'single': {'nl': 'kg suiker', 'en': 'kilo of sugar'},
        'multiple': {'nl': 'kg suiker', 'en': 'kilos of sugar'},
    },
    6400: {
        'single': {'nl': 'liter mayonaise', 'en': 'litre of mayonnaise'},
        'multiple': {
            'nl': 'liters mayonaise',
            'en': 'litres of mayonnaise',
        },
    },
}


def kcal_equivalent(kcal, language):
    assert kcal >= 0

    # Credits to https://www.koderdojo.com/blog/algorithm-to-make-change-in-python-dynamic-programming The algorithm
    # fits the KCAL_TABLE *exactly*, if it doesn't find an exact match, the result (in currency_composition) will be
    # None
    minimum_number_of_currency = [0]
    currency_composition = [[]]
    kcal_amounts = KCAL_TABLE.keys()

    # The base case (0 calories) is already given, so start iterating from 1
    # Also loop up to and including kcal, since we're dealing with quantities, not indices
    for target_kcal in range(1, kcal + 1):
        best_number_of_currency = 100000000
        best_currency_composition = None

        for kcal_amount in kcal_amounts:
            if (
                target_kcal >= kcal_amount
                and minimum_number_of_currency[target_kcal - kcal_amount] + 1
                < best_number_of_currency
            ):
                best_number_of_currency = (
                    minimum_number_of_currency[target_kcal - kcal_amount] + 1
                )
                best_currency_composition = currency_composition[
                    target_kcal - kcal_amount
                ] + [kcal_amount]

        minimum_number_of_currency.append(best_number_of_currency)
        currency_composition.append(best_currency_composition)

    # Find the highest item in KCAL_TABLE that could be used in the equivalent. A special case is for when kcal is less
    # than the smallest analogy
    highest_kcal_analogy = max(
        (kcal_amount for kcal_amount in kcal_amounts if kcal >= kcal_amount),
        default=None,
    )

    # The best equivalent should be as close to the actual kcal amount, so we do a reverse search/filter, effectively
    # flooring kcal to the best solution. The solution should actually exist, so filter out all the None value.
    # Finally, the goal of this function is to be fun to look at for users. Sometimes it's a better fit to have many
    # tomato's than a (few) liter(s) of mayonnaise, but the mayonnaise is more fun. Therefore, the best solution
    # should also include the highest possible equivalent that's possible for the given kcal
    best = next(
        composition
        for composition in reversed(currency_composition)
        if composition is not None
        and (highest_kcal_analogy is None or highest_kcal_analogy in composition)
    )

    grouped = {}

    for i in best:
        if i in grouped:
            grouped[i] += 1
        else:
            grouped[i] = 1

    return ' & '.join(
        f"{amount} {KCAL_TABLE[product]['multiple' if amount > 1 else 'single'][language]}"
        for product, amount in grouped.items()
    )

from django import template

register = template.Library()


@register.filter()
def unpaid_transactions_of_type(person, transaction_type=None):
    return person.unpaid_transactions(transaction_type=transaction_type)


@register.filter()
def unpaid_transactions_total_cost_of_type(person, transaction_type=None):
    return person.unpaid_transactions_total_cost(transaction_type=transaction_type)

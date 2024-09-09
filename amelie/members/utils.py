# Defines if a member is in the room duty committee.
def is_committee(request, abbreviation):
    return request.person.function_set.filter(committee__abbreviation=abbreviation, end__isnull=True).exists()
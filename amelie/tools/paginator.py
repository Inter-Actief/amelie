from django.core.paginator import Paginator


class RangedPaginator(Paginator):
    def set_page_range(self, current_page, range_offset):
        self.range_offset = range_offset
        self.current_page = current_page

    @property
    def page_range(self):
        # Check for current page to be set
        if not self.current_page:
            raise ValueError("Current page not set")

        # Check for offset
        if not self.range_offset:
            raise ValueError("Range offset not set")

        # Get current page range
        page_range = list(super(RangedPaginator, self).page_range)

        # Calculate index offsets
        index = page_range.index(self.current_page.number)
        left = index - self.range_offset
        right = index + self.range_offset
        last = len(page_range) - 1

        # Correct right part
        if right > last:
            left = left - (right - last)
            right = last

        # Correct left part
        if left <= 0:
            right = right + (0 - left)
            left = 0

        # Done
        return page_range[left:right + 1]

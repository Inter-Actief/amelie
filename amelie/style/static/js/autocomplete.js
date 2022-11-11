function enable_autocomplete() {
    var selector = 'input[type="hidden"] ~ input.autocomplete-input';
    var data = {};

    var reset = function (event, ui) {
        if (ui.item) {
            $.each(data, function (key, val) {
                if (val == ui.item.label) {
                    event.target.previousElementSibling.value = key;
                }
            });
        } else {
            event.target.previousElementSibling.value = '';
        }
    };
    $(selector).autocomplete({
        source: function (request, response) {
            $.ajax({
                url: '/members/ajax/autocomplete/name',
                dataType: "json",
                data: {
                    q: request.term
                },
                success: function (d) {
                    if (Object.keys(d).length > 0) {
                        data = d;
                        response(d);
                    }
                }
            });
        },
        minLength: 3,
        change: reset,
        close: reset,
        focus: reset,
        open: reset,
        response: reset,
        search: reset,
        select: reset
    });
}

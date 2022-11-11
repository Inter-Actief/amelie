/*
* Constructor for a scheduler
*/
function Scheduler() {
    this.default_widget = [];
    this.current_widget = null;
    this.widgets = [];
    this.timed_widgets = [];
    this.ticks = 0;
    this.defaults_before_widget = 14; // amount of default widgets before another one
}

/*
* Schedule at a specific time for a given amount of time
*/
Scheduler.prototype.schedule_at = function (widget, hours, minutes) {
    this.timed_widgets.append({"widget": widget, "hours": hours, "minutes": minutes});
};

/*
* The default widget that is shown when no other schedule was matched
*/
Scheduler.prototype.set_default = function (widget) {
    widget.pre_focus();
    this.default_widget = widget;
};

/*
* Insert a widget every n minutes
*/
Scheduler.prototype.schedule = function (widget) {
    this.widgets.push(widget);
};

/*
* Update a widget
*/
Scheduler.prototype.tick = function () {
    if (this.ticks == (this.defaults_before_widget - 1) * this.default_widget.get_duration() && this.widgets.length > 0) {
        // There is a non-default widget that has to be notified that it will get the foreground in 20 ticks (seconds).
        var found = this.widgets.indexOf(this.current_widget);

        if(found >= 0){
            this.widgets[(found + 1) % this.widgets.length].pre_focus();
        } else {
            this.current_widget = this.widgets[0].pre_focus();
        }
    } else if (this.ticks == this.defaults_before_widget * this.default_widget.get_duration()) {
        // Currently a non-default widget will be displayed, we have to notify the default one that it can now safely updates its steams.
        // Lets switch to the non default one.
        var found = this.widgets.indexOf(this.current_widget);

        if(this.widgets.length > 0) {
            if(found >= 0){
                this.current_widget = this.widgets[(found + 1) % this.widgets.length];
            } else {
                this.current_widget = this.widgets[0];
            }
        }
        this.default_widget.pre_focus();
    }

    if (this.ticks < this.defaults_before_widget * this.default_widget.get_duration()) {
        // The default widget needs a tick
        this.default_widget.tick();

        this.ticks += 1;
    } else if (this.widgets.length == 0) {
        this.default_widget.tick();

        this.ticks = (this.ticks + 1) % (this.defaults_before_widget * this.default_widget.get_duration());
    } else {
        // The non-default widget needs a tick

        // Hack
        if(this.current_widget.get_duration() > 0) {
            this.current_widget.tick();
        } else {
            this.default_widget.tick();
        }

        // We don't know how long the non default widget is, so lets modulo it here.
        this.ticks = (this.ticks + 1) % (this.defaults_before_widget * this.default_widget.get_duration() + this.current_widget.get_duration());
    }
};

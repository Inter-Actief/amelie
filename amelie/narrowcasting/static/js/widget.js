/*
* Constructor for a widget
*/
function Widget() {};

/*
* Function that is called when this widget is put on the screen
*/
Widget.prototype.on_focus = function() {};

/*
* Function that is called when this widget is removed form the screen
*/
Widget.prototype.on_lose_focus = function() {};

/*
* Function that is called a slot before this widget is put on screen
* Use to prefetch certain data from the server.
*/
Widget.prototype.pre_focus = function() {};

/*
* Function that is called every second
*/
Widget.prototype.tick = function () {};

/*
* Duration of this widget
*/
Widget.prototype.get_duration = function () { return 20; };

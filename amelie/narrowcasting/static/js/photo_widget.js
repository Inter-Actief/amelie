function PhotoWidget() {
    Widget.call(this);

    this.currently_showing = null;
    this.activities_with_photos = [];
    this.ticks = 0;

    this.photo_showing = false;
}

PhotoWidget.prototype = new Widget();

PhotoWidget.prototype.constructor = PhotoWidget;

PhotoWidget.prototype.pre_focus = function () {
    var self = this;
    // Get 10 latest activities and pictures
    $.jsonRPC.request('getLatestActivitiesWithPictures', {
        params: [10],
        success: function(result) {
            self.activities_with_photos = result.result;
        },
        error: function(result) {
            console.log("Could not load photos");
        }
    });

    // Get two historic activity and its pictures.
    this.update_historic_pictures();
};

PhotoWidget.prototype.update_historic_pictures = function () {
    var self = this;
    var num_historic = 3;
    var range_start = new Date();
    var range_end = new Date();

    range_end.setMonth(range_end.getMonth()-3);
    range_start.setFullYear(range_start.getFullYear()-2);

    $.jsonRPC.request('getHistoricActivitiesWithPictures', {
        params: [range_start.toISOString(), range_end.toISOString(), num_historic],
        success: function(result) {
            // Add date to each historic activity title
            for(var i = 0; i < result.result.length; i++){
                result.result[i].title = "[Old] " + result.result[i].title + " - "
                    + new Date(Date.parse(result.result[i]['beginDate'])).toLocaleDateString();
            }

            // Equally divide the historic activities across the activities_with_photos list,
            for (var j = 0; j < result.result.length; j++) {
                var splice_distance = Math.round(self.activities_with_photos.length / num_historic);
                self.activities_with_photos.splice((j + 1) * splice_distance, 0, result.result[j]);
            }
        },
        error: function(result) {
            console.log("Could not load photos");
        }
    });
};

PhotoWidget.prototype.get_duration = function () { return 20; };

PhotoWidget.prototype.tick = function () {
    if(this.ticks == 0 || !this.photo_showing) this.change_photo();

    this.ticks = (this.ticks + 1) % this.get_duration();
};

PhotoWidget.prototype.change_photo = function () {
    if (this.activities_with_photos.length > 0){
        var res = this.activities_with_photos.indexOf(this.currently_showing);

        if (res >= 0) {
            this.currently_showing = this.activities_with_photos[(res + 1) % (this.activities_with_photos.length )];
        } else if (this.activities_with_photos.length > 0) {
            this.currently_showing = this.activities_with_photos[0];
        }

        var photo_url = this.currently_showing.images[Math.floor(Math.random() * this.currently_showing.images.length )].large;
        if (photo_url == null) {
            photo_url = this.currently_showing.images[Math.floor(Math.random() * this.currently_showing.images.length )].original;
        }

        var self = this;

        $('<img />').attr({
            src: photo_url,
            id: "photo"
        }).load(function(){
            $(".photo-wrapper #photo").remove();
            $(".photo-wrapper").append($(this));
            $("#photo-activity").html(self.currently_showing.title);
            if($(this).height() > $(this).width()){
                $("#photo").addClass("portrait");
            }

            self.photo_showing = true;
        });
    } else {
        this.photo_showing = false;
    }
};

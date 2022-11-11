var SECOND = 1000;
var MINUTE = 60 * SECOND;

var numActivitiesInitial = 20;
var numActivities = 20;

function initialize() {
    moment.relativeTimeThreshold('s', 60);
    moment.relativeTimeThreshold('ss', -1);

    $.jsonRPC.setup({endPoint: '/api/'});

    moment.locale(getString("locale"));
}

$(document).ready(function(){
    initialize();
    updateAndInterval(setDateTime, SECOND);
    updateAndInterval(setNextEventCountdown, SECOND);
    updateAndInterval(setNextPicture, 10 * SECOND);
    updateAndInterval(updateEvent, 5 * MINUTE);
    updateAndInterval(updatePictures, 10 * MINUTE);
    updateAndInterval(updateRoomDuty, 60 * MINUTE);
    updateAndInterval(updatePCStatus, 20 * SECOND);
    updateAndInterval(updateNowPlaying, 2 * SECOND);
});

function getString(string_id){
    return $("#translation_strings #"+string_id).text();
}

function updateAndInterval(callback, interval){
    callback();
    setInterval(callback, interval);
}

function setDateTime(){
    timeObj = new Date();
    time = timeObj.toTimeString();
    var dateOpts = {
        weekday: "long", year: "numeric", month: "long",
        day: "numeric"
    };
    date = timeObj.toLocaleDateString("en-GB", dateOpts);
    var timeOpts = {
        hour: "2-digit", minute: "2-digit", second: "2-digit"
    };
    time = timeObj.toLocaleTimeString("en-GB", timeOpts);
    $('#date').text(date);
    $('#time').text(time);
}

var nextEvent = null;

function updateEvent() {
    $.jsonRPC.request('getUpcomingActivities', {
        params: [1],
        success: function(result) {
            if (result.result.length > 0) {
                nextEvent = result.result[0];
            } else {
                // No events on website, keep the current one and we'll check again later
            }
        },
        error: function(result) {
            console.error("Could not load activities");
        }
    });
}

var pictures = null;

function updatePictures() {
    $.jsonRPC.request('getLatestActivitiesWithPictures', {
        params: [numActivitiesInitial],
        success: function(result) {
            pictures = result.result;
            numActivities = result.result.length;
        },
        error: function(result) {
            console.error("Could not load pictures");
        }
    });
}

function updateRoomDuty() {
    $.jsonRPC.request('getRoomDutyToday', {
        params: [],
        success: function(result) {
            var roomDuties = result.result;
            $("#room_duty_entries .room_duty_entry").remove();
            if (roomDuties.length > 0){
                for (var i = 0; i < roomDuties.length; i++) {
                    var roomDuty = roomDuties[i];
                    var startTime = moment(roomDuty.beginDate);
                    var endTime = moment(roomDuty.endDate);
                    var participants = "";
                    for (var j = 0; j < roomDuty.participants.length; j++) {
                        if (participants === "") {
                            participants += roomDuty.participants[j].firstName;
                        } else {
                            participants += ", " + roomDuty.participants[j].firstName;
                        }
                    }
                    if (participants === "") {
                        participants = "<i>" + getString('no_room_duty_scheduled') + "</i>";
                    }

                    var elem = $("<div class='room_duty_entry'>" +
                        "<span class='time'>" + startTime.format("HH:mm") + " / " + endTime.format("HH:mm") + "</span>" +
                        "<span class='names'>" + participants + "</span>" +
                        "</div>");
                    $("#room_duty_entries").append(elem);
                }
            } else {
                var e = $("<div class='room_duty_entry'>" +
                    "<span class='time'><i>" + getString('no_room_duty_today') + "</i></span>" +
                    "<span class='names'></span>" +
                    "</div>");
                $("#room_duty_entries").append(e);
            }
        },
        error: function(result) {
            console.error("Could not load room duty");
        }
    });
}

var spotify_was_playing = false;
var spotify_did_pause = false;
var currently_playing_jingle = false;
var spotify_room_device = null;

function pauseIASpotify(){
    $.ajax({url: "./pause_spotify/?id=inter-actief"});
}

function unpauseIASpotify(){
    $.ajax({url: "./play_spotify/?id=inter-actief"});
}

function setNextEventCountdown() {
    var countdown = $("#nextevent_countdown");
    var title = $("#nextevent_title");
    var location = $("#nextevent_location");

    var five_before_four = moment().hour(15).minutes(55).seconds(0);
    var one_past_four = moment().hour(16).minutes(1).seconds(0);

    if (moment().isAfter(five_before_four) && moment().isBefore(one_past_four)){
        var four_o_clock = moment().hour(16).minutes(0).seconds(0);
        var fouroclock_audio = $("#fouroclock_audio");
        var fouroclock_player = $("#nextevent_location audio");

        // If the player is not placed yet, place it
        if(fouroclock_audio.html() !== "") {
            location.html(fouroclock_audio.html());
            fouroclock_audio.html("");
        }

        // Update countdown
        countdown.html(four_o_clock.fromNow() + "<i class=\"fas fa-clock\"></i>");
        title.html(getString("four_o_clock") + "&nbsp;<i class='fa fa-beer'></i>");

        // Start the player once exactly at 15:59:45
        var seconds_before_four = moment().hour(15).minutes(59).seconds(45);
        if (moment().isSame(seconds_before_four, "second") && fouroclock_player.length > 0 && fouroclock_player[0].paused) {
            // If spotify is playing, pause it
            spotify_was_playing = ($("#nowplaying_iaroom .nowplaying_artist").html() !== "");
            if (spotify_was_playing){
                if (spotify_room_device !== null && spotify_room_device.toLowerCase() === "guus") {
                    pauseIASpotify();
                    spotify_did_pause = true;
                }
            }

            // Play the jingle
            fouroclock_player[0].play();
            currently_playing_jingle = true;
        }

        // If we are playing the jingle and it has finished, check if we need to unpause spotify
        if (currently_playing_jingle && spotify_was_playing && fouroclock_player.length > 0 && fouroclock_player[0].ended) {
            if (spotify_did_pause) {
                unpauseIASpotify();
                spotify_did_pause = false;
            }
            currently_playing_jingle = false;
            spotify_was_playing = false;
        }


    }else{
        if (nextEvent !== null) {
            nextEventDate = moment(new Date(nextEvent.beginDate));
            nextEventEndDate = moment(new Date(nextEvent.endDate));

            if (nextEventDate.isAfter(moment())) {
                countdown.html(getString("next_activity_future") + nextEventDate.fromNow() + "<i class=\"fas fa-calendar-alt\"></i>");
            } else if (nextEventDate.isSame(moment(), 'minute')) {
                countdown.html(getString("next_activity_today") + "<i class=\"fas fa-calendar-alt\"></i>");
            } else {
                countdown.html(getString("next_activity_past") + nextEventDate.fromNow() + "<i class=\"fas fa-calendar-alt\"></i>");
            }
            title.html(nextEvent.title);
            location.html(nextEvent.location + "<i class=\"fas fa-map-marker-alt\"></i>");
        } else {
            if (title.html() !== getString("loading_activities")) {
                countdown.html("");
                title.html("<i>" + getString('no_activities') + "</i> <i class=\"fas fa-calendar-alt\"></i>");
                location.html("");
            }
        }
    }

}

function pick(choices) {
    var index = Math.floor(Math.random() * choices.length);
    return {'index': index, 'picture': choices[index]};
}

var currentPictureIndex = -1;

function setNextPicture() {
    if (pictures !== null) {
        currentPictureIndex = (currentPictureIndex + 1) % numActivities;
        var activity = pictures[currentPictureIndex];
        if (activity) {
            var randomPicture = pick(activity.images);
            var activityDate = moment(new Date(activity.beginDate));
            var imageUrl = randomPicture.picture.large;
            if (imageUrl === null || imageUrl.endsWith("/amelie/None") || imageUrl.endsWith("/site_media/None")) {
                imageUrl = randomPicture.picture.original;
            }

            imageUrl = imageUrl.replace("/site_media/data", "https://media.ia.utwente.nl/amelie/data");

            // Preload the image before showing it.
            var img_tag = $('<img alt="" src="' + imageUrl + '" />');
            img_tag.bind('load', function () {
                $("#media_title span").html("[" + activityDate.format("DD-MM-YYYY") + "] " + activity.title);
                $("#media_index_text").html((randomPicture.index + 1) + "/" + activity.images.length);
                $("#media_content").css('background-image', 'url("' + imageUrl + '")');
            });
            if (img_tag[0].width) {
                img_tag.trigger('load')
            }
        }
    }
}

function updatePCStatus() {
    $.ajax({
        url: "./pc_status"
    }).done(function(data){
        for (var key in data) {
            $(".pc_square[data-host="+key+"]").attr('data-state', data[key]);
        }
    });
}

var nowPlayingExclude = [];

function updateNowPlaying() {
    $(".nowplaying_location").each(function(){
        var dom_object = $(this);
        var identifier = $(this).data('user');

        if ($.inArray(identifier, nowPlayingExclude) === -1) {
            $.ajax({
                url: "./spotify/?id=" + identifier,
                error: function (result) {
                    console.log(result);
                    if (result.status === 404) {
                        nowPlayingExclude.push(identifier);
                        dom_object.find(".nowplaying_title").html("<a href='?setup_spotify=" + identifier + "'>" + getString('not_associated') + "</a>");
                    } else {
                        // Update playing device
                        if (identifier === "inter-actief") {
                            spotify_room_device = null;
                        }
                        dom_object.find(".albumimage").attr("style", "display: none;");
                        dom_object.find(".albumimage").attr("src", "");
                        dom_object.find(".nowplaying_title").html(getString("spotify_error"));
                        dom_object.find(".nowplaying_artist").html("");
                        dom_object.find(".nowplaying_device").html("");
                        dom_object.find(".nowplaying_track").addClass("nowplaying_nothing");
                        dom_object.find(".nowplaying_album").addClass("not_playing");
                    }
                }
            }).done(function (data) {
                if (data['error'] === false && data['is_playing'] === true) {
                    // Update playing device
                    if (identifier === "inter-actief") {
                        spotify_room_device = data["device"]["name"];
                    }

                    var artists = [];
                    for (var key in data.item.artists) {
                        artist = data.item.artists[key];
                        artists.push(artist.name);
                    }
                    if (artists.length === 0) {
                        artists = [getString("unknown_artist")];
                    }

                    var progress = (data.progress_ms / data.item.duration_ms) * 100;

                    // Preload the image before showing it.
                    var img_tag = $('<img alt="" src="' + data.item.album.images[0].url + '" />');
                    img_tag.bind('load', function () {
                        dom_object.find(".albumimage").attr("style", "");
                        dom_object.find(".nowplaying_album").removeClass("not_playing");
                        dom_object.find(".nowplaying_track").removeClass("nowplaying_nothing");
                        dom_object.find(".albumimage").attr('src', data.item.album.images[0].url);
                        dom_object.find(".nowplaying_title").html(data.item.name);
                        dom_object.find(".nowplaying_artist").html(artists.join(", "));
                        dom_object.find(".nowplaying_device").html(data.device.name);
                        var progressDiv = dom_object.find(".nowplaying_progress");
                        var progress_per_five_sec = (5000 / data.item.duration_ms) * 100;
                        var curProgress = parseFloat(progressDiv[0].style.width.replace("%", "")) - progress_per_five_sec - 0.1;
                        var transitionProgress = 0;
                        if (!isNaN(curProgress)) {
                            if (progress < curProgress) {
                                progressDiv.removeClass("transition");
                            } else if (!progressDiv.hasClass('transition')) {
                                progressDiv.addClass('transition');
                                transitionProgress = Math.min(progress + progress_per_five_sec, 100);
                            } else {
                                transitionProgress = Math.min(progress + progress_per_five_sec, 100);
                            }
                        }
                        progressDiv.attr('style', "width: "+transitionProgress+'%;');
                    });
                    if (img_tag[0].width) {
                        img_tag.trigger('load')
                    }
                } else if (data['error'] === false) {
                    // Update playing device
                    if (identifier === "inter-actief") {
                        spotify_room_device = null;
                    }
                    dom_object.find(".albumimage").attr("style", "display: none;");
                    dom_object.find(".albumimage").attr("src", "");
                    dom_object.find(".nowplaying_title").html(getString("not_playing"));
                    dom_object.find(".nowplaying_artist").html("");
                    dom_object.find(".nowplaying_device").html("");
                    dom_object.find(".nowplaying_track").addClass("nowplaying_nothing");
                    dom_object.find(".nowplaying_album").addClass("not_playing");
                } else {
                    // Update playing device
                    if (identifier === "inter-actief") {
                        spotify_room_device = null;
                    }
                    dom_object.find(".albumimage").attr("style", "display: none;");
                    dom_object.find(".albumimage").attr("src", "");
                    dom_object.find(".nowplaying_title").html(getString("spotify_error"));
                    dom_object.find(".nowplaying_artist").html("");
                    dom_object.find(".nowplaying_device").html("");
                    dom_object.find(".nowplaying_track").addClass("nowplaying_nothing");
                    dom_object.find(".nowplaying_album").addClass("not_playing");
                }
            });
        }
    });
}
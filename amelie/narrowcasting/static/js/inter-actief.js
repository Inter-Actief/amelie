var SECOND = 1000;
var MINUTE = 60 * SECOND;
var HOUR = 60 * MINUTE;
var tick = 0;

var banners = [];
var current_banner = null;

var past_activities = [];
var past_activity_currently_showing = null;

var imageScheduler = null;

/*
* view this as a cron like system
*/
$(function() {
    init();
    initIntervals();
});

var init = function () {
    $.jsonRPC.setup({
        endPoint: '/api/',
    });

    imageScheduler = new Scheduler();
    imageScheduler.set_default(new PhotoWidget());

    imageScheduler.schedule(new PromotionWidget());
};

var initIntervals = function () {
    setTimeout(function () {updateAndInterval(function () {updateBanner(); }, 20*SECOND)}, 10*SECOND);
    updateAndInterval(function () { update(); }, SECOND);
    updateAndInterval(function () { updateBannersList(); }, 5*MINUTE);
    updateAndInterval(function () { updateActivityList(); }, 5*MINUTE);
    updateAndInterval(function () { updateNewsList(); }, 5*MINUTE);
    updateAndInterval(function () { updateClock(); }, SECOND);
};

var updateAndInterval = function ( callback, interval ) {
    callback();
    setInterval(callback, interval);
};

var updateClock = function () {
    timeObj = new Date();
    time = timeObj.toTimeString();
    var dateOpts = {
        weekday: "long", year: "numeric", month: "long",
        day: "numeric"
    };
    date = timeObj.toLocaleDateString("en-US", dateOpts);
    var timeOpts = {
        hour: "2-digit", minute: "2-digit", second: "2-digit"
    };
    time = timeObj.toLocaleTimeString("en-US", timeOpts);
    $('.date').text(date);
    $('.time').text(time);
};

var updateBannersList = function () {
    $.jsonRPC.request('getBanners', {
        params: [],
        success: function(result) {
            banners = result.result;
        },
        error: function(result) {
            console.log("Could not load banners");
        }
    });
};

var update = function () {
    imageScheduler.tick();
};

var updateActivityList = function () {
     $.jsonRPC.request('getUpcomingActivities', {
        params: [4],
        success: function(result) {
            $("#activity-table tr").remove();
            for(var i = 0; i < result.result.length; i++) {
                var item = result.result[i];
                var options = {
                    weekday: "short", month: "short",
                    day: "numeric", hour: "2-digit", minute: "2-digit"
                };
                var date = new Date(item["beginDate"]).toLocaleString("en-US", options);
                $("#activity-table").append("<tr><td class=\"activity-icon\"><span class=\"glyphicon glyphicon-calendar\"></span></td><td class=\"activity-datetime\">"+date+"</td><td class=\"activity-title\">"+item.title+"</td></tr>")
            }
        },
        error: function(result) {
            console.log("Could not load activities");
        }
    });
};

var updateBanner = function () {
    if (banners.length > 0) {
        var res = banners.indexOf(current_banner);
        if (res >= 0) {
            current_banner = banners[(res + 1) % (banners.length )];
        } else if (banners.length > 0) {
            current_banner = banners[0];
        }
        $("#adImg").attr("src",current_banner.image);

        var banner_url = current_banner.image;

        $('<img />').attr({
		    src: banner_url,
            id: "adImg"
        }).load(function(){
            $(".ads #adImg").remove();
            $(".ads").append($(this));
            if($(this).height() > $(this).width()){
                $("#adImg").addClass("portrait");
            }
        });
    }
};

var updateNewsList = function () {
    $.jsonRPC.request('getNews', {
        params: [2, true],
        success: function(result) {
            $(".news-item").remove();
            news = result.result;

            for(var i = 0; i < result.result.length; i++) {
                var item = result.result[i];
                var options = {
                    weekday: "short", month: "short",
                    day: "numeric", hour: "2-digit", minute: "2-digit"
                };
                var date = new Date(item["publicationDate"]).toLocaleString("en-US", options);
                $(".footer").append("<div class=\"news-item\"><div class=\"news-header\"><span class=\"glyphicon glyphicon-globe\"></span><span>"+date+"</span>"+item.title+"</div><div class=\"news-content\">"+item.introduction+"</div></div>")
            }
        },
        error: function(result) {
            console.log("Could not load photos");
        }
    });

};

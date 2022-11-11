function createBrandBox(container) {
    //classes + id's
    var sliderBox = $('#slider-items');
    var sliderItems = sliderBox.children();
    var activityList = $('#slider-list');
    var oldImagesQuery = '#slider-items img';

    //settings
    var fadeTime = 1000;
    var interval = 10000;
    var randomUrl = 'random/';

    //initialize
    var intervalId;
    var currentImage;
    var last_click = new Date().getTime();

    sliderItems.each(
        function (index) {
            var href = this.href;
            $('<li/>', {
                class: 'slider-item',
                title: href
            }).html(this.title).bind('click', function () {
                // check if user is not clicking too much
                if (last_click < new Date().getTime() - fadeTime) {
                    last_click = new Date().getTime();
                    $(oldImagesQuery).stop();
                    fadeToSlide(index);
                    clearInterval(intervalId);
                    intervalId = setInterval(function () {
                        fadeToSlide()
                    }, interval);
                }
            }).bind('dblclick', function () {
                window.location.href = href
            }).appendTo(activityList);
            if (index == 0) {
                loadNewImage($(this), function (e) {
                    activityList.children().first().addClass('active');
                    currentImage = $(e.target);
                    currentImage.fadeIn(fadeTime, function (e) {
                        cycleBrandBox();
                    });
                    slideImage(currentImage, true);
                });
            }
        }
    );

    //functions
    function cycleBrandBox() {
        intervalId = setInterval(function () {
            fadeToSlide();
        }, interval - fadeTime);
    }

    function fadeToSlide(index) {
        var parent = currentImage.parent();
        if (index != null) {
            var next_parent = parent.siblings().addBack().eq(index);
        } else {
            next_parent = parent.next();
            if (next_parent.length == 0) {
                next_parent = parent.siblings().addBack().first();
            }
        }

        // Switch to active
        $(activityList).children().removeClass('active');
        $(activityList).children().eq(next_parent.index()).addClass('active');

        // Load new image
        loadNewImage(next_parent, function (e) {
            var oldImages = $(oldImagesQuery).not(currentImage);
            oldImages.stop();
            oldImages.fadeOut(fadeTime);
            currentImage.fadeIn(fadeTime, function (e) {
                oldImages.remove();
            });
            slideImage(currentImage, true);
        });
    }

    function slideImage(image, first) {
        //animate new image if possible
        var duration = first ? interval : interval - fadeTime;

        var heightBox = sliderBox.height();
        var heightImg = image.height();
        var heightDiff = heightImg - heightBox;

        if (heightDiff > 0) {
            image.animate({
                bottom: -heightDiff
            }, duration, 'swing');
        }
    }

    function loadNewImage(parent, onload) {
        $.getJSON(parent.attr('href') + randomUrl, function (data) {
            currentImage = $('<img />').attr({
                src: data.url,
                alt: parent.attr('title')
            });
            currentImage.css('display', 'none').load(onload).appendTo(parent);
        });
    }
}

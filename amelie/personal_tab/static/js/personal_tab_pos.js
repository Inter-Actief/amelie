var activityInterval = 20 * 1000; // 20 seconds
var pictureInterval = 10 * 1000; // 10 seconds
var pictureFadeTime = 2 * 1000; // 2 seconds
var loginTimeout = 3 * 60 * 1000; // 3 minutes
var loginCheckInterval = 2 * 1000; // 2 seconds
var indexReloadTimeout = 60 * 60 * 1000; // 1 hour
var shopTimeout = 3 * 60 * 1000; // 3 minutes
var successTimeout = 5 * 1000; // 5 seconds
var successFreeWinTimeout = 16 * 1000; // 16 seconds

$('img').bind('dragstart', function(event) {
    'use strict';
    event.preventDefault();
});

$('a').mousedown(function(e) {
    e.preventDefault();
});

function rfid_to_identifier(rfid) {
    var ia_rfid_prefix = false;

    if (rfid.hasOwnProperty("atqa") && rfid.hasOwnProperty("sak") && rfid.hasOwnProperty("uid")) {
        if (rfid['atqa'] === "00:04" && rfid['sak'] === "08") {
            ia_rfid_prefix = '02'; // MIFARE Classic 1k
        } else if (rfid['atqa'] === "00:02" && rfid['sak'] === "18") {
            ia_rfid_prefix = '03' // MIFARE Classic 4k
        } else if (rfid['atqa'] === "03:44" && rfid['sak'] === "20") {
            ia_rfid_prefix = '04' // MIFARE DESFire
        } else if (rfid['atqa'] === "00:44" && rfid['sak'] === "00") {
            ia_rfid_prefix = '05' // MIFARE Ultralight
        }
    }

    return ia_rfid_prefix ? ia_rfid_prefix + "," + rfid['uid'] : false;
}

function getCurrentActivity(){
    'use strict';
    return parseInt($('.activities-picker-button.active').data('index'), 10);
}

function setActivity(new_index){
    'use strict';
    var activeButton = $('.activities-picker-button.active');
    var activeIndex = parseInt(activeButton.data('index'), 10);
    var activeContent = $('.activities-content-pane[data-index="'+activeIndex+'"]');
    var activeIcon = $('.activities-picker-button[data-index="'+activeIndex+'"] i');
    var newButton = $('.activities-picker-button[data-index="'+new_index+'"]');
    var newContent = $('.activities-content-pane[data-index="'+new_index+'"]');
    var newIcon = $('.activities-picker-button[data-index="'+new_index+'"] i');
    activeButton.removeClass('active');
    activeContent.removeClass('active');
    activeIcon.removeClass('fa-dot-circle');
    activeIcon.addClass('fa-circle');
    newButton.addClass('active');
    newContent.addClass('active');
    newIcon.removeClass('fa-circle');
    newIcon.addClass('fa-dot-circle');
}

function animateActivityProgressBar(interval){
    'use strict';
    var container = $("#activities-timer");
    var bar = $('#activities-progressbar');
    bar.stop();
    bar.css('width', '0');
    bar.animate({
        width: container.width()
    }, interval, "linear");
}

function nextActivity(){
    'use strict';
    var newIndex = getCurrentActivity() + 1;
    if (newIndex >= numActivities) {
        newIndex = 0;
    }
    setActivity(newIndex);
    animateActivityProgressBar(activityInterval);
}

function slidePicture(index){
    'use strict';
    var image = $('.past-activities-image[data-index="'+index+'"] img');
    var heightBox = $('#past-activities-content').height();
    var heightImage = image.height();
    var heightDiff = heightImage - heightBox;
    if (heightDiff > 0) {
        image.animate({
            top: -heightDiff
        }, pictureInterval - pictureFadeTime);
    }
}

function resetPictureSlider(index) {
    'use strict';
    var img = $('.past-activities-image[data-index="'+index+'"] img');
    img.stop();
    img.css('top', '0');
}

function nextPicture(){
    'use strict';
    var activeTitle = $('.past-activities-title.active');
    var activeIndex = parseInt(activeTitle.data('index'), 10);
    var activePicture = $('.past-activities-image[data-index="'+activeIndex+'"]');
    var newIndex = activeIndex + 1;
    if (newIndex >= numPictures) {
        newIndex = 0;
    }
    var newTitle = $('.past-activities-title[data-index="'+newIndex+'"]');
    var newPicture = $('.past-activities-image[data-index="'+newIndex+'"]');
    activeTitle.removeClass('active');
    activePicture.removeClass('active');
    newTitle.addClass('active');
    newPicture.addClass('active');
    resetPictureSlider(newIndex);
    slidePicture(newIndex);
}

var activitySliderInterval = -1;

function selectEventAndResetTimer(index){
    'use strict';
    clearInterval(activitySliderInterval);
    setActivity(index)
    activitySliderInterval = setInterval(nextActivity, activityInterval);
    animateActivityProgressBar(activityInterval);
}

function logout_preset(msg_preset){
    'use strict';
    if(msg_preset !== null) {
        window.location = logoutURL + "?msg_preset=" + msg_preset;
    }else{
        window.location = logoutURL
    }
}

function logout_timeout(){
    'use strict';
    logout_preset('timeout');
}

function logout_cancelled(){
    'use strict';
    logout_preset('cancelled');
}

function logout(){
    'use strict';
    logout_preset(null);
}

function setupPosHome(){
    'use strict';
    if (numActivities > 1) {
        $("#activities-picker-previous").click(function(){
            var newEvent = getCurrentActivity() - 1;
            if (newEvent < 0) {
                newEvent = numActivities - 1;
            }
            selectEventAndResetTimer(newEvent)
        });
        $("#activities-picker-next").click(function(){
            var newEvent = getCurrentActivity() + 1;
            if (newEvent >= numActivities) {
                newEvent = 0;
            }
            selectEventAndResetTimer(newEvent)
        });
        $(".activities-picker-button").click(function(event){
            selectEventAndResetTimer(parseInt($(event.currentTarget).data('index'), 10));
        });
        activitySliderInterval = setInterval(nextActivity, activityInterval);
        // Activate initial progress bar
        animateActivityProgressBar(activityInterval);
    }

    if (numPictures > 0) {
        setInterval(nextPicture, pictureInterval);
        // Slide initial picture
        slidePicture(0);
    }

    /* RFID initialization */
    var socket = new WebSocket('ws://localhost:3000');
    socket.onmessage = function (event) {
        var rfid = JSON.parse(event.data);
        var tag = rfid_to_identifier(rfid);
        console.log("Tag scanned!");
        if (tag) {
            $('#rfid-form-tags').attr('value', '["' + tag + '"]');
            $('#rfid-form').submit();
        }
    };

    /* Reload page after some time to refresh images and activities */
    setTimeout(function () {
        location.reload();
    }, indexReloadTimeout);
}

function checkLoginStatus(){
    'use strict';
    // Refresh the export status, update the page, then schedule another refresh if the export is not finished.
    if (tokenCheckURL !== null) {
        $.ajax(tokenCheckURL, {
            cache: false,
            success: function (data) {
                console.log(data);

                // If the error flag is set, redirect to logout with the message parameter set, to
                // show the message to the user.
                if (data.error) {
                    console.log("Error flag set! Redirecting to logout. Message: " + data.message);
                    window.location = logoutURL + "?msg=" + data.message + "&msg_type=ERROR";
                }

                // If the export is not done, refresh again after another interval.
                if (!data.status) {
                    setTimeout(checkLoginStatus, loginCheckInterval);
                } else {
                    console.log("Login success. Refreshing page.");
                    location.reload(true);
                }
            },
            error: function (xhr, ajaxOptions, thrownError) {
                console.error("Error " + xhr.status + " while getting status update.");
                console.log("Redirecting back to main screen.");
                logout();
            }
        });
    } else {
        console.error("Error while getting status update, no check URL defined.");
    }
}

var shoppingCart = {};

function resetCart(){
    'use strict';
    shoppingCart = {};
}

function deactivateInstaBuy() {
    'use strict';
    $('.article-instabuy').hide();
}

function activateInstaBuy() {
    'use strict';
    $('.article-instabuy').show();
}

function deactivateAcceptButton() {
    'use strict';
    $('#button-accept').hide();
}

function activateAcceptButton() {
    'use strict';
    $('#button-accept').show();
}

function deactivateCart() {
    'use strict';
    $('#shopping-cart').hide();
    $('#top-five').show()
}

function activateCart() {
    'use strict';
    $('#shopping-cart').show();
    $('#top-five').hide()
}

function updateCart() {
    'use strict';
    var cart_entries = $('#cart-entries');
    cart_entries.html("");
    var cart_total = 0.0;
    var euroFormat = new Intl.NumberFormat('nl-NL', {style: 'currency', currency: 'EUR', minimumFractionDigits: 2});

    var current_num_items = 0;
    var num_items = 0;
    for (var i in shoppingCart){num_items += 1;}

    if (num_items > 0) {
        deactivateInstaBuy();
        activateCart();
        activateAcceptButton();
    } else {
        activateInstaBuy();
        deactivateCart();
        deactivateAcceptButton();
    }

    for (var entry in shoppingCart) {
        if (current_num_items === 7 && num_items > 8) {
            // Add an element that says that there are more items that are not visible. "And more"
            var num_items_more = num_items - 7;
            var full_html = $('#cart-full-template').clone();
            full_html.removeAttr('id');
            full_html.addClass('cart-full-entry');
            full_html.html(full_html.html().replace("{amount}", num_items_more));
            cart_entries.append(full_html);
        }

        var entry_html = $('#cart-entry-template').clone();
        entry_html.attr('data-id', entry);
        entry_html.attr('data-amount', shoppingCart[entry].amount);
        entry_html.attr('data-price-per-unit', shoppingCart[entry].price_per_unit);
        entry_html.attr('data-price-total', shoppingCart[entry].price_total);
        entry_html.attr('data-image-url', shoppingCart[entry].image_url);

        entry_html.find(".image").css('background-image', "url('" + shoppingCart[entry].image_url + "')");
        entry_html.find(".image-amount").html(shoppingCart[entry].amount + "x");
        entry_html.find(".name").html(shoppingCart[entry].name);
        entry_html.find(".amount").html(shoppingCart[entry].amount + "x " + euroFormat.format(shoppingCart[entry].price_per_unit));
        entry_html.find(".total").html(euroFormat.format(shoppingCart[entry].price_total));

        entry_html.find('.remove').click(removeCartEntry);

        cart_total += shoppingCart[entry].price_total;

        entry_html.removeAttr('id');
        entry_html.addClass('cart-entry');

        cart_entries.append(entry_html);
        current_num_items += 1;
    }
    $('#totals-amount').html(euroFormat.format(cart_total));
}

function addToCartInstant(id, name, amount, price_per_unit, image_url){
    if (shoppingCart[id] === undefined) {
        // Add new item
        shoppingCart[id] = {
            'name': name,
            'amount': amount,
            'price_per_unit': price_per_unit,
            'price_total': amount * price_per_unit,
            'image_url': image_url
        }
    } else {
        // Update amount and total price
        shoppingCart[id].amount += amount;
        shoppingCart[id].price_total = shoppingCart[id].amount * shoppingCart[id].price_per_unit;
    }
}

function addToCart(id, name, amount, price_per_unit, image_url){
    'use strict';
    addToCartInstant(id, name, amount, price_per_unit, image_url);
    updateCart();
}

function removeCartEntry(event){
    'use strict';
    var entry = $(event.currentTarget.parentElement);
    var article_id = entry.data('id');
    delete shoppingCart[article_id];
    updateCart();
}

function submitCart() {
    'use strict';
    var num_items = 0;
    for (var i in shoppingCart){num_items += 1;}

    if(num_items > 0){
        var cart = [];
        for(var article_id in shoppingCart){
            var amount = shoppingCart[article_id].amount;
            cart.push('{"product": ' + article_id + ', "amount": ' + amount + '}');
        }
        cart = '[' + cart + ']';

        $('#checkout-form-cart').attr('value', cart);
        $('#checkout-form').submit();
    }
}

function showCategory(id) {
    'use strict';
    /* Hide the category buttons */
    $('.shop-category-button').hide();
    /* Set the current category title */
    $('#shop-category-name').html($('.shop-category-button[data-id='+id+'] .category-title').html());
    /* Show the back button */
    $('#shop-back').show();
    /* Show the category contents */
    var shop_category = $('.shop-category[data-id='+id+']');
    shop_category.addClass('active');
}

function goBack() {
    'use strict';
    /* Hide the current category */
    var shop_category = $('.shop-category.active');
    shop_category.removeClass('active');
    /* Hide the back button */
    $('#shop-back').hide();
    /* Unset the current category title */
    $('#shop-category-name').html("&nbsp;");
    /* show the category buttons */
    $('.shop-category-button').show();
}

function setupCalculator(calculator) {
    'use strict';
    var calculator_obj = $(calculator);
    var productId = calculator_obj.data('id');
    var productName = calculator_obj.data('name');
    var productPrice = calculator_obj.data('price');
    var productImage = calculator_obj.data('image');
    var inputfield = $(calculator_obj.find(".input-amount input"));

    calculator_obj.find(".calculator-buttons a").click(function(){
        // Setup button click handlers
        var value = $(this).data('val');
        switch (value) {
            case "back":
                var oldValue = inputfield.attr('value');
                inputfield.attr('value', oldValue.substring(0, oldValue.length - 1));
                break;
            case "add":
                var inputValue = parseInt(inputfield.attr('value'), 10);
                if(!isNaN(inputValue) && inputValue > 0){
                    // Add to cart
                    addToCart(productId, productName, parseInt(inputfield.attr('value'), 10), parseFloat(productPrice), productImage);
                    // Clear the input field
                    inputfield.attr('value', '');
                    // Return to main tab
                    goBack();
                } else {
                    inputfield.attr('value', '');
                }
                break;
            default:
                // Only add if there are less than 3 numbers in the input field
                if(inputfield.attr('value').length < 3){
				    inputfield.attr('value', inputfield.attr('value') + value);
                }
                break;
        }
    })

}

function setupLoginPage(){
    'use strict';
    setTimeout(logout_timeout, loginTimeout);
    setTimeout(checkLoginStatus, loginCheckInterval);
}

function setupShopPage(){
    'use strict';
    setTimeout(logout_timeout, shopTimeout);
    resetCart();
    $('.shop-category-button').click(function(event){
        showCategory($(event.currentTarget).data('id'));
    });
    $('#shop-back-button').click(function(){
        goBack();
    });
    $('.article-instabuy').click(function(event){
        resetCart();
        var article_elem = $(event.currentTarget.parentElement);
        var article_id = article_elem.data('id');
        var article_price = parseFloat(productPrice);
        var article_name = article_elem.data('name');
        var article_image = article_elem.data('image');
        addToCartInstant(article_id, article_name, 1, article_price, article_image);
        submitCart();
    });
    $('.top-five-instabuy').click(function(event){
        resetCart();
        var article_elem = $(event.currentTarget.parentElement);
        var article_id = article_elem.data('id');
        var article_price = parseFloat(productPrice)
        var article_name = article_elem.data('name');
        var article_image = article_elem.data('image');
        addToCartInstant(article_id, article_name, 1, article_price, article_image);
        submitCart();
    });
    $('.article-addtocart').click(function(event){
        var article_elem = $(event.currentTarget.parentElement);
        var article_id = article_elem.data('id');
        var article_price = parseFloat(productPrice);
        var article_name = article_elem.data('name');
        var article_image = article_elem.data('image');
        addToCart(article_id, article_name, 1, article_price, article_image);
    });
    $('#button-accept').click(function(){
        submitCart();
    });
    $('#button-cancel').click(function(){
        logout_cancelled();
    });
    $('.calculator').each(function() {
        setupCalculator(this);
    })
}

function setupPosExternalScan(){
    'use strict';
    /* RFID initialization */
    var socket = new WebSocket('ws://localhost:3000');
    socket.onmessage = function (event) {
        var rfid = JSON.parse(event.data);
        var tag = rfid_to_identifier(rfid);
        console.log("Tag scanned!");
        if (tag) {
            $('#rfid-form-tags').attr('value', '["' + tag + '"]');
            $('#rfid-form').submit();
        }
    };
}

function updateSuccessTimer() {
    'use strict';
    var curTimer = parseInt($('#success-timer').html());
    if (curTimer > 0 ) {
        $('#success-timer').html(curTimer - 1);
        setTimeout(updateSuccessTimer, 1000);
    }
}

function setupPosSuccess(){
    'use strict';
    var delay = successTimeout;
    if($(document.body).hasClass('free-cookie-winner')){
        document.getElementById('promotion-audio').play();
        $('#promotion').css('display', 'block');
        delay = successFreeWinTimeout;
        setTimeout(function(){
            $('#promotion').css('display', 'none');
        }, 11000);
    }

    if(delay === successTimeout) {
        setTimeout(updateSuccessTimer, 1000);
    } else {
        setTimeout(successTimeout, delay - successTimeout + 1000);
    }

    setTimeout(logout, delay);
    $('a').mousedown(function(e) {
        e.preventDefault();
    });
    $('img').bind('dragstart', function(event) { event.preventDefault(); });

}

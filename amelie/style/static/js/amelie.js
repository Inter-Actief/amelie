var TemplateUtil = (function() {

	function TemplateUtil(textarea, counter, previewer, max_count, replacers) {
		var __t = this;
		this.textarea = textarea;
		this.counter = counter;
		this.previewer = previewer;
		this.max_count = isNaN(parseInt(max_count)) ? Infinity : parseInt(max_count);
		this.replacers = (typeof replacers === "object") ? replacers : {};

		if (this.max_count == Infinity) {
			this.counter.hide();
		} else {
			this.updateCount();
		}

		textarea.bind("keypress keydown keyup paste", function() {
			__t.updateCount();
			__t.updatePreview();
		});

		$(".template-tags > input").click(function() {
			textarea.filter(':visible').insertAtCaret($(this).val());
			__t.updateCount();
			__t.updatePreview();
		});

		// Initial update
		__t.updateCount();
		__t.updatePreview();
	}

	TemplateUtil.prototype.updateCount = function() {
		var count = this.textarea.val().length;
		this.counter.html(this.max_count + "/" + count);
		(count > this.max_count) ? this.counter.addClass('invalid') : this.counter.removeClass('invalid');
	};

	TemplateUtil.prototype.updatePreview = function() {
		var text = this.textarea.val();
		var matches = text.match(/\{\{[a-z._]+\}\}/g);
		for (i in matches) {
			var tag = matches[i].substring(2, matches[i].length - 2);
			if (match = this.replacers[tag]) {
				text = text.replace(matches[i], match);
			}
		}

		// Escape the input
		// http://stackoverflow.com/a/374176
		text = $('<div/>').text(text).html();

		text = text.replace(/\n/g, '<br />');
		this.previewer.html(text);
	}
	return TemplateUtil;

})();

jQuery.fn.extend({
	insertAtCaret : function(myValue) {
		return this.each(function(i) {
			if(document.selection) {
				//For browsers like Internet Explorer
				this.focus();
				sel = document.selection.createRange();
				sel.text = myValue;
				this.focus();
			} else if(this.selectionStart || this.selectionStart == '0') {
				//For browsers like Firefox and Webkit based
				var startPos = this.selectionStart;
				var endPos = this.selectionEnd;
				var scrollTop = this.scrollTop;
				this.value = this.value.substring(0, startPos) + myValue + this.value.substring(endPos, this.value.length);
				this.focus();
				this.selectionStart = startPos + myValue.length;
				this.selectionEnd = startPos + myValue.length;
				this.scrollTop = scrollTop;
			} else {
				this.value += myValue;
				this.focus();
			}
		})
	}
});

var followLink = function(elem) {
	if(elem.length > 0) {
		window.location.href = elem.attr('href');
	}
}

$(document).ready(function() {
	/**
	 *  Date/timepicker
	 */
	$('.date_selector').datepicker({format: 'yyyy-mm-dd','weekStart': 1});
	$('.time_selector').timepicker({'template': 'dropdown', 'showMeridian': false, 'defaultTime': false});

	/**
	 *  ChosenJS Select boxes / Dropdowns
	 */
	$('.chosen-select').chosen();

	/**
	 * Open or close login popup in the menu bar by clicking on it.
	 */
	$("#nav > li#nav_login > a").click(function(e) {
		e.preventDefault();
		$(this).parent().toggleClass("active").toggleClass("hover");
	});

	/**
	 * Give open/closable elements the right classes
	 */
	$(".expand").each(function() {
		var expand = $(this);

		if ($(this).data("target") == undefined) { return false; }

		var container = "#" + $(this).data("target");
		$(container).not(":visible").each(function() { expand.removeClass("expanded").addClass("collapsed"); });
		$(container).not(":hidden").each(function() { expand.addClass("expanded").removeClass("collapsed"); });

		expand.append('<span>&nbsp;</span>');
	});

	/**
	 * Can show or hide a hidden element
	 */
	$(".expand").click(function(e) {
		var expand = $(this);
		e.preventDefault();

		// Check for target
		if ($(this).data("target") == undefined) {
			console.log("No target to expand!");
			return false;
		}

		var container = "#" + $(this).data("target");
		$(container).slideToggle(500, function() {
			// Animation complete, set the right classes
			$(this).not(":visible").each(function() { expand.removeClass("expanded").addClass("collapsed"); });
			$(this).not(":hidden").each(function() { expand.addClass("expanded").removeClass("collapsed"); });
			// Stop animation when clicked more than once
			$(this).stop(true);
		});
	});
	/**
	 * Utility functions such as a 'number of characters' counter and template preview
	 */
	$(".util").each(function() {
		new TemplateUtil($(this).find(".characters"), $(this).find(".counter"), $(this).find(".previewer"), $(this).data('max-chars'), $(this).data('tags'));
	});
	/**
	 * Hotkeys for navigating through pictures
	 */
	$(document).keydown(function(e) {
		switch(e.keyCode) {
			case 37:
				followLink($('#previous_photo'));
				break;
			case 39:
				followLink($('#next_photo'));
				break;
		}
	});

	window.timer = false;

	/**
	 * Prevent the menu from closing too quickly after the mouse has left the menu.
	 */
	$("#nav ul").not('#nav > #nav_login ul').mouseleave(function(e) {
		var self = $(this);

		var timer = setTimeout(function() {

			self.removeClass("hover");
			self.parent().removeClass("hover");
		}, 500);

		self.addClass("hover");
		self.parent().addClass("hover");

		self.parent().parent().bind("mousemove", function() {
			self.removeClass("hover");
			self.parent().removeClass("hover");
			clearTimeout(timer);
			$(this).unbind("mousemove");
		});
	});

	/**
	 * Follow a link to an anchor in the page with a scroll animation
	 */
	function refreshScrollTo(elem){
		$(elem).click(function(e) {
			e.preventDefault();

			var element = $(this);
			var name = element.prop('href').split("#")[1];

			if (name.length > 0) {
				var offset = $("a[name='" + name + "']").offset().top;
				var padding = parseInt(element.data("scroll-to-padding")) || 20;

				$('html, body').stop().animate({scrollTop: offset - padding*2+1});//dirty fix with padding*2 �?
			}
		});
	}

	// Execute on all elements
	refreshScrollTo('.scroll-to');

	/**
	 * Lets a block scroll along with the page.
	 */
	$(".follow-scroll").each(function(e) {
		var element = $(this);
		var offsetTop = element.offset().top;
		var marginTop = element.outerHeight() - element.height();

		var elemClone = element.clone().addClass('follow-scroll-clone');

		$(window).scroll(function() {
			var header = $('#top');
			var headerMargin = offsetTop - header.height() - marginTop;
			var isVisible = elementIsVisible(header);

			if(!isVisible){
				element.parent().parent().find('#screenfollow').append(elemClone);
				element.addClass('follow-invisible');
				/*elemClone.css({position:"relative", top:headerMargin});*/

			} else {
				element.removeClass('follow-invisible');
				element.parent().parent().find('#screenfollow').find('.follow-scroll-clone').remove();
			}

			//refresh scrollto because it changed
			refreshScrollTo('.scroll-to');
		});

		function elementIsVisible(elem){
			var scrollTop = $(window).scrollTop();
			var elemTop = $(elem).offset().top;
			var elemBottom = elemTop + $(elem).height();
			return (scrollTop <= elemBottom);
		}
	});

	/**
	 * Make a link load HTML via AJAX to a specified container. The container
	 * should be specified in data-container and the URL should be in the href.
	 */
	$("body").on("click", ".js-load-block", function(e) {
		e.preventDefault();
		var container = $("#" + $(this).data("container"))

		// Load via AJAX
		$.ajax($(this).attr("href"), {
			'cache': false,
			'success': function(data, textStatus, jqXHR) {
				container.html(data);
			},
			'error': function(jqXHR, textStatus, errorThrown) {
				alert("Could not load block via AJAX: " + errorThrown);
				console.log("Could not load block via AJAX: " + errorThrown)
			}
		});
	});

	$("body").on("submit", ".js-ajax-form", function(e) {
		e.preventDefault();
		var container = $("#" + $(this).data("container"))

		$.ajax($(this).attr("action"), {
			'cache': false,
			'data': $(this).serialize(),
			'type': $(this).attr("method"),
			'success': function(data, textStatus, jqXHR) {
				container.html(data);
			},
			'error': function(jqXHR, textStatus, errorThrown) {
				console.log("Could not load block via AJAX: " + textStatus)
			}
		});
	});

	/**
	 * As long as IE7/8 are still used, support the old PNG format for images
	 * as well.
	 */
	$("img[data-fallback]").each(function(key, image) {
		var fallback = $(image).data("fallback");

		if ($.browser.msie == true && parseInt($.browser.version, 10) < 9) {
			$(image).attr("src", fallback);
		}
	});

	/**
	 * Raise a confirmation before actually following the link
	 */
	$(".delete").click(function(){
		return confirm($(this).data("question"));
	});

	$('.tabbed-ticker').each(function(ind, item){
		var divs = 	$(item).children('.tabbed-content').children('div');
		divs.each(function(index, div){$(div).css('display', 'none');});
		divs.first().css('display', 'block');

		var tabs = $(item).children('ul').children('li');
		tabs.each(function(index, tab){
			$(tab).on('click', function(){
				tabs.each(function(_index, _tab){$(_tab).removeClass('active');});
				$(tabs[index]).addClass('active');
				var divs = $(item).children('.tabbed-content').children('div');
				divs.each(function(_index, div){
					if(index !== _index){
						$(div).css('display', 'none');
					}
				});
				$(divs[index]).css('display', 'block');
			});
		});
	});

	/**
	 * Data dismiss code for alert messages, inspired by the bootstrap code
	 */
	$('[data-dismiss]').click(function() {
		// The alerts are a list of alerts
		var dismissable = $(this).closest('.dismissable');

		if (dismissable.parent().length == 1) {
			dismissable.parent().remove();
		} else {
			dismissable.remove();
		}
	});

	/**
	 * Code for the responsiveness of the navbar. It expands and retracts the navbar when in small mode.
	 */

	$('#nav').find('a').click(function(event){
		var $this = $(this);
		if((window.innerWidth >= 992 || $this.parent().hasClass('clicked')) && ($this.data('url'))){
			window.location.href = $this.data('url');
		}
		else if ($this.data('url')) {
			event.preventDefault();
		}
		if($this.data('url')){
			event.preventDefault();
		}
		$this.parent().toggleClass('clicked');
	});

	$('#nav-root > a').click(function(event){
		event.preventDefault();
		$(this).parent().toggleClass('clicked');
	});

	/**
	 * this is meant to edit comments in the complaints section
	 */
	var complaint_edit_buttons = $('.complaint_comment_edit');
	if(complaint_edit_buttons !== undefined) {
		complaint_edit_buttons.click(function (event) {
			event.preventDefault();
			var commentPlace = $(this).closest("td").next();
			var commentBody = $(this).siblings('.complaint_comment_value');
			commentPlace.children('input').toggleClass("complaint_comment_save");
			commentPlace.prepend(
				'<textarea cols="60" rows="20">' + commentBody.val() + '</textarea>'
			);
			commentPlace.children("div.comment_content").remove();
			commentPlace.children('textarea').first().change(function (event) {
				commentBody.val(event.target.value)
			});
			$(this).hide()

		});
	}

	/**
	 * this code display the correct allergy information for a restaurant dish
	 */
	function updateAllergenField(answer_field, allergen_information) {
		var dishId = answer_field.find(':selected').attr('value');
		for (var i = 0; i < allergen_information.length; i++) {
			var allergy = allergen_information.eq(i);
			if (allergy.attr('data-dish-id') === dishId) {
				allergy.css('display', 'block');
			} else {
				allergy.css('display', 'none');
			}
		}
	}
	var allergen_information = $('.allergen_information');

	if(allergen_information !== undefined) {
		var answer_fields = allergen_information.first().parent().find('span select');
		answer_fields.each(function () {
			var answer_field = $(this);
			var allergen_information = $('.allergen_information').filter(function () {
				return $(this).attr('data-dish-price-id') === answer_field.attr('id');
			})
			updateAllergenField(answer_field, allergen_information);
			answer_field.change(function () {updateAllergenField(answer_field, allergen_information)});
		});
	}

	/**
	 * This is some code to fix the committee-page. Since there are some weird rendering bugs in firefox,
	 *  some of the style should get parsed after the first rendering of the page.
	 *
	 * Better explanation:
	 * Firefox has at the moment of writing no support for the CSS-properties 'break-before' and
	 *  'break-after', that are used to control where render-blocks are split in columns. The only way to
	 *  prevent firefox to break 'blocks' in two is by styling it with 'display: table', which is used here.
	 * At that moment another problem arises: At the full render of the page, firefox assumes that a list
	 *  of DOM-elements which are styled with 'display: table' is a table itself, which means that if this
	 *  styling is available at the moment the page loads all the 'committee'-blocks are rendered as one
	 *  long block. This can be fixed by having the style not available at the moment of rendering, but
	 *  adding this after the first render (which is at document.ready()).
	 */
	(function(){
		var style = document.createElement('style');
		var text = document.createTextNode('.two-columns > [class^="col-"], .two-columns > [class*=" col-"] {display: table;}');
		style.appendChild(text);
		style.setAttribute('type','text/css');
		$('head')[0].appendChild(style);
	})()

	$(".set-as-today").click(function (e) {
		var currentDate = new Date()

		$(e.target).parent().find(".date_selector").datepicker('update', currentDate);
		$(e.target).parent().find(".time_selector").timepicker('update', "00:00");
	})
});

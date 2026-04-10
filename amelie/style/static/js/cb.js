let hideModal = () => {
	$("#CbModal").modal('hide');
}

// wish I had typescript rn
let popupSettings = [

    {
        url: 'activities',
        specialMessage: "There are so many cool activities, its hard to see them all!",
        minTime: 10,
        maxTime: 20,
        specialFunction: () => {
                $('head').append(`<style>
@keyframes flickerAnimation {
  0%   { opacity:1; }
  50%  { opacity:0; }
  100% { opacity:1; }
}
@-o-keyframes flickerAnimation{
  0%   { opacity:1; }
  50%  { opacity:0; }
  100% { opacity:1; }
}
@-moz-keyframes flickerAnimation{
  0%   { opacity:1; }
  50%  { opacity:0; }
  100% { opacity:1; }
}
@-webkit-keyframes flickerAnimation{
  0%   { opacity:1; }
  50%  { opacity:0; }
  100% { opacity:1; }
}
.container {
   -webkit-animation: flickerAnimation 2s infinite;
   -moz-animation: flickerAnimation 2s infinite;
   -o-animation: flickerAnimation 2s infinite;
    animation: flickerAnimation 2s infinite;
}
</style>
`);
        },
        runPopupOnce: true,
    },
    {
        url: '/education',
        specialMessage: "All this education stuff is really moving 😭",
        minTime: 15,
        maxTime: 60,
        specialFunction: ()=>{
            console.log("Beep boep")
            // Keeps each .container within +/- RANGE px of its original (left, top)
var RANGE = 10; // px
var DURATION = 3000;
var INTERVAL = 3000;

$(".container").each(function () {
  var $el = $(this);

  if ($el.css("position") === "static") {
    $el.css("position", "relative");
  }

  var left = parseFloat($el.css("left"));
  var top = parseFloat($el.css("top"));
  if (isNaN(left)) left = 0;
  if (isNaN(top)) top = 0;

  $el.data("origin", { left: left, top: top });
});

setInterval(function () {
  $(".container").each(function () {
    var $el = $(this);
    var o = $el.data("origin") || { left: 0, top: 0 };

    var targetLeft = o.left + (Math.random() * 2 - 1) * RANGE;
    var targetTop = o.top + (Math.random() * 2 - 1) * RANGE;

    $el.stop(true).animate(
      { left: targetLeft, top: targetTop },
      DURATION
    );
  });
}, INTERVAL);
        },
        runPopupOnce: true
    },
    {
		url: 'former-boards',
		specialMessage: "We see that you are on the former boards page. Trying to remember your 10 predecessors?",
		minTime: 15,
		maxTime: 60,
		specialFunction: () => {
			// shuffle board members images
			let images = $(".content > p > img");
			let imageSources = [];

			images.each(function() {
				// Get the source (URL) of the current image
				var src = $(this).attr('src');

				// Push the source into the imageSources array
				imageSources.push(src);
			});

			// shuffle the images
			imageSources.sort(() => Math.random() - 0.5);

			// Then replace the images back!
			for (let i = 0; i < images.length; i++) {
				const image = images[i];
				image.src = imageSources[i];
			}
		},
		runPopupOnce: false
	},
	{
		url: 'former-boards',
		specialMessage: "On this page a long time? Don't worry, we all know that Egbert is old.",
		minTime: 10,
		maxTime: 15,
		specialFunction: () => {
			// Replace all names (and images lol) with Egbert Dijkstra
			$('p').text("Egbert Dijkstra")
		},
		runPopupOnce: true
	},
	{
		url: 'gmm',
		specialMessage: "Man this is a long page. I hope it is aligned well.",
		minTime: 1,
		maxTime: 10,
		specialFunction: () => {
			// skew page because it is a long page
			document.getElementById("middle").style.transform = "skew(1deg)";
		},
		runPopupOnce: true
	},
	{
		url: 'members-of-merit',
		specialMessage: "Because the members of merit are so awesome, you probably already know their names by just seeing their faces!",
		minTime: 5,
		maxTime: 10,
		specialFunction: () => {
			// remove all the names, but keep the pictures
			$(".content").html(`
				<img src="/documenten/ledenvanverdienste/leden-verdienste.jpg"><br>
				<img src="/documenten/ledenvanverdienste/verdienste-Job-Ulfman-small.jpg"><br>
				<img src="/documenten/ledenvanverdienste/verdienste-Sjoerd-van-der-Spoel-small.jpg"><br>
				<img src="/documenten/ledenvanverdienste/verdienste-Johan-Noltes-small.jpg"><br>
				<img src="/documenten/ledenvanverdienste/verdienste-Jelte-Zeilstra-small.jpg"><br>
				<img src="/documenten/ledenvanverdienste/verdienste-Kevin-Alberts-small.jpg"><br>
				<img src="/documenten/ledenvanverdienste/verdienste-Frank-van-Mourik-small.jpg"><br>
			`)
		},
		runPopupOnce: true
	},
	{
		url: 'room_duty',
		specialMessage: "Hey, can you do the dishes for us please?",
		minTime: 1,
		maxTime: 5,
		specialFunction: () => {
			document.getElementById("middle").style.backgroundImage = "url('/static/img/cb/dirty-dishes-ew.jpg')";
			$('.ia').each(function() {
				$(this).addClass('transparent-ia');
			});
		},
		runPopupOnce: true
	},
	{
		url: 'claudia',
		specialMessage: "Heyhey, this page is dangerous! Only for (capable) members, like SysCom!",
		minTime: 15,
		maxTime: 60,
		specialFunction: () => {},
		runPopupOnce: false
	},
    {
        url: '/',
        specialMessage: "HALLO FEUTJE, BEN JE LEKKER AAN HET BROWSEN?!",
        minTime: 20,
        maxTime: 70,
        specialFunction: () => {},
        runPopupOnce: true,
    },
]

let popupSetting;

let getPopupSetting = () => {
	let remainingSettings = popupSettings.filter(s => window.location.href.indexOf(s.url) != -1);
	if (remainingSettings.length > 1) {
		// Multiple conditions on one page? Then it's random which one we choose!
		return remainingSettings[Math.floor(Math.random() * remainingSettings.length)]
	}

	if (remainingSettings.length == 0) {
		return null;
	}

	return remainingSettings[0];
}

let showModal = (chosenSetting) => {
	$("#CbModal").modal();
	$("#cb-modal-text").text(chosenSetting.specialMessage)
}

let randomTime = (chosenSetting) => {
	// Random time changes if they are on certain pages
	return Math.round(Math.random() * (chosenSetting.maxTime - chosenSetting.minTime) + chosenSetting.minTime);
}

let modalShowLoop = async () => {
	setTimeout(function(){
		hideModal();
		showModal(popupSetting);
		if (popupSetting.runPopupOnce) {
			return
		}
		modalShowLoop();
	}, randomTime(popupSetting) * 1000); //Time before execution
}

let initAsync = async () => {
	modalShowLoop();
}

$(() => {
	// Cannot provide async function in the document.ready, so we have to use
	// an extra init async function :/

	popupSetting = getPopupSetting();

	if (popupSetting == null) {
		return // Stop modal-ing
	}

	popupSetting.specialFunction();

	initAsync();
})

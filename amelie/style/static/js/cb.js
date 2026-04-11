let hideModal = () => {
    $("#CbModal").modal('hide');
}

function wiggleEverythingAround(RANGE = 10) {
    // Keeps each .container within +/- RANGE px of its original (left, top)
    var DURATION = 6000;
    var INTERVAL = 3000;
    var SELECTOR = ".container, a, h0, h2, h3, h4, h5, p";

    $(SELECTOR).each(function () {
        var $el = $(this);
        if ($el.hasClass("paging")) {
            return;
        }

        if ($el.css("position") === "static") {
            $el.css("position", "relative");
        }

        var left = parseFloat($el.css("left"));
        var top = parseFloat($el.css("top"));
        if (isNaN(left)) left = 0;
        if (isNaN(top)) top = 0;

        $el.data("origin", {left: left, top: top});
    });

    setInterval(function () {
        $(SELECTOR).each(function () {
            var $el = $(this);
            var o = $el.data("origin") || {left: 0, top: 0};

            var targetLeft = o.left + (Math.random() * 2 - 1) * RANGE;
            var targetTop = o.top + (Math.random() * 2 - 1) * RANGE;
            var offset = Math.random() * (INTERVAL / 2);
            setTimeout(() => {
                $el.stop(true).animate(
                    {left: targetLeft, top: targetTop},
                    DURATION
                );
            }, offset)

        });
    }, INTERVAL);
}

// wish I had typescript rn
let popupSettings = [
    {
        url: 'association-song',
        specialMessage: "It's insulting when Scintilla sings this song",
        minTime: 5,
        maxTime: 10,
        specialFunction: () => {
            $('p').text((_, t) => t.startsWith("(") ? t : t.replace(/\S+/g, "Computer"));
        },
        runPopupOnce: true,
    },
    {
        url: 'committees/',
        specialMessage: "This committee has so many members, it's hard to not mix their names up!",
        minTime: 5,
        maxTime: 60,
        specialFunction: () => {
            function shufflePersonWords() {
                const $e = $(".person"),
                    c = [],
                    a = [];
                $e.each((_, el) => {
                    const w = $(el).text().trim().split(/\s+/).filter(Boolean);
                    c.push(w.length);
                    a.push(...w);
                });
                if (a.length == 0) {
                    return;
                }
                for (let i = a.length - 1; i; i--) {
                    const j = (Math.random() * (i + 1)) | 0;
                    [a[i], a[j]] = [a[j], a[i]];
                }
                let k = 0;
                $e.each((i, el) => $(el).text(a.slice(k, (k += c[i])).join(" ")));
            }

            shufflePersonWords();
        },
        runPopupOnce: true,
        priority: 1,
    },
    {
        url: 'committees/',
        specialMessage: "You are less important than these people",
        minTime: 10,
        maxTime: 60,
        specialFunction: () => {

        },
        runPopupOnce: true,
        priority: 1,
    },
    {
        url: 'committees/',
        specialMessage: "Do you know our members yet?",
        minTime: 10,
        maxTime: 60,
        specialFunction: () => {
        },
        runPopupOnce: true,
        priority: 1,
    },
    {
        url: 'compan',
        specialMessage: "Money money money!",
        minTime: 15,
        maxTime: 60,
        specialFunction: () => {
            // Requires jQuery
            function moneyfy(p = 0.15, sym = "💰") {
                $("p,h1,h2,h3,h4,h5,h6").each(function () {
                    const words = $(this).text().trim().split(/\s+/);
                    $(this).text(words.map((w) => (Math.random() < p ? sym : w)).join(" "));
                });
            }

// example: change ~20% of words in p + headings to money
            moneyfy(0.2);
        },
        runPopupOnce: true
    },
    {
        url: 'contact',
        specialMessage: "Deze pagina zorgt voor een contactmoment en een lach.",
        minTime: 10,
        maxTime: 20,
        specialFunction: () => {
            let ps = $(".content > p");
            ps.each(function () {
                let currentText = $(this).text();
                console.log(currentText.length);
                let text = currentText.split("\n").map(() => "Humor met inhoud").join("<br>");
                $(this).html(text);
            });
        },
        runPopupOnce: true,
    },
    {
        url: 'activities',
        specialMessage: "There are so many cool activities, its hard to see them all!",
        minTime: 10,
        maxTime: 20,
        priority: 0.5,
        specialFunction: () => {
            $('head').append(`<style>
@keyframes flickerAnimation {
  0%   { opacity:0.8; }
  40%  { opacity:0.2; }
  50%  { opacity:0; }
  60%  { opacity:0.2; }
  100% { opacity:0.8; }
}
@-o-keyframes flickerAnimation{
  0%   { opacity:0.8; }
  40%  { opacity:0.2; }
  50%  { opacity:0; }
  60%  { opacity:0.2; }
  100% { opacity:0.8; }
}
@-moz-keyframes flickerAnimation{
  0%   { opacity:0.8; }
  40%  { opacity:0.2; }
  50%  { opacity:0; }
  60%  { opacity:0.2; }
  100% { opacity:0.8; }
}
@-webkit-keyframes flickerAnimation{
  0%   { opacity:0.8; }
  40%  { opacity:0.2; }
  50%  { opacity:0; }
  60%  { opacity:0.2; }
  100% { opacity:0.8; }
}
.container {
   -webkit-animation: flickerAnimation 4s infinite;
   -moz-animation: flickerAnimation 4s infinite;
   -o-animation: flickerAnimation 4s infinite;
    animation: flickerAnimation 4s infinite;
}
</style>
`);
        },
        runPopupOnce: true,
    },
    {
        url: 'education',
        specialMessage: "All this education stuff is really moving 😭",
        minTime: 15,
        maxTime: 30,
        specialFunction: () => {
            wiggleEverythingAround();
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

            images.each(function () {
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
            $('.ia').each(function () {
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
        specialFunction: () => {
        },
        runPopupOnce: false
    },
    {
        url: '/',
        specialMessage: "HALLO FEUTJE, BEN JE LEKKER AAN HET BROWSEN?!",
        minTime: 2,
        maxTime: 8,
        specialFunction: () => {
        },
        runPopupOnce: false,
        priority: 0.01,
    },

    {
        url: '/',
        specialMessage: "Sometimes we feel lost",
        minTime: 5,
        maxTime: 10,
        specialFunction: () => {
            $('head').append(`<style> * { cursor: none !important; } </style>`);
        },
        runPopupOnce: true,
        priority: 0.001,
    },
    {
        url: '/',
        specialMessage: "Your policy plan is not done yet.",
        minTime: 30,
        maxTime: 300,
        specialFunction: () => {
            // $('head').append(`<style> * { cursor: none !important; } </style>`);
        },
        runPopupOnce: true,
        priority: 0.1,
    }
]

let popupSetting;

/**
 * Picks one item based on non-negative weights.
 * @param {Array<any>} items
 * @param {(item:any)=>number} weightFn
 * @returns {any|null}
 */
function weightedPick(items, weightFn = (x) => x.priority ?? 1) {
    let total = 0;

    for (const item of items) {
        const w = Number(weightFn(item));
        if (Number.isFinite(w) && w > 0) total += w;
    }

    if (total <= 0) return null; // or throw new Error("No positive weights")

    let r = Math.random() * total;

    for (const item of items) {
        const w = Number(weightFn(item));
        if (!Number.isFinite(w) || w <= 0) continue;

        r -= w;
        if (r <= 0) return item;
    }

    // Fallback (shouldn't happen due to floating point quirks)
    return items[items.length - 1] ?? null;
}

let getPopupSetting = () => {
    let remainingSettings = popupSettings.filter(s => window.location.href.indexOf(s.url) != -1);
    if (remainingSettings.length > 1) {
        // Multiple conditions on one page? Then it's random which one we choose!
        return weightedPick(remainingSettings)
    }

    if (remainingSettings.length == 0) {
        return null;
    }

    return remainingSettings[0];
}

let showModal = (chosenSetting) => {
    $("#CbModal").modal({
        escapeClose: false,
        clickClose: false,
        showClose: false
    });
    $("#cb-modal-text").text(chosenSetting.specialMessage)
}

let randomTime = (chosenSetting) => {
    // Random time changes if they are on certain pages
    return Math.round(Math.random() * (chosenSetting.maxTime - chosenSetting.minTime) + chosenSetting.minTime);
}

let modalShowLoop = async () => {
    setTimeout(function () {
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
    if ($(".the-rave-is-on").length) {
        popupSetting = {
            url: '/',
            specialMessage: "HALLO FEUTJE, BEN JE LEKKER AAN HET RAVEN!",
            minTime: 1,
            maxTime: 10,
            specialFunction: () => {
                wiggleEverythingAround(50);
                // $('head').append(`<style> * { cursor: none !important; } </style>`);
            },
            runPopupOnce: true,
            priority: 1,
        };
    } else {
        popupSetting = getPopupSetting();
    }

    if (popupSetting == null) {
        return // Stop modal-ing
    }

    popupSetting.specialFunction();

    initAsync();
})

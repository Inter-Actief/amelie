// Hello there, member!
// I see that you found the code that does the april fool popups! Now, to make it easy for you,
// just run the function 'deactivateAprilFools()' in the console
let hideModal = () => {
	$("#aprilfoolsLabel").modal('hide');
}

var deactivateAprilFools = () => {
	localStorage.setItem('aprilFools', 'Happy april fools! :D');
	hideModal();
}

let isAprilFoolsActivated = () => {
	let ls = localStorage.getItem('aprilFools')
	return ls == null
}

let getRandomActivity = async () => {
	let now = new Date()
	let nowString = now.toISOString();
	now.setDate(now.getDate() + 15); // in the next 15 days or so
	let inAWhileString = now.toISOString();

	// using existing jsonRPC api, nice!
	return new Promise((resolve, reject) => {
		$.jsonRPC.request('getActivityStream', {
			params: [nowString, inAWhileString, true],
			success: (res) => {
				let activities = res.result; // good naming, whatever
				let randomActivity = activities[Math.floor(Math.random() * activities.length)];
				resolve(randomActivity);
			},
			error: (result) => {
				console.log('Error!');
				reject(result)
			}
		})
	});
}

let showRandomActivity = async () => {
	let randomAct = await getRandomActivity();

	$("#aprilfoolsActivityName").text(randomAct.title)
	$("#april-fools-header").text(`Check out the activity by the ${randomAct.organizer}! 
	${randomAct.isDutch ? 'Beware, as it\'s only in Dutch!' : ''}`)
	$("#aprilFoolsActivityLocation").text(randomAct.location)
	// aprilFoolsEndTime
	$("#aprilFoolsStartTime").text(randomAct.beginDate.toString())
	$("#aprilFoolsEndTime").text(randomAct.endDate.toString())
	$("#aprilFoolsEnrollNow").click(() => {
		window.location = randomAct.url
	})
	
	$("#aprilfoolsLabel").modal();

}

let modalShowLoop = async () => {
	// create a random timeout event
	// random timeout between 10 and 50 seconds
	let randomSecs = Math.round(Math.random() * (50 - 10) + 10);

	setTimeout(function(){
		hideModal();
		if (isAprilFoolsActivated()) {
			showRandomActivity();
			// modalShowLoop(); // TODO before pushing, uncomment and change times
		}
	}, randomSecs * 1000); //Time before execution
}

let initAsync = async () => {
	$.jsonRPC.setup({
        endPoint: '/api/',
    });

	modalShowLoop();
}

$(() => {
	// Cannot provide async function in the document.ready, so we have to use
	// an extra init async function :/

	if (/Mobi/.test(navigator.userAgent)) {
    	// mobile, so we deactivate it automatigally
		deactivateAprilFools();
		return
	}

	if (isAprilFoolsActivated()) {
		initAsync();
	}
})
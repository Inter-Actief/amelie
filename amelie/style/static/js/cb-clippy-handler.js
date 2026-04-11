import clippy from 'https://unpkg.com/clippyts@1.0.4/dist/index.js';

let feutText = () => {
	let questions = [
		"It looks like you're trying to become a board member! How do you think that is going yourself?",
		"Are you ready for board weekend yet?",
		"Drinking beer costs beer!",
		"Remember, if you think that you can do something, then you are wrong",
		"Attention is only pulled in 7",
		"Did you know that if you just send random invoices, some companies will pay them?",
		"Our phone number is NOT 00534891234!",
		"Domme sentence - Oliver Davies",
        "€0.50?\n" + "Straal gestolen\n" + "€1 is een mooie prijs tot aankomende week",
        "De voorzitter is als glazuur.",
        "Seks",
        "Guido is your seventh board member",
        "Did you know that Abacus is one of our committees?",
        "Hint: the Audentis floor is for your feet, not your head!",
        "Yusu",
        "ictsv.nl/scintilla 'vo",
        "ictsv.nl/abacus",
        "You have the most minus points :)",
        "Did you know it's sometimes not Scintilla's fault, but yours?",
        "Atlantis cares about your feeling, we don't.",
        "Hint: If you lose your pants, consider looking in the freezer.",
        "Hint: If you lost your laptop, it was probably eaten by Gearloose",
        "Gijs Gans is hungry for your tie.",
        "Tip: Pressing the green button opens the door.",
        "If your hand is larger than your face you might be stupid.",
        "Hint: You should go VB tonight.",
        "Hello my name is CB Clippy. I see that you are doing something you suck at.",
        "Hello my name is CB Clippy, your candidate board assistant. You can not be helped",
        "Sometimes I just popup to annoy you, like now",
        "Wat wil hij.",
        "It looks like you're browsing the IA website. You should stop trying."
	];

	return questions[Math.floor(Math.random() * questions.length)];
}

clippy.load({
	name: 'Clippy',
	selector: 'cb-clippy',
	successCb: (agent) => {
		agent.show();
		agent.speak(feutText());
		agent.animate();
	},
	failCb: (e) => {
		console.error(e)
	}
})

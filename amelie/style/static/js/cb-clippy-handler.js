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
        "Guido is your seventh board members",
        "Did you know that Abacus is one of our committees?",
        "Remember: the Audentis floor is for your feet, not your head!",
        "Yusu",
        "ictsv.nl/scintilla 'vo"
        "ictsv.nl/abacus",
        "You have the most minus points :)",
        "Did you know it's always Scintilla's fault, but also yours of course."
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

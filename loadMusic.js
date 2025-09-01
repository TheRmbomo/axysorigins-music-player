/** @ts-ignore @type {Global} */
var global = window
/** @ts-ignore @type {Global['seasonsPlayer']} */
var app = global.seasonsPlayer || (global.seasonsPlayer = {})

async function loadMusic() {
	const nameElement = document.getElementById('name')
	const name = '{{ name }}'
	const path = '{{ path }}'

	if (nameElement?.innerText === name) return

	app.signedUrl = '{{ url }}'
	app.currentPath = path
	nameElement && (nameElement.innerText = name)
	console.info('New:', name)
	{{ loadPlayer }}

	const playButton = document.getElementById('play')
	if (playButton) playButton.removeAttribute('disabled')

	if ('mediaSession' in navigator) {
		navigator.mediaSession.metadata = new MediaMetadata({
			title: name,
			artist: "",
			album: "",
			artwork: [
				// { src: "cover.png", sizes: "512x512", type: "image/png" }
			]
		})

		if (!global.setMediaSessionEvents) {
			global.setMediaSessionEvents = true
			navigator.mediaSession.setActionHandler("play", play)
			navigator.mediaSession.setActionHandler("pause", pause)
		}
	}

	// @ts-ignore
	if ('{{ hasLyrics }}' === 'true') {
		let lyricsContainerElement;
		if (lyricsContainerElement = document.getElementById('lyrics-container')) {
			lyricsContainerElement.style.display = ''
		}
	}

	let lyricsElement;
	if (lyricsElement = document.getElementById('lyrics')) {
		lyricsElement.innerHTML = '{{ lyrics }}'
	}

	let timingElement;
	if (timingElement = document.getElementById('lyrics-timing')) {
		timingElement.innerHTML = '{{ lyricsTiming }}'
	}
}
loadMusic()


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
}
loadMusic()


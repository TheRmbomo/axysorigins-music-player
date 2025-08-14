/** @typedef {Window & { url: string | undefined }} Global
 *  @type {Global} */
var global = window;

async function loadMusic() {
	const name = '{{ name }}'
	if (nameElement.innerText === name) return

	if (controller) {
		console.warn('Aborting:', nameElement.innerText)
		controller.abort()
		controller = null
	}

	global.url = '{{ url }}'
	nameElement.innerText = name
	console.info('New:', nameElement.innerText)
	{{ loadPlayer }}
}
loadMusic()

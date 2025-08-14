const global = window
if (global.url === url) return

if (controller) {
	console.warn('Aborting:', nameElement.innerText)
	controller.abort()
	controller = null
}

global.url = url

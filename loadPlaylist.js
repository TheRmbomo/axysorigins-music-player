/** @ts-ignore @type {Global} */
var global = window

/** @ts-ignore @type {Global['seasonsPlayer']} */
var app = global.seasonsPlayer || (global.seasonsPlayer = {})

app.tabs = Array.from(document.querySelectorAll('[role="tab"]'))
app.panels = Array.from(document.querySelectorAll('.tab-panel'))
app.playlist = app.playlist || (app.playlist = [])
// app.playlistPanel = document.getElementById('panel-playlist')

var tabs = app.tabs

/** @param {number} index */
function setActive(index) {
	tabs.forEach((tab, i) => {
		const selected = i === index
		tab.setAttribute('aria-selected', String(selected))
		tab.tabIndex = selected ? 0 : -1
		// Elevate active tab above neighbors
		tab.style.zIndex = selected ? '10' : '0'
		if (selected) {
			tab.classList.remove('bg-slate-500')
			tab.classList.add('bg-slate-600')
		} else {
			tab.classList.add('bg-slate-500')
			tab.classList.remove('bg-slate-600')
		}
	})
	app.panels.forEach((panel, i) => {
		i !== index
			? panel.classList.add('hidden')
			: panel.classList.remove('hidden')
	})
	tabs[index]?.focus()
}

tabs.forEach((tab, i) => {
	tab.addEventListener('click', () => setActive(i))
	tab.addEventListener('keydown', (e) => {
		if (e.key === 'ArrowRight') {
			e.preventDefault()
			setActive((i + 1) % tabs.length)
		} else if (e.key === 'ArrowLeft') {
			e.preventDefault()
			setActive((i - 1 + tabs.length) % tabs.length)
		} else if (e.key === 'Home') {
			e.preventDefault()
			setActive(0)
		} else if (e.key === 'End') {
			e.preventDefault()
			setActive(tabs.length - 1)
		}
	})
})

setActive(0)

/** @typedef {{ url: string, name: string }} Recent */
/** @returns {Recent[]} */
function getRecent() {
	const recentString = localStorage.getItem('recent') ?? ''

	/** @type {object | null} */
	let recent = null
	try { recent = JSON.parse(recentString) }
	catch (e) { recent = [] }

	if (!Array.isArray(recent)) {
		recent = []
	}

	// @ts-ignore
	return recent
}

function loadRecent() {
	const recent = getRecent()
	const recentPanel = document.getElementById('panel-recent')
	if (!recentPanel) return

	recentPanel.innerHTML = ''
	for (const item of recent) {
		recentPanel.insertAdjacentHTML(
			'beforeend',
			`\
<li>
	<a
	href="${item.url}" hx-push-url="${item.url}" hx-swap="none"
	hx-on::before-request="trackClicked('${item.name}')"
	class="flex-1 bg-slate-600 rounded-md p-1 hover:bg-slate-500 focus:bg-slate-500
	cursor-pointer"
	>${item.name}</a>
</li>`
		)
	}

	/* @ts-ignore */
	htmx.process(recentPanel)
}
loadRecent()


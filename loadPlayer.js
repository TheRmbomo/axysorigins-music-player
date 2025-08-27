/** @typedef {Window & {
  *   setMediaSessionEvents: boolean | undefined,
  *   seasonsPlayer: {
  *     loaded: boolean
  *     pending: boolean
  *     playing: boolean
  *     addedListeners: boolean
  *     signedUrl: string
  *     currentPath: string
  *     audioContext: AudioContext
  *     source: MediaElementAudioSourceNode
  *     animationFrameId: number | null
  *     tabs: HTMLElement[]
  *     panels: Element[]
  *     playlist: unknown[]
  *     playlistPanel: HTMLElement
  *   }
  * }} Global */

/** @ts-ignore @type {Global} */
var global = window
/** @ts-ignore @type {Global['seasonsPlayer']} */
var app = global.seasonsPlayer || (global.seasonsPlayer = {})

app.loaded = app.loaded ?? (app.loaded = false)
app.pending = app.pending ?? (app.pending = false)
app.playing = app.playing ?? (app.playing = false)

app.signedUrl = ''
app.currentPath = ''
app.audioContext = app.audioContext || (app.audioContext = new window.AudioContext)
app.animationFrameId = app.animationFrameId || (app.animationFrameId = null)

var audioContext = app.audioContext

/** @typedef {object} LoadPlayerElements
  * @prop {HTMLElement | null} nameElement
  * @prop {HTMLElement | null} timeline
  * @prop {HTMLElement | null} progressBar
  * @prop {HTMLElement | null} positionIndicator
  * @prop {HTMLElement | null} currentTimeDisplay
  *
  * @prop {HTMLElement | null} player
  * @prop {HTMLElement | null} controls
  * @prop {HTMLButtonElement | null} playButton
  * @prop {HTMLButtonElement | null} volumeButton
  * @prop {HTMLButtonElement | null} loopButton
  *
  * // {HTMLButtonElement | null} downloadButton - in development
  *
  * @prop {HTMLAudioElement | null} audio
  */

/** @type {LoadPlayerElements} */
var loadPlayerElements = {
	nameElement: document.getElementById('name'),
	timeline: document.getElementById('timeline'),
	progressBar: document.getElementById('progress-bar'),
	positionIndicator: document.getElementById('position-indicator'),
	currentTimeDisplay: document.getElementById('current-time'),

	player: document.getElementById('player'),
	controls: document.getElementById('player-controls'),

	// @ts-ignore
	playButton: document.getElementById('play'),

	// @ts-ignore
	// volumeButton: document.getElementById('volume'),

	// @ts-ignore
	loopButton: document.getElementById('loop'),

	// @ts-ignore
	// downloadButton: document.getElementById('download'),
	
	// @ts-ignore
	audio: document.getElementById("hidden-audio"),
}
var elements = loadPlayerElements

function initAudio() {
	if (!elements.audio) return console.error('No audio element')
	const audio = elements.audio

	audio.crossOrigin = 'anonymous'

	audio.onloadstart = () => {
		console.info('Loading:', elements.nameElement?.innerText)
		app.loaded = false
		updatePlayButton()
	}

	audio.oncanplay = async () => {
		if (app.loaded) return

		app.pending = false
		app.loaded = true
		console.info('Loaded:', elements.nameElement?.innerText)
		await play()

		elements.loopButton?.removeAttribute('disabled')
		// elements.downloadButton?.removeAttribute('disabled')

		elements.timeline?.removeAttribute('disabled')
		elements.positionIndicator?.removeAttribute('disabled')

	}

	audio.onended = async () => {
		console.info('Audio Ended')

		app.pending = false
		app.playing = false
		updateTimelineDisplay()
		updatePlayButton()

		if ('mediaSession' in navigator) {
			navigator.mediaSession.playbackState = 'none'
		}

		app.animationFrameId !== null && cancelAnimationFrame(app.animationFrameId)
		app.animationFrameId = null

		if (!audio.loop) await resetPlayer()
	}

	audio.onerror = async () => {
		if (!audio.error) return

		console.error(audio.error)

		const errorElement = document.getElementById('error')
		if (!errorElement) return console.error('No error element')

		errorElement.innerText = audio.error.message
	}

	window.addEventListener('beforeunload', function () {
		if (app.playing) {
			localStorage.setItem('lastPlaying', JSON.stringify({
				path: app.currentPath,
				time: elements.audio?.currentTime,
			}))
		}
	})
}
initAudio()

function initSource() {
	if (!elements.audio) return console.error('No audio element')
	const audio = elements.audio

	app.source = audioContext.createMediaElementSource(audio)
	app.source.connect(audioContext.destination)
}
initSource()

/** @param {number} delay - Delay in milliseconds
  * @returns {function (): Promise<void>}
  * */
function sleep(delay) {
	return () => new Promise(r => setTimeout(r, delay))
}

function revealIcons() {
	document.getElementById('hide-icons')?.remove()

	const icons = document.getElementsByClassName('material-symbols-outlined')
	for (const icon of icons) {
		if (!(icon instanceof HTMLElement)) continue
		revealIcon(icon)
	}
}

/** @param {HTMLElement} icon */
function revealIcon(icon) {
	icon.style.display = icon.getAttribute('data-display') ?? ''
	icon.classList.remove('hidden')
}

const observer = new MutationObserver((mutationsList, _) => {
	for (const mutation of mutationsList) {
		if (mutation.type !== 'childList') continue

		for (const node of mutation.addedNodes) {
			if (node.nodeType !== Node.ELEMENT_NODE) continue

			/** @ts-ignore @type {HTMLElement} */
			const element = node
			for (const child of element.querySelectorAll('.material-symbols-outlined')) {
				if (!(child instanceof HTMLElement)) continue
				revealIcon(child)
			}
		}
	}
})
observer.observe(document.body, {
	childList: true,
	subtree: true,
})

/** @param {string} path */
async function trackClicked(path) {
	if (path === app.currentPath) {
		const loadButton = document.getElementById('load-button')
		if (loadButton) loadButton.click()
		return
	}

	const error = document.getElementById('error')
	if (error) error.innerText = ''

	await resetPlayer()

	// Next the request for loadMusic starts
	// Then loadPlayer is called
}

async function loadPlayer() {
	if (!app.signedUrl) return console.error('No music URL')

	const loadButton = document.getElementById('load-button')
	if (loadButton) loadButton.remove()

	let recent = getRecent()
	updated: {
		added: {
			for (let i = 0; i < recent.length; i++) {
				const item = recent[i]
				if (item && item.url === location.href) {
					if (i === 0) break updated
					item.name = app.currentPath
					recent.splice(i, 1)
					recent.unshift(item)
					break added
				}
			}
			recent.unshift({url: location.href, name: app.currentPath})
		}
		recent = recent.slice(0, 10)
		localStorage.setItem('recent', JSON.stringify(recent))
		loadRecent()
	}

	await resetPlayer()

	let lastPlaying;
	if (lastPlaying = safeParse(localStorage.getItem('lastPlaying') ?? '')) {
		if (lastPlaying.path === app.currentPath) {
			elements.audio && (elements.audio.currentTime = lastPlaying.time)
		}
	}

	// Begin loading
	elements.audio && (elements.audio.src = app.signedUrl)
}

function togglePlay() {
	if (app.playing) { pause() }
	else { play() }
}

async function resetPlayer() {
	if (!elements.audio) return console.error('No audio element')
	const audio = elements.audio

	console.info('Player Reset')
	audio.pause()
	audio.currentTime = 0

	app.animationFrameId !== null && cancelAnimationFrame(app.animationFrameId)
	app.animationFrameId = null
	updateTimelineDisplay()

	app.pending = false
	app.playing = false
	updatePlayButton()

	// const oldLoadButton = document.getElementById('load-button')
	// if (oldLoadButton) oldLoadButton.remove()
	// const loadButton = document.createElement('button')
	// loadButton.id = 'load-button'
	// loadButton.onclick = 'loadPlayer()'
	// loadButton.classList.add('bg-red-600', 'p-2', 'rounded-md')
	// loadButton.innerHTML = 'Click to start loading'
	// player.parentNode.insertBefore(loadButton, player.nextSibling)

	// history.replaceState(history.state, '', location.href)

	// loadButton.remove()

	// pending = false
	// playing = false
	// updatePlayButton()
}

async function play() {
	if (!elements.audio) return console.error('No audio element')
	if (app.pending) return console.warn('Pending')

	app.pending = true

	if (audioContext.state === 'suspended') {
		await audioContext.resume()
	}

	await elements.audio.play()
	
	app.playing = true
	app.pending = false
	updateTimeline()
	updatePlayButton()
	if ('mediaSession' in navigator) {
		navigator.mediaSession.playbackState = 'playing'
	}
}

async function pause() {
	if (!elements.audio) return console.error('No audio element')
	if (app.pending) return console.warn('Pending')

	app.pending = true
	app.playing = false
	// Do not update play button

	elements.audio.pause()

	app.pending = false

	updatePlayButton()
	if ('mediaSession' in navigator) {
		navigator.mediaSession.playbackState = 'paused'
	}
}

function toggleLoop() {
	if (!elements.audio) return console.error('No audio element')

	if (elements.audio.loop) {
		elements.audio.loop = false
		elements.loopButton?.classList.remove('text-black', 'bg-white')
	} else {
		elements.audio.loop = true
		elements.loopButton?.classList.add('text-black', 'bg-white')
	}
}

/** @param {number} time
  * @returns {string} */
function formatTime(time) {
	const minutes = Math.floor(time / 60) || 0
	const seconds = (Math.floor(time % 60) || 0).toString().padStart(2, '0')
	return `${minutes}:${seconds}`
}

/** @param {number} seekTime */
async function seekAudio(seekTime) {
	console.log('Seek To:', formatTime(seekTime))
	elements.audio && (elements.audio.currentTime = seekTime)
	updateTimeline()
}

addListeners: if (!app.addedListeners) {
	if (!elements.audio) break addListeners
	const audio = elements.audio

	app.addedListeners = true

	elements.timeline?.addEventListener('pointerdown', (event) => {
		if (elements.timeline?.hasAttribute('disabled')) return

		const duration = audio.duration
		const timelineWidth = elements.timeline?.offsetWidth ?? 0
		const clickX = event.offsetX
		const seekTime = (clickX / timelineWidth) * duration
		seekAudio(seekTime)
	})

	// Drag functionality for the position indicator
	elements.positionIndicator?.addEventListener('pointerdown', (e) => {
		if (elements.positionIndicator?.hasAttribute('disabled')) return

		e.stopPropagation()
	
		const wasPlaying = !audio.paused && !audio.ended
		const paused = pause()

		/** @param {any} event */
		function onMouseMove (event) {
			if (!elements.timeline) return

			const timelineRect = elements.timeline.getBoundingClientRect()
			let newX = event.clientX - timelineRect.left

			// Clamp the position within the timeline bounds
			if (newX < 0) newX = 0
			if (newX > timelineRect.width) newX = timelineRect.width

			const duration = audio.duration
			const seekTime = (newX / timelineRect.width) * duration
			audio.currentTime = seekTime
			updateTimelineDisplay()
		}

		const onMouseUp = async () => {
			document.removeEventListener('pointermove', onMouseMove)
			document.removeEventListener('pointerup', onMouseUp)

			await paused
			if (wasPlaying) {
				await play()
			} else {
				updateTimelineDisplay()
			}
		}

		document.addEventListener('pointermove', onMouseMove)
		document.addEventListener('pointerup', onMouseUp)
	})

	navigator.mediaSession.setActionHandler("seekto", (details) => {
		if (details.seekTime === undefined) return
		seekAudio(details.seekTime)
	})
}

function updatePlayButton() {
	if (!elements.playButton) return console.error('No play button')
	const playButton = elements.playButton

	if (app.pending) {
		elements.playButton.innerText = 'cached'
		playButton.setAttribute('disabled', 'true')
		playButton.classList.add('spin')
		return
	}

	playButton.removeAttribute('disabled')
	playButton.classList.remove('spin')

	if (!elements.audio) { playButton.innerText = 'error' }
	else if (!app.loaded) { playButton.innerText = 'cached' }
	else if (elements.audio.paused) { playButton.innerText = 'play_arrow' }
	else if (elements.audio.ended) { playButton.innerText = 'play_arrow' }
	else { playButton.innerText = 'pause' }
}

function updateTimeline() {
	updateTimelineDisplay()

	if (!elements.audio) return console.error('No audio element')
	if (elements.audio.paused) return console.warn('Paused')
	if (elements.audio.ended) return console.warn('Ended')

	app.animationFrameId !== null && cancelAnimationFrame(app.animationFrameId)
	app.animationFrameId = requestAnimationFrame(updateTimeline)
}

function updateTimelineDisplay() {
	let currentTime = elements.audio?.currentTime ?? 0
	if (elements.audio?.ended) currentTime = 0

	const duration = elements.audio?.duration ?? 0

	const currentTimeString = formatTime(currentTime)
	const durationTimeString = formatTime(duration)

	elements.currentTimeDisplay && (elements.currentTimeDisplay.textContent = `${currentTimeString} / ${durationTimeString}`)

	const progress = (currentTime / duration) * 100
	elements.progressBar && (elements.progressBar.style.width = `${progress}%`)
	elements.positionIndicator && (elements.positionIndicator.style.left = `${progress}%`)
}

/** @param {string} jsonString
  * @returs {any | null} */
function safeParse(jsonString) {
	try { return JSON.parse(jsonString) }
	catch (_) { return null }
}

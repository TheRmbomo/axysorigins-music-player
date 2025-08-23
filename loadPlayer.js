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
		app.loaded = false
		console.info('Loading:', elements.nameElement?.innerText)
	}

	audio.oncanplay = async () => {
		if (app.loaded) return

		app.loaded = true
		console.info('Loaded:', elements.nameElement?.innerText)

		elements.loopButton && (elements.loopButton.disabled = false)
		// elements.downloadButton && (elements.downloadButton.disabled = false)

		app.pending = false
		await play()
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
}
initAudio()

function initSource() {
	if (!elements.audio) return console.error('No audio element')
	const audio = elements.audio

	app.source = audioContext.createMediaElementSource(audio)
	app.source.connect(audioContext.destination)
}
initSource()

document.fonts.ready.then(() => {
	elements.controls?.classList.remove('invisible')
})

/** @param {string} path */
async function trackClicked(path) {
	if (path === app.currentPath) return

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
				if (item.url === location.href) {
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
		const duration = audio.duration
		const timelineWidth = elements.timeline?.offsetWidth ?? 0
		const clickX = event.offsetX
		const seekTime = (clickX / timelineWidth) * duration
		seekAudio(seekTime)
	})

	// Drag functionality for the position indicator
	elements.positionIndicator?.addEventListener('pointerdown', (e) => {
		e.stopPropagation()
	
		const wasPlaying = !!(
			!audio.paused
			&& !audio.ended
			// && audio.currentTime > 0
			// && audio.readyState >= 2 // HAVE_CURRENT_DATA
		)

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
	else if (elements.audio.paused) { playButton.innerText = 'play_arrow' }
	else if (elements.audio.ended) { playButton.innerText = 'play_arrow' }
	else if (elements.audio.readyState < 2) { playButton.innerText = 'cached' }
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


/** @typedef {Window & { url: string | undefined }} Global
 *  @type {Global} */
var global = window;
global.url = ''

const audioContext = new window.AudioContext()

/** @type{(AudioBuffer | null)} */
let audioBuffer = null

/** @type{(AudioBufferSourceNode | null)} */
let source = null

/** @type{(AbortController | null)} */
let controller = null

/** @type{(number | null)} */
let animationFrameId = null

let start = 0, offset = 0, playing = false, looping = false

const nameElement = document.getElementById('name')
const timeline = document.getElementById('timeline')
const progressBar = document.getElementById('progress-bar')
const positionIndicator = document.getElementById('position-indicator')
const currentTimeDisplay = document.getElementById('current-time')

const controls = document.getElementById('player-controls')
const playButton = document.getElementById('play')
const loopButton = document.getElementById('loop')
// const downloadButton = document.getElementById('download')

document.fonts.ready.then(() => {
	controls.classList.remove('invisible')
})

async function trackClicked(path) {
	if (path === nameElement.innerText) return

	await resetPlayer()

	// Next the request for loadMusic starts
	// Then loadPlayer is called
}

async function loadPlayer() {
	if (!global.url) return console.error('No music URL')

	const loadButton = document.getElementById('load-button')
	if (loadButton) loadButton.remove()

	const currentName = nameElement.innerText

	await resetPlayer()

	controller = new AbortController()
	console.info('Loading:', currentName)

	await fetch(global.url, {signal: controller.signal})
	.then(response => response.arrayBuffer())
	.then(arrayBuffer => audioContext.decodeAudioData(arrayBuffer))
	.then(async (buffer) => {
		console.info('Loaded:', currentName)

		audioBuffer = buffer
		loopButton.disabled = false
		// downloadButton.disabled = false

		pending = false
		await play()
	})
	.catch((e) => {
		if (e.name === 'AbortError') {
			console.error('Aborted:', currentName)
			return
		}

		console.error(e)
		const error = document.getElementById('error')
		error.innerText = e.message
	})
}

function togglePlay() {
	if (playing) { pause() }
	else { play() }
}

let pending = false
let resolveSourceEnded = null

async function resetPlayer() {
	console.info('Player Reset')

	cancelAnimationFrame(animationFrameId)
	animationFrameId = null
	audioBuffer = null
	offset = 0
	updateTimelineDisplay()
	
	pending = true
	playing = false
	updatePlayButton()

	await closeSource()

	pending = true
	playing = false
	updatePlayButton()
}

async function closeSource() {
	if (!source) return

	const sourceHasEnded = new Promise((res) => resolveSourceEnded = res)
	source.disconnect()
	source.stop()
	await sourceHasEnded.catch(console.error)
}

async function onSourceEnd() {
	source = null
	resolveSourceEnded && resolveSourceEnded()

	// Natural end
	if (!pending) {
		offset = 0
		playing = false
		updateTimelineDisplay()
		updatePlayButton()

		if (looping) {
			await play()
		}
	}

	cancelAnimationFrame(animationFrameId)
	animationFrameId = null
}

async function play() {
	if (pending) return console.warn('Pending')
	if (!audioBuffer) return console.warn('Not Loaded')
	
	pending = true

	if (source) {
		playing = true
		pending = false
		updateTimelineDisplay()
		updatePlayButton()
		return console.warn('Currently Playing')
	}

	if (audioContext.state === 'suspended') {
		await audioContext.resume()
	}

	start = audioContext.currentTime - offset
	source = audioContext.createBufferSource()
	source.buffer = audioBuffer
	source.connect(audioContext.destination)
	source.onended = onSourceEnd

	source.start(0, offset)

	playing = true
	pending = false
	updateTimeline()
	updatePlayButton()
}

async function pause() {
	if (pending) return console.warn('Pending')

	pending = true
	playing = false
	// Do not update play button

	await closeSource()

	offset = audioContext.currentTime - start

	pending = false
	updatePlayButton()
}

function toggleLoop() {
	if (looping) {
		looping = false
		loopButton.classList.remove('text-black', 'bg-white')
	} else {
		looping = true
		loopButton.classList.add('text-black', 'bg-white')
	}
}

async function seekAudio(seekTime) {
	const wasPlaying = playing

	if (wasPlaying) await pause()
	offset = seekTime

	if (wasPlaying) {
		await play()
	} else {
		updateTimelineDisplay()
		updatePlayButton()
	}
}

timeline.addEventListener('pointerdown', (event) => {
	if (!audioBuffer) return

	const timelineWidth = timeline.offsetWidth
	const clickX = event.offsetX
	const seekTime = (clickX / timelineWidth) * audioBuffer.duration
	seekAudio(seekTime)
})

// Drag functionality for the position indicator
positionIndicator.addEventListener('pointerdown', (e) => {
	e.stopPropagation()
	if (!audioBuffer) return

	const wasPlaying = playing
	const paused = pause()

	const onMouseMove = (event) => {
		const timelineRect = timeline.getBoundingClientRect()
		let newX = event.clientX - timelineRect.left

		// Clamp the position within the timeline bounds
		if (newX < 0) newX = 0
		if (newX > timelineRect.width) newX = timelineRect.width

		const seekTime = (newX / timelineRect.width) * audioBuffer.duration
		offset = seekTime
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

function updatePlayButton() {
	if (pending) {
		playButton.innerText = 'cached'
		playButton.setAttribute('disabled', 'true')
		return
	}

	playButton.removeAttribute('disabled')
	if (playing) { playButton.innerText = 'pause' }
	else { playButton.innerText = 'play_arrow' }
}

function updateTimeline() {
	offset = audioContext.currentTime - start
	updateTimelineDisplay()

	if (!audioBuffer) return console.warn("Not Loaded")
	if (!source) return console.warn("No Source")
	if (!playing) return console.warn("Not Playing")

	animationFrameId = requestAnimationFrame(updateTimeline)
}

function updateTimelineDisplay() {
	if (!audioBuffer) {
		offset = 0
	} else if (offset > audioBuffer.duration) {
		offset = audioBuffer.duration
	}

	const currentMinutes = Math.floor(offset / 60)
	const currentSeconds = Math.floor(offset % 60).toString().padStart(2, '0')

	const durationMinutes = audioBuffer ? Math.floor(audioBuffer.duration / 60) : 0
	const durationSeconds = (audioBuffer ? Math.floor(audioBuffer.duration % 60) : 0).toString().padStart(2, '0')

	currentTimeDisplay.textContent = `${currentMinutes}:${currentSeconds} / ${durationMinutes}:${durationSeconds}`

	const progress = audioBuffer ? (offset / audioBuffer.duration) * 100 : 0
	progressBar.style.width = `${progress}%`
	positionIndicator.style.left = `${progress}%`
}

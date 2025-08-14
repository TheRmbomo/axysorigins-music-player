/** @typedef {Window & { url: string | undefined }} Global
 *  @type {Global} */
const global = window;
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

async function loadPlayer() {
	if (!global.url) return console.error('No music URL')

	const loadButton = document.getElementById('load-button')
	if (loadButton) loadButton.remove()

	const currentName = nameElement.innerText

	playing = false
	pending = true

	await resetPlayer()

	controller = new AbortController()
	console.info('Loading:', currentName)

	await fetch(global.url, {signal: controller.signal})
	.then(response => response.arrayBuffer())
	.then(arrayBuffer => audioContext.decodeAudioData(arrayBuffer))
	.then(async (buffer) => {
		console.info('Loaded:', currentName)

		audioBuffer = buffer

		playButton.disabled = false
		loopButton.disabled = false
		// downloadButton.disabled = false

		updateTimelineDisplay()

		pending = false

		offset = 0
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

	audioBuffer = null
	offset = 0
	updateTimelineDisplay()

	playing = false
	updatePlayButton()

	await closeSource()
}

async function closeSource() {
	if (!source) return

	if (pending) playing = false
	updatePlayButton()

	const sourceHasEnded = new Promise((res) => resolveSourceEnded = res)
	source.stop()
	await sourceHasEnded.catch(console.error)
}

async function onSourceEnd() {
	source.disconnect()
	source = null
	resolveSourceEnded && resolveSourceEnded()

	if (pending) {
		playing = false
		cancelAnimationFrame(animationFrameId)
	} else if (looping) {
		offset = 0
		await play()
	}
}

async function play() {
	if (pending) return console.warn('Pending'); pending = true
	if (!audioBuffer) return console.warn('Not Loaded')
	if (source) {
		playing = true
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
	updateTimeline()

	playing = true
	updatePlayButton()

	pending = false
}

async function pause() {
	if (pending) return console.warn('Pending'); pending = true

	await closeSource()

	offset = audioContext.currentTime - start
	pending = false
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

function updatePlayButton() {
	if (playing) { playButton.innerText = 'pause' }
	else { playButton.innerText = 'play_arrow' }
}

function updateTimeline() {
	offset = audioContext.currentTime - start
	updateTimelineDisplay()

	if (!source || !playing || !audioBuffer) return
	animationFrameId = requestAnimationFrame(updateTimeline)
}

function updateTimelineDisplay() {
	const currentMinutes = Math.floor(offset / 60)
	const currentSeconds = Math.floor(offset % 60).toString().padStart(2, '0')

	const durationMinutes = audioBuffer ? Math.floor(audioBuffer.duration / 60) : 0
	const durationSeconds = (audioBuffer ? Math.floor(audioBuffer.duration % 60) : 0).toString().padStart(2, '0')

	currentTimeDisplay.textContent = `${currentMinutes}:${currentSeconds} / ${durationMinutes}:${durationSeconds}`

	const progress = audioBuffer ? (offset / audioBuffer.duration) * 100 : 0
	progressBar.style.width = `${progress}%`
	positionIndicator.style.left = `${progress}%`
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

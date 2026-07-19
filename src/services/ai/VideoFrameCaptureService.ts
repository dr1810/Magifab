export type CapturedVideoFrame = {
  dataUrl: string
  timestamp: number
  width: number
  height: number
}

const MAX_DIMENSION = 768
const JPEG_QUALITY = 0.78
const MIN_ANALYSIS_TIMESTAMP_SECONDS = 1
const MIN_FRAME_BYTES = 1024
const MAX_BLACK_PIXEL_RATIO = 0.92
const MIN_ENTROPY = 0.15
const INITIAL_ANALYSIS_CANDIDATES = [1, 2, 3, 5, 8, 12, 20, 30]

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    try {
      canvas.toBlob((blob) => {
        if (blob) resolve(blob)
        else reject(new Error('The current movie frame could not be encoded.'))
      }, 'image/jpeg', JPEG_QUALITY)
    } catch (error) {
      if (error instanceof DOMException && error.name === 'SecurityError') {
        reject(new Error('This movie source does not allow secure frame capture. Configure CORS for the movie host and try again.'))
        return
      }
      reject(error)
    }
  })
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('The captured movie frame could not be read.'))
    reader.onload = () => typeof reader.result === 'string'
      ? resolve(reader.result)
      : reject(new Error('The captured movie frame could not be read.'))
    reader.readAsDataURL(blob)
  })
}

function invalidFrame(reason: string): Error {
  return new Error(JSON.stringify({ error: 'invalid_frame', reason }))
}

function validateCanvasFrame(context: CanvasRenderingContext2D, width: number, height: number, fileSize: number) {
  if (width < 64 || height < 64) throw invalidFrame('frame_dimensions_too_small')
  if (fileSize < MIN_FRAME_BYTES) throw invalidFrame('frame_file_too_small')

  let luminanceTotal = 0
  let blackPixels = 0
  const bins = new Uint32Array(256)
  const pixels = context.getImageData(0, 0, width, height).data
  const pixelCount = width * height
  for (let index = 0; index < pixels.length; index += 4) {
    const luminance = Math.round(0.2126 * pixels[index] + 0.7152 * pixels[index + 1] + 0.0722 * pixels[index + 2])
    luminanceTotal += luminance
    bins[luminance] += 1
    if (luminance <= 12) blackPixels += 1
  }
  let entropy = 0
  for (const count of bins) {
    if (count === 0) continue
    const probability = count / pixelCount
    entropy -= probability * Math.log2(probability)
  }
  const averagePixel = luminanceTotal / pixelCount
  if (averagePixel <= 3 || blackPixels / pixelCount >= MAX_BLACK_PIXEL_RATIO || entropy < MIN_ENTROPY) {
    throw invalidFrame('black_frame_detected')
  }
}

async function seekTo(video: HTMLVideoElement, target: number): Promise<void> {
  if (Math.abs(video.currentTime - target) < 0.05) return
  await new Promise<void>((resolve, reject) => {
    const timeout = window.setTimeout(() => finish(new Error('The first movie frame did not finish decoding.')), 5000)
    const finish = (error?: Error) => {
      window.clearTimeout(timeout)
      video.removeEventListener('seeked', onSeeked)
      video.removeEventListener('error', onError)
      if (error) reject(error)
      else resolve()
    }
    const onSeeked = () => finish()
    const onError = () => finish(new Error('The movie could not decode the initial analysis frame.'))
    video.addEventListener('seeked', onSeeked, { once: true })
    video.addEventListener('error', onError, { once: true })
    video.currentTime = target
  })
}

/** Captures one compact still from the active player; it never observes playback continuously. */
export async function captureVideoFrame(video: HTMLVideoElement | null): Promise<CapturedVideoFrame> {
  if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || !video.videoWidth || !video.videoHeight) {
    throw new Error('The current movie frame is not ready yet.')
  }

  const scale = Math.min(1, MAX_DIMENSION / Math.max(video.videoWidth, video.videoHeight))
  const width = Math.max(1, Math.round(video.videoWidth * scale))
  const height = Math.max(1, Math.round(video.videoHeight * scale))
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height

  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) throw new Error('Frame capture is not available in this browser.')
  const originalTimestamp = video.currentTime
  const duration = Number.isFinite(video.duration) ? video.duration : 0
  const candidates = [...new Set([Math.max(MIN_ANALYSIS_TIMESTAMP_SECONDS, originalTimestamp), ...INITIAL_ANALYSIS_CANDIDATES])]
    .filter((timestamp) => timestamp >= MIN_ANALYSIS_TIMESTAMP_SECONDS && timestamp < duration - 0.1)
  let lastInvalidFrame: Error | null = null
  try {
    for (const timestamp of candidates) {
      await seekTo(video, timestamp)
      if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) continue
      try {
        context.drawImage(video, 0, 0, width, height)
        const frameBlob = await canvasToBlob(canvas)
        validateCanvasFrame(context, width, height, frameBlob.size)
        return { dataUrl: await blobToDataUrl(frameBlob), timestamp: video.currentTime, width, height }
      } catch (error) {
        if (error instanceof DOMException && error.name === 'SecurityError') {
          throw new Error('This movie source does not allow secure frame capture. Configure CORS for the movie host and try again.')
        }
        if (error instanceof Error && error.message.includes('"error":"invalid_frame"')) {
          lastInvalidFrame = error
          continue
        }
        throw error
      }
    }
    throw lastInvalidFrame ?? invalidFrame('first_real_frame_unavailable')
  } finally {
    // Preparation may inspect a later representative frame, but it must not
    // move the user's playback position.
    await seekTo(video, originalTimestamp)
  }
}

export type CapturedVideoFrame = {
  dataUrl: string
  timestamp: number
  width: number
  height: number
}

const MAX_DIMENSION = 768
const JPEG_QUALITY = 0.78

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

  const context = canvas.getContext('2d')
  if (!context) throw new Error('Frame capture is not available in this browser.')
  context.drawImage(video, 0, 0, width, height)

  const frameBlob = await canvasToBlob(canvas)

  return {
    dataUrl: await blobToDataUrl(frameBlob),
    timestamp: video.currentTime,
    width,
    height,
  }
}

export type CapturedVideoFrame = {
  dataUrl: string
  timestamp: number
  width: number
  height: number
}

const MAX_DIMENSION = 768
const JPEG_QUALITY = 0.78

/** Captures one compact still from the active player; it never observes playback continuously. */
export function captureVideoFrame(video: HTMLVideoElement | null): CapturedVideoFrame {
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

  return {
    dataUrl: canvas.toDataURL('image/jpeg', JPEG_QUALITY),
    timestamp: video.currentTime,
    width,
    height,
  }
}

import type { MovieId } from '../types/movie'

export type MovieAssetId = MovieId | 'insideOut' | 'findingNemo'

const CLOUDFLARE_R2_BASE = 'https://pub-26547a0f0f74415f9e77724b24edd8fe.r2.dev'

export type MovieAssetConfig = {
  id: MovieAssetId
  name: string
  videoUrl: string
  fileType: 'webm' | 'mov' | 'mp4'
  contentType: string
  subtitleSrc: string
  posterUrl: string
}

export const movieAssets: Record<MovieAssetId, MovieAssetConfig> = {
  bigBuckBunny: {
    id: 'bigBuckBunny',
    name: 'Big Buck Bunny',
    videoUrl: `${CLOUDFLARE_R2_BASE}/big-buck-bunny.mp4`,
    fileType: 'mp4',
    contentType: 'video/mp4',
    subtitleSrc: '/subtitles/big-buck-bunny.srt',
    posterUrl: '/posters/big-buck-bunny.jpg',
  },
  spriteFright: {
    id: 'spriteFright',
    name: 'Sprite Fright',
    videoUrl: `${CLOUDFLARE_R2_BASE}/sprite-fright.webm`,
    fileType: 'webm',
    contentType: 'video/webm',
    subtitleSrc: '/subtitles/sprite-fright.vtt',
    posterUrl: '/posters/sprite-fright.png',
  },
  insideOut: {
    id: 'insideOut',
    name: 'Inside Out (Demo)',
    videoUrl: `${CLOUDFLARE_R2_BASE}/inside-out-demo.mp4`,
    fileType: 'mp4',
    contentType: 'video/mp4',
    subtitleSrc: '',
    posterUrl:
      'https://images.unsplash.com/photo-1496497243327-9dccd845c35f?auto=format&fit=crop&w=1200&q=80',
  },
  findingNemo: {
    id: 'findingNemo',
    name: 'Finding Nemo (Demo)',
    videoUrl: `${CLOUDFLARE_R2_BASE}/finding-nemo-demo.mp4`,
    fileType: 'mp4',
    contentType: 'video/mp4',
    subtitleSrc: '',
    posterUrl:
      'https://images.unsplash.com/photo-1500375592092-40eb2168fd21?auto=format&fit=crop&w=1200&q=80',
  },
}

export function getMovieVideoUrl(id: MovieAssetId): string {
  return movieAssets[id].videoUrl
}

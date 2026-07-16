import type { MovieId } from '../types/movie'
import { getSupabasePublicUrl } from '../lib/supabaseClient'

export type MovieAssetId = MovieId | 'insideOut' | 'findingNemo'

export type MovieAssetConfig = {
  id: MovieAssetId
  name: string
  bucket: 'movies'
  objectPath: string
  fileType: 'webm' | 'mov' | 'mp4'
  contentType: string
  subtitleSrc: string
  posterUrl: string
}

export const movieAssets: Record<MovieAssetId, MovieAssetConfig> = {
  bigBuckBunny: {
    id: 'bigBuckBunny',
    name: 'Big Buck Bunny',
    bucket: 'movies',
    objectPath: 'big-buck-bunny.mov',
    fileType: 'mov',
    contentType: 'video/quicktime',
    subtitleSrc: '/subtitles/big-buck-bunny.srt',
    posterUrl: '/posters/big-buck-bunny.jpg',
  },
  spriteFright: {
    id: 'spriteFright',
    name: 'Sprite Fright',
    bucket: 'movies',
    objectPath: 'sprite-fright.webm',
    fileType: 'webm',
    contentType: 'video/webm',
    subtitleSrc: '/subtitles/sprite-fright.vtt',
    posterUrl: '/posters/sprite-fright.png',
  },
  insideOut: {
    id: 'insideOut',
    name: 'Inside Out (Demo)',
    bucket: 'movies',
    objectPath: 'inside-out-demo.mp4',
    fileType: 'mp4',
    contentType: 'video/mp4',
    subtitleSrc: '',
    posterUrl:
      'https://images.unsplash.com/photo-1496497243327-9dccd845c35f?auto=format&fit=crop&w=1200&q=80',
  },
  findingNemo: {
    id: 'findingNemo',
    name: 'Finding Nemo (Demo)',
    bucket: 'movies',
    objectPath: 'finding-nemo-demo.mp4',
    fileType: 'mp4',
    contentType: 'video/mp4',
    subtitleSrc: '',
    posterUrl:
      'https://images.unsplash.com/photo-1500375592092-40eb2168fd21?auto=format&fit=crop&w=1200&q=80',
  },
}

export function getMovieVideoUrl(id: MovieAssetId): string {
  const asset = movieAssets[id]
  return getSupabasePublicUrl(asset.bucket, asset.objectPath)
}

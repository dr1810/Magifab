import type { MovieData } from '../types/movie'

export const bigBuckBunnyData: MovieData = {
  id: 'bigBuckBunny',
  title: 'Big Buck Bunny',
  description: 'A gentle rabbit’s peaceful morning is interrupted by three mischievous squirrels, setting off a playful woodland adventure.',
  runtime: '9 min',
  genre: 'Comedy · Animation',
  rating: 'All ages',
  accessibilityTags: ['Simple Language Prompts', 'Keyboard Navigation', 'Reduced Motion Supported'],
  posterUrl: '/posters/big-buck-bunny.jpg',
  videoSrc: '/movies/big-buck-bunny.mov', subtitleSrc: '/subtitles/big-buck-bunny.srt',
  companionTheme: 'sun',
  scenes: [
    {
      sceneId: 'bbb-01', timestamp: 0, subtitle: 'Buck enjoys a quiet morning in the forest.',
      prompts: [
        { id: 'who', label: 'Who is this?', question: 'Who is Buck?', explanation: 'Buck is a kind rabbit who lives peacefully in the forest.' },
        { id: 'scene', label: 'Explain this scene', question: 'What is happening?', explanation: 'This opening shows Buck’s calm everyday life before the trouble begins.' },
        { id: 'emotion', label: 'What emotion is this?', question: 'How does Buck feel?', explanation: 'He feels relaxed and content because everything around him is safe.' },
      ],
      characterList: [{ id: 'buck', name: 'Buck', role: 'Main character', emotionalState: 'Peaceful' }],
      emotion: 'Calm and contentment', relationshipGraph: [],
      timelineData: [{ id: 'before', time: 'Before', label: 'A peaceful morning' }, { id: 'now', time: 'Now', label: 'Buck enjoys the forest' }, { id: 'next', time: 'Next', label: 'The squirrels arrive' }],
      causeEffectData: { cause: 'Buck wants a peaceful day', action: 'He enjoys the forest', effect: 'The contrast makes the prank feel surprising' },
      companionPosition: { x: 45, y: 52 }, highlightObject: { name: 'Carrot', reason: 'It represents Buck’s simple, peaceful routine.' }, voiceNarration: 'Buck begins the story in a calm, safe world.',
    },
    {
      sceneId: 'bbb-02', timestamp: 160, subtitle: 'The squirrels tease Buck and disrupt his peaceful day.',
      prompts: [
        { id: 'who', label: 'Who is this?', question: 'Who are the squirrels?', explanation: 'They are playful troublemakers who keep making Buck’s day difficult.' },
        { id: 'why', label: 'Why is this important?', question: 'Why does this matter?', explanation: 'Their teasing gives Buck a reason to stand up for himself.' },
        { id: 'simple', label: 'Explain simply', question: 'What changed?', explanation: 'Buck’s quiet day changed into a problem he needs to solve.' },
      ],
      characterList: [{ id: 'buck', name: 'Buck', role: 'Rabbit', emotionalState: 'Frustrated' }, { id: 'squirrels', name: 'Squirrels', role: 'Troublemakers', emotionalState: 'Mischievous' }],
      emotion: 'Frustration and surprise', relationshipGraph: [{ from: 'Squirrels', to: 'Buck', label: 'Teasing him' }],
      timelineData: [{ id: 'before', time: 'Before', label: 'Peaceful morning' }, { id: 'now', time: 'Now', label: 'The prank begins' }, { id: 'next', time: 'Next', label: 'Buck makes a plan' }],
      causeEffectData: { cause: 'The squirrels keep teasing Buck', action: 'Buck decides to respond', effect: 'He takes back control of the situation' },
      companionPosition: { x: 56, y: 46 }, highlightObject: { name: 'Fallen fruit', reason: 'It shows the small disruptions caused by the prank.' }, voiceNarration: 'Buck is upset, but he is beginning to decide how to respond.',
    },
    {
      sceneId: 'bbb-03', timestamp: 340, subtitle: 'Buck uses clever ideas to bring the prank to an end.',
      prompts: [
        { id: 'scene', label: 'Explain this scene', question: 'What is Buck doing?', explanation: 'Buck uses clever, harmless plans to show the squirrels how their behavior felt.' },
        { id: 'emotion', label: 'What emotion is this?', question: 'How does Buck feel now?', explanation: 'He feels confident because he is solving the problem without being cruel.' },
        { id: 'before', label: 'What happened before?', question: 'Why did Buck make this plan?', explanation: 'The squirrels kept disturbing him, so Buck chose a smart way to set a boundary.' },
      ],
      characterList: [{ id: 'buck', name: 'Buck', role: 'Problem solver', emotionalState: 'Confident' }],
      emotion: 'Confidence and relief', relationshipGraph: [{ from: 'Buck', to: 'Squirrels', label: 'Sets a clear boundary' }],
      timelineData: [{ id: 'before', time: 'Before', label: 'Repeated pranks' }, { id: 'now', time: 'Now', label: 'Buck acts cleverly' }, { id: 'next', time: 'Next', label: 'Peace returns' }],
      causeEffectData: { cause: 'Buck has had enough teasing', action: 'He creates a clever response', effect: 'The conflict ends and calm returns' },
      companionPosition: { x: 51, y: 49 }, highlightObject: { name: 'Forest clearing', reason: 'It becomes the place where Buck regains control.' }, voiceNarration: 'Buck solves the conflict with confidence and without losing his kindness.',
    },
  ],
}

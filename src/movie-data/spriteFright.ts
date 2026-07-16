import type { MovieData } from '../types/movie'

export const spriteFrightData: MovieData = {
  id: 'spriteFright', title: 'Sprite Fright',
  description: 'A young sprite explores a moonlit forest where a mischievous spell turns a quiet night into a surprising adventure.',
  runtime: '11 min', genre: 'Fantasy · Animation', rating: 'All ages',
  accessibilityTags: ['Simple Language Prompts', 'Keyboard Navigation', 'Reduced Motion Supported'], posterUrl: '/posters/sprite-fright.png', videoSrc: '/movies/sprite-fright.webm', subtitleSrc: '/subtitles/sprite-fright.vtt', companionTheme: 'ocean',
  scenes: [
    {
      sceneId: 'sf-01', timestamp: 0, subtitle: 'The sprite follows a glowing trail through the forest.',
      prompts: [{ id: 'who', label: 'Who is this?', question: 'Who is the sprite?', explanation: 'The sprite is a curious forest helper who wants to understand the strange glow.' }, { id: 'scene', label: 'Explain this scene', question: 'What is happening?', explanation: 'The sprite is following a clue through a magical forest.' }, { id: 'object', label: 'What is that?', question: 'Why does the glow matter?', explanation: 'The glow is a clue that leads the sprite toward the next important moment.' }],
      characterList: [{ id: 'sprite', name: 'The sprite', role: 'Explorer', emotionalState: 'Curious' }], emotion: 'Wonder and curiosity', relationshipGraph: [],
      timelineData: [{ id: 'before', time: 'Before', label: 'A quiet forest night' }, { id: 'now', time: 'Now', label: 'A glowing clue appears' }, { id: 'next', time: 'Next', label: 'The mystery grows' }], causeEffectData: { cause: 'A strange glow appears', action: 'The sprite follows it', effect: 'A hidden forest mystery is revealed' }, companionPosition: { x: 47, y: 45 }, highlightObject: { name: 'Glowing trail', reason: 'It guides the sprite to the mystery.' }, voiceNarration: 'The sprite is curious, not in danger. The glow is a clue.',
    },
    {
      sceneId: 'sf-02', timestamp: 180, subtitle: 'A spell makes the forest creatures behave in surprising ways.',
      prompts: [{ id: 'why', label: 'Why is this important?', question: 'Why are things changing?', explanation: 'A mischievous spell is affecting the forest, which is why everything suddenly seems unusual.' }, { id: 'emotion', label: 'What emotion is this?', question: 'How does the sprite feel?', explanation: 'The sprite is startled but stays curious and keeps looking for answers.' }, { id: 'simple', label: 'Explain simply', question: 'What is the problem?', explanation: 'The forest is mixed up because of magic, and the sprite wants to fix it.' }],
      characterList: [{ id: 'sprite', name: 'The sprite', role: 'Helper', emotionalState: 'Concerned' }, { id: 'forest', name: 'Forest creatures', role: 'Affected by magic', emotionalState: 'Confused' }], emotion: 'Surprise and concern', relationshipGraph: [{ from: 'Spell', to: 'Forest creatures', label: 'Causes confusion' }],
      timelineData: [{ id: 'before', time: 'Before', label: 'Following the glow' }, { id: 'now', time: 'Now', label: 'The spell causes chaos' }, { id: 'next', time: 'Next', label: 'The sprite looks for the source' }], causeEffectData: { cause: 'A spell spreads through the forest', action: 'Creatures act strangely', effect: 'The sprite needs to find the source' }, companionPosition: { x: 59, y: 51 }, highlightObject: { name: 'Sparkling mist', reason: 'It shows where the spell has spread.' }, voiceNarration: 'The magic is making the forest confused, not permanently harmed.',
    },
    {
      sceneId: 'sf-03', timestamp: 390, subtitle: 'The sprite understands the spell and helps bring the forest back to normal.',
      prompts: [{ id: 'scene', label: 'Explain this scene', question: 'How is the problem solved?', explanation: 'The sprite understands what caused the spell and uses that knowledge to help the forest settle down.' }, { id: 'before', label: 'What happened before?', question: 'Why can the sprite help now?', explanation: 'Following the clues helped the sprite learn where the magic came from.' }, { id: 'emotion', label: 'What emotion is this?', question: 'How does the ending feel?', explanation: 'It feels relieved and hopeful because the forest is safe again.' }],
      characterList: [{ id: 'sprite', name: 'The sprite', role: 'Problem solver', emotionalState: 'Relieved' }], emotion: 'Relief and hope', relationshipGraph: [{ from: 'Sprite', to: 'Forest', label: 'Restores balance' }],
      timelineData: [{ id: 'before', time: 'Before', label: 'Forest confusion' }, { id: 'now', time: 'Now', label: 'The sprite understands the spell' }, { id: 'next', time: 'Next', label: 'The forest becomes calm again' }], causeEffectData: { cause: 'The sprite follows the magical clues', action: 'The spell is understood', effect: 'The forest returns to balance' }, companionPosition: { x: 49, y: 46 }, highlightObject: { name: 'Moonlit clearing', reason: 'It is where the mystery becomes clear.' }, voiceNarration: 'Understanding the cause helps the sprite make the forest feel safe again.',
    },
  ],
}

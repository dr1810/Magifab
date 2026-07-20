import type { MovieData } from '../types/movie'
import { getMovieVideoUrl, movieAssets } from '../config/movies'

export const spriteFrightData: MovieData = {
  id: 'spriteFright', title: 'Sprite Fright',
  description: 'A group of teenagers hiking through the woods clash over Ellie’s love of nature before they encounter the forest sprites.',
  runtime: '11 min', genre: 'Fantasy · Animation', rating: 'All ages',
  accessibilityTags: ['Simple Language Prompts', 'Keyboard Navigation', 'Reduced Motion Supported'], posterUrl: movieAssets.spriteFright.posterUrl, videoSrc: getMovieVideoUrl('spriteFright'), subtitleSrc: movieAssets.spriteFright.subtitleSrc, companionTheme: 'ocean',
  canonicalCharacters: [
    { id: 'ellie', name: 'Ellie', description: 'Nature lover', personality: 'Curious and observant', goals: ['Study the forest'], relationships: ['Rex and Victoria are impatient with her detours'], firstAppearance: 0, importantInformation: ['She uses Latin names for animals.'], visualDescription: 'Teen girl with blue hair ties and nature equipment', confidenceThreshold: 0.7 },
    { id: 'rex', name: 'Rex', description: 'Aggressive jock', personality: 'Impatient', goals: ['Keep the group moving'], relationships: ['Annoyed with Ellie'], firstAppearance: 0, importantInformation: ['He carries a bat.'], visualDescription: 'Blonde hair, blue vest, carries a bat', confidenceThreshold: 0.7 },
    { id: 'victoria', name: 'Victoria', description: 'Teenager', personality: 'Supports Rex', goals: ['Finish the trip'], relationships: ['Travels with Rex and Ellie'], firstAppearance: 0, importantInformation: ['She is part of the hiking group.'], visualDescription: 'Pink hair and sunglasses', confidenceThreshold: 0.7 },
    { id: 'sprites', name: 'Sprites', description: 'Forest creatures', personality: 'Protective of their forest', goals: ['Protect the forest'], relationships: ['React to the teenagers entering their home'], firstAppearance: 135, importantInformation: ['They do not appear in the opening conversation.'], visualDescription: 'Small mushroom-like forest creatures', confidenceThreshold: 0.75 },
  ],
  scenes: [
    {
      sceneId: 'sf-01', timestamp: 0, subtitle: 'Rex complains to Victoria about Ellie stopping to study animals.',
      prompts: [
        { id: 'emotion', label: 'Feelings', question: 'Why is Rex upset with Ellie?', explanation: 'Rex is frustrated because Ellie keeps stopping to study animals while he wants the group to continue.' },
        { id: 'scene', label: 'Explain this scene', question: 'What is happening?', explanation: 'Rex and Victoria are discussing Ellie because her interest in nature is slowing their trip.' },
        { id: 'relationship', label: 'Relationships', question: 'Why are Rex and Ellie arguing?', explanation: 'Rex and Ellie have different priorities: Rex wants to move on, while Ellie wants to pay attention to nature.' },
      ],
      characterList: [{ id: 'rex', name: 'Rex', role: 'Aggressive jock', emotionalState: 'Frustrated and impatient' }, { id: 'victoria', name: 'Victoria', role: 'Teenager', emotionalState: 'Supporting Rex' }, { id: 'ellie', name: 'Ellie', role: 'Nature lover', emotionalState: 'Not visible' }],
      visibleCharacterIds: ['rex', 'victoria'], missingCharacterIds: ['ellie', 'sprites'], entityConfidence: { rex: 0.92, victoria: 0.88, ellie: 0, sprites: 0 }, entityEvidence: { rex: ['blue vest and bat are visible'], victoria: ['pink hair and sunglasses are visible'], ellie: ['mentioned in dialogue only'], sprites: ['not present before 02:15'] },
      promptSubjects: { emotion: ['rex'], scene: ['rex', 'victoria'], relationship: ['rex'] },
      dialogueReferences: [{ speakerEntityId: 'rex', targetEntityIds: ['ellie'], pronouns: [{ pronoun: 'her', resolvedEntityId: 'ellie', evidence: 'Ellie is the established subject of the complaint and is known for naming animals.' }] }],
      emotion: 'Frustration and impatience', relationshipGraph: [{ from: 'Rex', to: 'Ellie', label: 'Annoyed because they have different priorities' }],
      timelineData: [{ id: 'before', time: 'Before', label: 'Ellie studies the forest' }, { id: 'now', time: 'Now', label: 'Rex and Victoria complain about the delay' }, { id: 'next', time: 'Next', label: 'The group goes deeper into the forest' }],
      causeEffectData: { cause: 'Ellie keeps stopping to study animals', action: 'Rex complains to Victoria', effect: 'The group’s conflict becomes clear' }, companionPosition: { x: 47, y: 45 }, highlightObject: { name: 'Rex’s bat', reason: 'It helps identify Rex in this scene.' }, visibleObjects: ['Rex’s bat'], voiceNarration: 'Rex and Victoria are discussing Ellie because her interest in nature is slowing their trip.',
    },
    {
      sceneId: 'sf-02', timestamp: 135, subtitle: 'The group enters the sprites’ part of the forest and the creatures finally appear.',
      prompts: [{ id: 'scene', label: 'Explain this scene', question: 'Who are the sprites?', explanation: 'The sprites are small forest creatures who live here and react to the teenagers entering their home.' }, { id: 'emotion', label: 'Feelings', question: 'Why are the sprites cautious?', explanation: 'The sprites are cautious because unfamiliar people have entered the forest they protect.' }],
      characterList: [{ id: 'sprites', name: 'Sprites', role: 'Forest creatures', emotionalState: 'Cautious' }], visibleCharacterIds: ['sprites'], missingCharacterIds: ['ellie', 'rex', 'victoria'], entityConfidence: { sprites: 0.9, ellie: 0, rex: 0, victoria: 0 }, entityEvidence: { sprites: ['small mushroom-like creatures are visible'], ellie: ['not in frame'], rex: ['not in frame'], victoria: ['not in frame'] }, promptSubjects: { scene: ['sprites'], emotion: ['sprites'] },
      emotion: 'Caution', relationshipGraph: [{ from: 'Sprites', to: 'Teenagers', label: 'Protect their forest home' }], timelineData: [{ id: 'before', time: 'Before', label: 'The teenagers argue' }, { id: 'now', time: 'Now', label: 'Sprites appear' }, { id: 'next', time: 'Next', label: 'The forest reacts' }], causeEffectData: { cause: 'The teenagers enter the sprites’ home', action: 'The sprites notice them', effect: 'The forest conflict begins' }, companionPosition: { x: 59, y: 51 }, highlightObject: { name: 'Mushroom shelter', reason: 'It shows the sprites’ forest home.' }, visibleObjects: ['Mushroom shelter'], voiceNarration: 'The sprites appear only now, after the teenagers have entered their part of the forest.',
    },
    {
      sceneId: 'sf-03', timestamp: 390, subtitle: 'The conflict in the forest reaches its resolution.',
      prompts: [{ id: 'scene', label: 'Explain this scene', question: 'How is the problem solved?', explanation: 'The conflict settles once the characters understand why the forest and its creatures reacted to the group.' }, { id: 'before', label: 'Remember', question: 'What caused this?', explanation: 'The trouble began when the group ignored the forest and the sprites’ home.' }],
      characterList: [{ id: 'sprites', name: 'Sprites', role: 'Forest creatures', emotionalState: 'Relieved' }], visibleCharacterIds: ['sprites'], entityConfidence: { sprites: 0.85 }, entityEvidence: { sprites: ['sprites are visible during the resolution'] }, promptSubjects: { scene: ['sprites'], before: ['sprites'] },
      emotion: 'Relief', relationshipGraph: [{ from: 'Sprites', to: 'Teenagers', label: 'The conflict has settled' }], timelineData: [{ id: 'before', time: 'Before', label: 'The forest conflict' }, { id: 'now', time: 'Now', label: 'The conflict settles' }, { id: 'next', time: 'Next', label: 'The forest is safe again' }], causeEffectData: { cause: 'The group understands the forest’s boundaries', action: 'The conflict is resolved', effect: 'The forest becomes calm again' }, companionPosition: { x: 49, y: 46 }, highlightObject: { name: 'Forest clearing', reason: 'It marks the resolution.' }, visibleObjects: ['Forest clearing'], voiceNarration: 'The conflict settles after the group understands why the forest reacted.',
    },
  ],
}

import assert from 'node:assert/strict'
import { createLogger, createServer } from 'vite'

const logger = createLogger('error', { allowClearScreen: false })
logger.error = () => undefined
const server = await createServer({ customLogger: logger, server: { middlewareMode: true, hmr: false }, appType: 'custom' })

try {
  const { StoryResolver } = await server.ssrLoadModule('/src/services/narrative/StoryResolver.ts')
  const { getMovieNarrativeGraph } = await server.ssrLoadModule('/src/services/narrative/NarrativeRepository.ts')
  const { StoryContextObserver } = await server.ssrLoadModule('/src/services/narrative/StoryContextObserver.ts')
  const { isPromptValid, resolvePromptRequest } = await server.ssrLoadModule('/src/services/narrative/usePromptLifecycle.ts')
  const graph = getMovieNarrativeGraph('spriteFright')
  assert.ok(graph, 'Sprite Fright graph must be available')
  const resolver = new StoryResolver(graph)

  const intro = resolver.resolveTime(6, null)
  assert.equal(intro?.phase, 'intro_credits')
  assert.equal(intro?.sceneSummary, 'Opening credits')
  assert.equal(intro?.companionEnabled, false)
  assert.equal(intro?.promptBubbles.length, 0)

  const conversation = resolver.resolveTime(28, null)
  assert.equal(conversation?.phase, 'setup')
  assert.deepEqual(conversation?.characters.map((character) => character.name), ['Rex', 'Victoria'])
  assert.ok(conversation?.promptBubbles.some((prompt) => prompt.question === 'Why is Rex annoyed with Ellie?'))

  const observing = resolver.resolveTime(238, null)
  const attack = resolver.resolveTime(260, null)
  assert.equal(observing?.sceneId, 'sf:sprites-observing')
  assert.equal(attack?.sceneId, 'sf:first-attack')

  const observer = new StoryContextObserver()
  const observingContext = observer.observe(observing, 238)
  const attackContext = observer.observe(attack, 260)
  assert.ok(attackContext.contextVersion > observingContext.contextVersion)
  assert.equal(isPromptValid({ id: 'stale', question: 'Old prompt', explanation: '', lifecycle: 'completed', contextVersion: observingContext.contextVersion, storyBeatId: observingContext.storyBeatId ?? '', timestampCreated: 238, validFrom: observingContext.validFrom, validUntil: observingContext.validUntil }, attackContext), false)

  const timeoutResult = await resolvePromptRequest(
    () => new Promise(() => undefined),
    new AbortController(),
    'Cached explanation is unavailable right now.',
    10,
  )
  assert.deepEqual(timeoutResult, { lifecycle: 'fallback', explanation: 'Cached explanation is unavailable right now.' })

  const climax = resolver.resolveTime(452, null)
  assert.equal(climax?.phase, 'climax')
  assert.ok(climax?.emotions.some((emotion) => emotion.summary.includes('Ellie is frightened')))
  assert.ok(climax?.emotions.some((emotion) => emotion.summary.includes('sprites are angry')))
  assert.ok(climax?.promptBubbles.some((prompt) => prompt.question === 'How did the conflict become so dangerous?'))

  const resolution = resolver.resolveTime(485, null)
  assert.equal(resolution?.phase, 'resolution')
  assert.equal(resolution?.sceneSummary, 'The forest is calm again and the conflict is over.')
  console.log('Story beat acceptance checks passed.')
} finally {
  await server.close()
}

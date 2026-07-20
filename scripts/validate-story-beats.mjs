import assert from 'node:assert/strict'
import { createLogger, createServer } from 'vite'

const logger = createLogger('error', { allowClearScreen: false })
logger.error = () => undefined
const server = await createServer({ customLogger: logger, server: { middlewareMode: true, hmr: false }, appType: 'custom' })

try {
  const { StoryResolver } = await server.ssrLoadModule('/src/services/narrative/StoryResolver.ts')
  const { getMovieNarrativeGraph } = await server.ssrLoadModule('/src/services/narrative/NarrativeRepository.ts')
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

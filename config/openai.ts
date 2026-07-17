/**
 * Server-only OpenAI configuration for MagiFab's API gateway.
 *
 * TODO: Add these two values to the server environment once billing is enabled:
 * OPENAI_API_KEY=
 * MODEL_NAME=
 *
 * Do not import this file into browser code. It intentionally reads non-public
 * environment variables so the API key cannot be bundled by Vite.
 */
export type ServerOpenAIConfig = {
  apiKey: string
  modelName: string
}

/** Reads the exact server environment variables used by both GPT pipeline stages. */
export function readOpenAIConfig(environment: Record<string, string | undefined>): ServerOpenAIConfig {
  return {
    apiKey: environment.OPENAI_API_KEY ?? '',
    modelName: environment.MODEL_NAME ?? '',
  }
}

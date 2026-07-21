/**
 * OpenAI integration settings.
 *
 * TODO: Set `OPENAI_API_KEY` only in the server environment. Never expose it as
 *       a Vite `VITE_*` variable or call OpenAI directly from this browser app.
 */
export const openAIConfig = {
  apiBaseUrl: import.meta.env.VITE_MAGIFAB_BACKEND_URL ?? '',
} as const

/** Returns whether a server-side AI gateway has been configured. */
export function isAiGatewayConfigured(): boolean {
  return Boolean(openAIConfig.apiBaseUrl)
}

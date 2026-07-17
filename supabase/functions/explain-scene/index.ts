import "@supabase/functions-js/edge-runtime.d.ts";
import { withSupabase } from "@supabase/server";

type ExplainSceneRequest = {
  question: string;
  scene: string;
  companion: {
    personality: string;
    conversationStyle: string;
    detailLevel: string;
  };
};

type ExplainSceneResponse = {
  explanation: string;
  emotion: string;
  character: string;
};

const corsHeaders = {
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Origin": "*",
};

const responseSchema = {
  type: "object",
  additionalProperties: false,
  required: ["explanation", "emotion", "character"],
  properties: {
    explanation: { type: "string", description: "A short, accessible explanation in plain language." },
    emotion: { type: "string", description: "The character's clearest current emotion." },
    character: { type: "string", description: "The character's name, or a clear descriptive name if unknown." },
  },
};

function json(body: unknown, status = 200) {
  return Response.json(body, { status, headers: corsHeaders });
}

function readText(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return text && text.length <= 2_000 ? text : null;
}

function validateRequest(value: unknown): ExplainSceneRequest | null {
  if (!value || typeof value !== "object") return null;
  const request = value as Record<string, unknown>;
  const companion = request.companion;
  if (!companion || typeof companion !== "object") return null;

  const question = readText(request.question);
  const scene = readText(request.scene);
  const companionValue = companion as Record<string, unknown>;
  const personality = readText(companionValue.personality);
  const conversationStyle = readText(companionValue.conversationStyle);
  const detailLevel = readText(companionValue.detailLevel);

  if (!question || !scene || !personality || !conversationStyle || !detailLevel) return null;
  return { question, scene, companion: { personality, conversationStyle, detailLevel } };
}

function isExplainSceneResponse(value: unknown): value is ExplainSceneResponse {
  if (!value || typeof value !== "object") return false;
  const response = value as Record<string, unknown>;
  return [response.explanation, response.emotion, response.character]
    .every((item) => typeof item === "string" && item.trim().length > 0);
}

export default {
  fetch: withSupabase({ auth: ["publishable", "secret"] }, async (req) => {
    if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
    if (req.method !== "POST") return json({ error: "Method not allowed." }, 405);

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return json({ error: "Request body must be valid JSON." }, 400);
    }

    const input = validateRequest(body);
    if (!input) return json({ error: "question, scene, and companion preferences are required." }, 400);

    const apiKey = Deno.env.get("OPENAI_API_KEY");
    const model = Deno.env.get("OPENAI_MODEL");
    if (!apiKey || !model) {
      console.error("Missing OPENAI_API_KEY or OPENAI_MODEL Supabase secret.");
      return json({ error: "AI service is not configured." }, 503);
    }

    const instructions = [
      "You are MagiFab, an accessibility companion for someone watching a movie.",
      "Answer the question using only the supplied scene context. Do not invent plot details or identities.",
      "Use simple, clear, respectful language. Avoid jargon and unnecessary complexity.",
      `Match this companion personality: ${input.companion.personality}.`,
      `Use this conversation style: ${input.companion.conversationStyle}.`,
      `Use this detail level: ${input.companion.detailLevel}.`,
      "Keep the explanation concise enough to read in an on-screen bubble.",
    ].join(" ");

    const openAIResponse = await fetch("https://api.openai.com/v1/responses", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        instructions,
        input: JSON.stringify({ question: input.question, scene: input.scene }),
        max_output_tokens: 300,
        text: {
          format: {
            type: "json_schema",
            name: "scene_explanation",
            strict: true,
            schema: responseSchema,
          },
        },
      }),
    });

    if (!openAIResponse.ok) {
      console.error("OpenAI request failed", openAIResponse.status, await openAIResponse.text());
      return json({ error: "Unable to create an explanation right now." }, 502);
    }

    const completion = await openAIResponse.json() as { output_text?: unknown };
    if (typeof completion.output_text !== "string") {
      console.error("OpenAI response did not contain output_text.");
      return json({ error: "AI returned an invalid response." }, 502);
    }

    try {
      const output = JSON.parse(completion.output_text) as unknown;
      if (!isExplainSceneResponse(output)) throw new Error("Schema validation failed");
      return json({
        explanation: output.explanation.trim(),
        emotion: output.emotion.trim(),
        character: output.character.trim(),
      });
    } catch (error) {
      console.error("Could not parse structured OpenAI response", error);
      return json({ error: "AI returned an invalid response." }, 502);
    }
  }),
};

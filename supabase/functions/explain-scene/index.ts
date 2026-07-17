import "@supabase/functions-js/edge-runtime.d.ts";

type Anchor = { x: number; y: number; width: number; height: number };

type ExplainSceneRequest = {
  mode?: "legacy_vision";
  question: string;
  scene: string;
  timestamp: number;
  frame: { dataUrl: string; width: number; height: number };
  companion: { personality: string; conversationStyle: string; detailLevel: string };
};

type PersonalizeRequest = {
  mode: "personalize";
  question: string;
  semanticContext: Record<string, unknown>;
  companion: { personality: string; conversationStyle: string; detailLevel: string };
};

type PersonalizeResponse = { explanation: string; emotion: string };

type ExplainSceneResponse = {
  explanation: string;
  emotion: string;
  character: string | null;
  characterFound: boolean;
  confidence: number;
  anchor: Anchor;
  visualAidType: "magnifier" | "highlight";
};

type OpenAIResponsePayload = { id?: unknown; status?: unknown; output_text?: unknown; output?: unknown; error?: unknown };

const MAX_FRAME_DATA_URL_LENGTH = 3_000_000;
const corsHeaders = {
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Origin": "*",
};

const responseSchema = {
  type: "object",
  additionalProperties: false,
  required: ["explanation", "emotion", "character", "characterFound", "confidence", "anchor", "visualAidType"],
  properties: {
    explanation: { type: "string", description: "A concise, accessible explanation in plain language." },
    emotion: { type: "string", description: "The character's clearest current emotion." },
    character: { type: ["string", "null"], description: "The identified character's name. Use null when no person is visible or identity cannot be determined." },
    characterFound: { type: "boolean", description: "True only when a visible person can be identified from the movie frame with confidence." },
    confidence: { type: "number", minimum: 0, maximum: 1 },
    anchor: {
      type: "object",
      additionalProperties: false,
      required: ["x", "y", "width", "height"],
      properties: {
        x: { type: "number", minimum: 0, maximum: 100, description: "Character center x as a percentage of the image width." },
        y: { type: "number", minimum: 0, maximum: 100, description: "Character center y as a percentage of the image height." },
        width: { type: "number", minimum: 1, maximum: 100, description: "Character bounding-box width as a percentage of image width." },
        height: { type: "number", minimum: 1, maximum: 100, description: "Character bounding-box height as a percentage of image height." },
      },
    },
    visualAidType: { type: "string", enum: ["magnifier", "highlight"] },
  },
};

const personalizeResponseSchema = {
  type: "object", additionalProperties: false, required: ["explanation", "emotion"],
  properties: {
    explanation: { type: "string", description: "A concise, accessible explanation based only on supplied facts." },
    emotion: { type: "string", description: "The supported emotion, or neutral when none is supplied." },
  },
};

function json(body: unknown, status = 200) {
  return Response.json(body, { status, headers: corsHeaders });
}

function readText(value: unknown, limit = 2_000): string | null {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return text && text.length <= limit ? text : null;
}

function readAnchor(value: unknown): Anchor | null {
  if (!value || typeof value !== "object") return null;
  const anchor = value as Record<string, unknown>;
  const values = [anchor.x, anchor.y, anchor.width, anchor.height];
  if (!values.every((item) => typeof item === "number" && Number.isFinite(item))) return null;
  const [x, y, width, height] = values as number[];
  if (x < 0 || x > 100 || y < 0 || y > 100 || width <= 0 || width > 100 || height <= 0 || height > 100) return null;
  return { x, y, width, height };
}

function validateRequest(value: unknown): ExplainSceneRequest | null {
  if (!value || typeof value !== "object") return null;
  const request = value as Record<string, unknown>;
  const companion = request.companion;
  const frame = request.frame;
  if (!companion || typeof companion !== "object" || !frame || typeof frame !== "object") return null;

  const companionValue = companion as Record<string, unknown>;
  const frameValue = frame as Record<string, unknown>;
  const question = readText(request.question);
  const scene = readText(request.scene);
  const personality = readText(companionValue.personality);
  const conversationStyle = readText(companionValue.conversationStyle);
  const detailLevel = readText(companionValue.detailLevel);
  const dataUrl = readText(frameValue.dataUrl, MAX_FRAME_DATA_URL_LENGTH);
  const timestamp = request.timestamp;
  const width = frameValue.width;
  const height = frameValue.height;

  if (!question || !scene || !personality || !conversationStyle || !detailLevel
    || !dataUrl?.startsWith("data:image/") || typeof timestamp !== "number" || !Number.isFinite(timestamp)
    || typeof width !== "number" || typeof height !== "number" || width <= 0 || height <= 0) return null;

  return {
    question,
    scene,
    timestamp,
    frame: { dataUrl, width, height },
    companion: { personality, conversationStyle, detailLevel },
  };
}

function validatePersonalizeRequest(value: unknown): PersonalizeRequest | null {
  if (!value || typeof value !== "object") return null;
  const request = value as Record<string, unknown>;
  if (request.mode !== "personalize" || !request.companion || typeof request.companion !== "object" || !request.semanticContext || typeof request.semanticContext !== "object") return null;
  const companion = request.companion as Record<string, unknown>;
  const question = readText(request.question);
  const personality = readText(companion.personality);
  const conversationStyle = readText(companion.conversationStyle);
  const detailLevel = readText(companion.detailLevel);
  if (!question || !personality || !conversationStyle || !detailLevel) return null;
  return { mode: "personalize", question, semanticContext: request.semanticContext as Record<string, unknown>, companion: { personality, conversationStyle, detailLevel } };
}

function isExplainSceneResponse(value: unknown): value is ExplainSceneResponse {
  if (!value || typeof value !== "object") return false;
  const response = value as Record<string, unknown>;
  return typeof response.explanation === "string" && response.explanation.trim().length > 0
    && typeof response.emotion === "string" && response.emotion.trim().length > 0
    && typeof response.characterFound === "boolean"
    && typeof response.confidence === "number" && Number.isFinite(response.confidence)
    && (response.characterFound ? typeof response.character === "string" && response.character.trim().length > 0 : response.character === null)
    && readAnchor(response.anchor) !== null
    && (response.visualAidType === "magnifier" || response.visualAidType === "highlight");
}

function isPersonalizeResponse(value: unknown): value is PersonalizeResponse {
  if (!value || typeof value !== "object") return false;
  const response = value as Record<string, unknown>;
  return typeof response.explanation === "string" && response.explanation.trim().length > 0 && typeof response.emotion === "string" && response.emotion.trim().length > 0;
}

function extractOutputText(completion: OpenAIResponsePayload): string | null {
  if (typeof completion.output_text === "string") return completion.output_text;
  if (!Array.isArray(completion.output)) return null;
  for (const outputItem of completion.output) {
    if (!outputItem || typeof outputItem !== "object") continue;
    const content = (outputItem as Record<string, unknown>).content;
    if (!Array.isArray(content)) continue;
    for (const contentItem of content) {
      if (!contentItem || typeof contentItem !== "object") continue;
      const item = contentItem as Record<string, unknown>;
      if (item.type === "output_text" && typeof item.text === "string") return item.text;
    }
  }
  return null;
}

function outputSummary(completion: OpenAIResponsePayload) {
  if (!Array.isArray(completion.output)) return [];
  return completion.output.map((item) => {
    if (!item || typeof item !== "object") return "invalid";
    const record = item as Record<string, unknown>;
    const content = Array.isArray(record.content) ? record.content : [];
    return `${String(record.type ?? "unknown")}[${content.map((entry) => entry && typeof entry === "object" ? String((entry as Record<string, unknown>).type ?? "unknown") : "invalid").join(",")}]`;
  });
}

Deno.serve(async (req) => {
  const requestId = crypto.randomUUID();
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return json({ error: "Method not allowed." }, 405);

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return json({ error: "Request body must be valid JSON." }, 400);
  }

  const personalizeInput = validatePersonalizeRequest(body);
  // Visual detection is intentionally not an OpenAI responsibility anymore.
  // Hugging Face adapters supply verified semantic facts before this endpoint is called.
  if (!personalizeInput) return json({ error: "A valid semantic personalization request is required." }, 400);
  const input: ExplainSceneRequest | null = null;

  const apiKey = Deno.env.get("OPENAI_API_KEY");
  const model = Deno.env.get("OPENAI_MODEL")?.trim();
  if (!apiKey || !model) {
    console.error("[explain-scene] Missing OpenAI configuration", { requestId, hasApiKey: Boolean(apiKey), hasModel: Boolean(model) });
    return json({ error: "AI service is not configured." }, 503);
  }

  const instructions = personalizeInput ? [
    "You are MagiFab, an accessibility companion for someone watching a movie.",
    "Use only the structured semantic facts supplied by the user. Do not perform visual detection, identify a new character, or invent facts.",
    "Use simple, clear, respectful language and keep the explanation concise enough for an on-screen bubble.",
    `Match this companion personality: ${personalizeInput.companion.personality}.`,
    `Use this conversation style: ${personalizeInput.companion.conversationStyle}.`,
    `Use this detail level: ${personalizeInput.companion.detailLevel}.`,
  ].join(" ") : [
    "You are MagiFab, an accessibility companion for someone watching a movie.",
    "Identify every visible person conceptually, but return the single person most relevant to the question only when identity is supported by the image and supplied movie context. Do not invent identities or plot details.",
    "If there is no visible person, the person is only background/too small, or identity cannot be determined confidently, set characterFound to false and character to null. Never guess a main character.",
    "Use simple, clear, respectful language and keep the explanation concise enough for an on-screen bubble.",
    "Return the character's visible bounding box as percentages of the image: x and y are the box center; width and height are its dimensions.",
    "Prefer visualAidType magnifier for a person, and highlight only when a magnifier would not be useful.",
    `Match this companion personality: ${input!.companion.personality}.`,
    `Use this conversation style: ${input!.companion.conversationStyle}.`,
    `Use this detail level: ${input!.companion.detailLevel}.`,
  ].join(" ");

  let openAIResponse: Response;
  try {
    openAIResponse = await fetch("https://api.openai.com/v1/responses", {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        instructions,
        input: personalizeInput ? [{ role: "user", content: [{ type: "input_text", text: JSON.stringify({ question: personalizeInput.question, semanticContext: personalizeInput.semanticContext }) }] }] : [{
          role: "user", content: [
            { type: "input_text", text: JSON.stringify({ question: input!.question, scene: input!.scene, timestamp: input!.timestamp, frameSize: `${input!.frame.width}x${input!.frame.height}` }) },
            { type: "input_image", image_url: input!.frame.dataUrl, detail: "low" },
          ],
        }],
        max_output_tokens: 400,
        text: { format: { type: "json_schema", name: personalizeInput ? "personalized_scene_explanation" : "grounded_scene_explanation", strict: true, schema: personalizeInput ? personalizeResponseSchema : responseSchema } },
      }),
    });
  } catch (error) {
    console.error("[explain-scene] OpenAI network request failed", { requestId, model, error: String(error) });
    return json({ error: "Unable to create an explanation right now." }, 502);
  }

  const rawOpenAIResponse = await openAIResponse.text();
  if (!openAIResponse.ok) {
    console.error("[explain-scene] OpenAI request failed", { requestId, model, status: openAIResponse.status, statusText: openAIResponse.statusText, response: rawOpenAIResponse.slice(0, 2_000) });
    return json({ error: "Unable to create an explanation right now." }, 502);
  }

  let completion: OpenAIResponsePayload;
  try {
    completion = JSON.parse(rawOpenAIResponse) as OpenAIResponsePayload;
  } catch (error) {
    console.error("[explain-scene] OpenAI response was not JSON", { requestId, model, error: String(error), response: rawOpenAIResponse.slice(0, 2_000) });
    return json({ error: "AI returned an invalid response." }, 502);
  }

  const outputText = extractOutputText(completion);
  if (!outputText) {
    console.error("[explain-scene] OpenAI response contained no output text", { requestId, model, openAIResponseId: completion.id, status: completion.status, output: outputSummary(completion), error: completion.error });
    return json({ error: "AI returned an invalid response." }, 502);
  }

  try {
    const output = JSON.parse(outputText) as unknown;
    if (personalizeInput) {
      if (!isPersonalizeResponse(output)) throw new Error("Personalization schema validation failed");
      return json({ explanation: output.explanation.trim(), emotion: output.emotion.trim() });
    }
    if (!isExplainSceneResponse(output)) throw new Error("Schema validation failed");
    const anchor = readAnchor((output as ExplainSceneResponse).anchor);
    if (!anchor) throw new Error("Anchor validation failed");
    return json({ ...(output as ExplainSceneResponse), explanation: output.explanation.trim(), emotion: output.emotion.trim(), character: output.character.trim(), anchor });
  } catch (error) {
    console.error("[explain-scene] Could not parse structured OpenAI response", { requestId, model, openAIResponseId: completion.id, error: String(error), outputText: outputText.slice(0, 2_000) });
    return json({ error: "AI returned an invalid response." }, 502);
  }
});

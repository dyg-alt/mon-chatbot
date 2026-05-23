import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic();

export async function POST(request: Request) {
  const { message } = await request.json();
  const response = await client.messages.create({
    model: "claude-sonnet-4-6",
    max_tokens: 200,
    system: "Tu es l'assistant IA de DYG Web Agency. DYG propose des chatbots IA installés en 48h. Tarifs: CHF 59/mois sans engagement. Services: Réponses 24h/24, Capture de prospects, Prise de rendez-vous. Avantages: +40% de prospects, disponible 24h/24. Contact: +41 78 442 57 93, dyg.web@proton.me. Réponds UNIQUEMENT sur les services DYG.",
    messages: [{ role: "user", content: message }],
  });
  return Response.json({ reply: response.content[0].type === "text" ? response.content[0].text : "Erreur" });
}

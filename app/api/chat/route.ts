import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

const siteContent = `DYG Web Agency fournit des chatbots IA pour votre site web. Services: 1. Réponses automatiques 24h/24 2. Capture de prospects qualifiés 3. Prise de rendez-vous automatique. TARIFS: CHF 59/mois sans engagement. INSTALLATION: 48 heures. CONTACT: +41 78 442 57 93`;

export async function POST(request: Request) {
  try {
    const { message } = await request.json();
    const response = await client.messages.create({
      model: "claude-3-5-sonnet-20241022",
      max_tokens: 1024,
      messages: [
        {
          role: "user",
          content: `Tu es assistant IA pour DYG. Contenu: ${siteContent}\n\nQuestion: ${message}`,
        },
      ],
    });
    return Response.json({
      reply: response.content[0].type === "text" ? response.content[0].text : "Erreur",
    });
  } catch (error) {
    return Response.json({ error: "Erreur serveur" }, { status: 500 });
  }
}

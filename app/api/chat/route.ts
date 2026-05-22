import Anthropic from "@anthropic-ai/sdk";
import fs from "fs";
import path from "path";

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

interface SiteContent {
  title: string;
  headings: string[];
  paragraphs: string[];
  links: Array<{ text: string; href: string }>;
  fullText: string;
}

export async function POST(request: Request) {
  try {
    const { message } = await request.json();

    const contentPath = path.join(process.cwd(), "public", "siteContent.json");
    const siteContent: SiteContent = JSON.parse(
      fs.readFileSync(contentPath, "utf-8")
    );

    const context = `Tu es un assistant IA pour le site DYG Web Agency. Voici le contenu du site:
${siteContent.fullText.substring(0, 3000)}

Réponds en te basant UNIQUEMENT sur ce contenu du site.`;

    const response = await client.messages.create({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 1024,
      messages: [
        {
          role: "user",
          content: `${context}\n\nQuestion: ${message}`,
        },
      ],
    });

    return Response.json({
      reply:
        response.content[0].type === "text"
          ? response.content[0].text
          : "Erreur",
    });
  } catch (error) {
    console.error("Erreur:", error);
    return Response.json({ error: "Erreur serveur" }, { status: 500 });
  }
}

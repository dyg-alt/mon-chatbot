"use client";

import { useState } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = input;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage }),
      });

      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply || "Erreur" },
      ]);
    } catch (error) {
      console.error("Erreur:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-500 to-purple-600 p-4">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-4xl font-bold text-white mb-8 text-center">
          💬 DYG Web Agency
        </h1>

        <div className="bg-white rounded-lg shadow-2xl p-6 mb-4">
          <div className="h-96 overflow-y-auto mb-4 bg-gray-50 rounded p-4">
            {messages.length === 0 ? (
              <p className="text-gray-400 text-center">
                Posez vos questions sur DYG Web Agency !
              </p>
            ) : (
              messages.map((msg, i) => (
                <div
                  key={i}
                  className={`mb-4 ${
                    msg.role === "user" ? "text-right" : "text-left"
                  }`}
                >
                  <div
                    className={`inline-block max-w-xs px-4 py-2 rounded-lg ${
                      msg.role === "user"
                        ? "bg-blue-500 text-white rounded-br-none"
                        : "bg-gray-200 text-black rounded-bl-none"
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && sendMessage()}
              placeholder="Posez une question..."
              disabled={loading}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
            />
            <button
              onClick={sendMessage}
              disabled={loading}
              className="bg-blue-500 text-white px-6 py-3 rounded-lg font-semibold hover:bg-blue-600 disabled:bg-gray-400"
            >
              {loading ? "⏳" : "Envoyer"}
            </button>
          </div>
        </div>

        <p className="text-white text-center text-sm">
          Chatbot alimenté par Claude API
        </p>
      </div>
    </div>
  );
}

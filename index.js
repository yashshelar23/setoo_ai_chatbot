"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState("");
  const [preview, setPreview] = useState("");

  // Poll backend every 3 seconds to get updated scraped data
  useEffect(() => {
    const interval = setInterval(async () => {
      const res = await fetch("http://localhost:8001/scraped-data");
      const data = await res.json();
      if (data.data) setPreview(data.data);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleScrape = async () => {
    if (!url) return alert("Enter URL!");

    setStatus("Scraping...");
    const formData = new FormData();
    formData.append("url", url);

    try {
      const res = await fetch("http://localhost:8001/scrape", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setStatus(data.status === "success" ? "Scraping complete!" : "Error: " + data.message);
    } catch (err) {
      setStatus("Fetch error: " + err);
    }
  };

  return (
    <div style={{ maxWidth: 600, margin: "40px auto", padding: 20, background: "#fff", borderRadius: 12 }}>
      <h1>Website Scraper + Chatbot</h1>

      <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
        <input
          style={{ flex: 1, padding: 12, borderRadius: 8, border: "1px solid #ccc" }}
          type="text"
          placeholder="Enter website URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <button style={{ padding: 12, borderRadius: 8, background: "#6366f1", color: "#fff" }} onClick={handleScrape}>
          Scrape
        </button>
      </div>

      <div>{status}</div>
      <pre style={{ background: "#f9fafb", padding: 20, borderRadius: 10, maxHeight: 300, overflow: "auto" }}>
        {preview}
      </pre>

      {preview && (
        <div style={{ marginTop: 20 }}>
          <h2>Chatbot ready with scraped data!</h2>
          {/* You can integrate OpenAI GPT call here using preview as context */}
        </div>
      )}
    </div>
  );
}

/* Settings for the free study companion that signed-out readers get.

   Leave freeBase empty and the chat prepares the reader's question for the
   free ChatGPT or Claude website instead. To answer on the page for free, set
   freeBase to an OpenAI-compatible endpoint that accepts requests from this
   site, for example the Cloudflare Worker in tools/free-chat-worker/:

     freeBase: "https://epis-free-chat.<your-account>.workers.dev/v1",

   Never put a paid API key here: this file is public. */
window.EPIS_AI_CONFIG = {
  // Optional adaptive interview: the Worker base URL, without /v1.
  // Keep empty until tools/free-chat-worker is deployed with /reading-path support.
  readingPathBase: "",
  readingPathName: "Cloudflare Workers AI",
  freeBase: "",
  freeModel: "",
  freeKey: "",
  freeName: "Free assistant"
};

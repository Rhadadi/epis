# Free chat endpoint (optional)

Readers who aren't signed in with their own API key can use a free study
companion. By default the site hands their question to the free ChatGPT or
Claude website. With this small Cloudflare Worker, the free companion answers
right on the page instead, using Cloudflare's Workers AI.

Workers AI includes a daily free allowance. When it runs out, the endpoint
answers "try again tomorrow"; nothing is charged unless you move to a paid plan.

## Deploy

1. Create a free Cloudflare account.
2. On a computer with Node.js:

   ```sh
   cd tools/free-chat-worker
   npx wrangler login
   npx wrangler deploy
   ```

   Wrangler prints the address, for example
   `https://epis-free-chat.<your-account>.workers.dev`.
3. In `assets/ai-config.js`, set `freeBase` to that address followed by `/v1`,
   commit and push.

`wrangler.toml` sets the model and the sites that may use the endpoint
(`ALLOWED_ORIGINS`). Browsers enforce that list; to stop other programs using up
your allowance too, add a rate-limiting rule for the worker in the Cloudflare
dashboard.

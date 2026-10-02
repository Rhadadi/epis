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

## Reading-path interview

The same Worker also exposes `POST /reading-path`. Build the site before
deploying so its generated `interview-bank.js` matches the curated reading
routes. Set `readingPathBase` in `assets/ai-config.js` to the Worker URL **without
`/v1`**. Keep it empty until this version of the Worker is deployed.

The interview is optional and off until the visitor chooses it. It accepts
only a question (up to 600 characters) and a study mode, returns a validated
topic ID and a follow-up question, and never provides page URLs. It does not
log interview bodies. Provider data handling still applies. Quota failures
and invalid responses make the website use its curated questions instead.
Use the Cloudflare dashboard to set rate limits and check your plan's current
quota and billing terms before enabling a public endpoint.

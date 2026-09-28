// Render Mermaid diagrams to SVG in light and dark versions for the website.
//
//   node tools/site/render_mermaid.cjs <jobs.json> <out-dir>
//
// jobs.json maps an id to Mermaid source. Writes <out-dir>/<id>-light.svg and
// <id>-dark.svg. Needs the npm packages playwright-core and mermaid (on
// NODE_PATH or installed locally) and a Chromium; set CHROMIUM_PATH if
// Playwright cannot find one by itself.
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright-core");

const [jobsFile, outDir] = process.argv.slice(2);
// The site's own fonts, embedded, so labels are measured with the type they are shown in.
const fontsDir = path.join(__dirname, "..", "..", "assets", "fonts");
const fontsCss = fs.readFileSync(path.join(fontsDir, "fonts.css"), "utf8").replace(/url\(([^)]+\.woff2)\)/g, (m, file) =>
  `url(data:font/woff2;base64,${fs.readFileSync(path.join(fontsDir, file)).toString("base64")})`);
const jobs = JSON.parse(fs.readFileSync(jobsFile, "utf8"));
const mermaidJs = fs.readFileSync(require.resolve("mermaid/dist/mermaid.min.js"), "utf8");

const font = "'Source Serif 4', Georgia, serif";
const themes = {
  light: { background: "#FFFDF8", primaryColor: "#F3EEE3", primaryBorderColor: "#8A4F00", primaryTextColor: "#1B2730",
           secondaryColor: "#E7F1F3", tertiaryColor: "#FFFDF8", lineColor: "#6B7C86", textColor: "#1B2730",
           mainBkg: "#F3EEE3", nodeBorder: "#8A4F00", clusterBkg: "#F6F3EC", edgeLabelBackground: "#FFFDF8",
           fontFamily: font, fontSize: "15px" },
  dark: { background: "#112433", primaryColor: "#16303F", primaryBorderColor: "#F2B84B", primaryTextColor: "#E8EEF1",
          secondaryColor: "#1B3A4B", tertiaryColor: "#112433", lineColor: "#9AABB5", textColor: "#E8EEF1",
          mainBkg: "#16303F", nodeBorder: "#F2B84B", clusterBkg: "#0E1D29", edgeLabelBackground: "#112433",
          fontFamily: font, fontSize: "15px" },
};

(async () => {
  const opts = process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {};
  const browser = await chromium.launch(opts);
  const page = await browser.newPage();
  await page.setContent(`<html><head><style>${fontsCss}</style></head><body><p style="font-family:'Source Serif 4'">Aa <i>Aa</i></p></body></html>`);
  await page.evaluate(async () => {
    await document.fonts.load("15px 'Source Serif 4'");
    await document.fonts.load("14px Vazirmatn", "معرفت");
    await document.fonts.ready;
  });
  await page.addScriptTag({ content: mermaidJs });
  for (const [mode, vars] of Object.entries(themes)) {
    for (const [id, code] of Object.entries(jobs)) {
      // Persian diagrams are set in Vazirmatn, which has the Arabic-script glyphs.
      const fa = /[\u0600-\u06FF]/.test(code);
      const themeVars = fa ? { ...vars, fontFamily: "Vazirmatn, 'Source Serif 4', sans-serif", fontSize: "14px" } : vars;
      const svg = await page.evaluate(async ({ id, code, vars, mode }) => {
        mermaid.initialize({ startOnLoad: false, theme: "base", themeVariables: vars, securityLevel: "strict",
                             flowchart: { htmlLabels: false, curve: "basis" } });
        const { svg } = await mermaid.render(`dg-${id}-${mode}`, code);
        return svg;
      }, { id, code, vars: themeVars, mode });
      fs.writeFileSync(path.join(outDir, `${id}-${mode}.svg`), svg);
      console.log(`  diagram ${id} (${mode})`);
    }
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });

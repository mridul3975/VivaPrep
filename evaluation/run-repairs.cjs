// Executes only the committed synthetic evaluation fixtures in the actual UI sandbox.
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto')
const { stripTypeScriptTypes } = require('node:module')
const http = require('node:http')
const { chromium } = require(process.env.EVAL_PLAYWRIGHT_MODULE || 'playwright')
const root = path.resolve(__dirname, '..'), file = path.join(__dirname, 'dataset.json')
const sha = value => crypto.createHash('sha256').update(value).digest('hex')
;(async () => {
  const dataset = JSON.parse(fs.readFileSync(file, 'utf8'))
  const runner = fs.readFileSync(path.join(root, 'frontend/src/debug/runner.ts'), 'utf8')
  const server = http.createServer((_request, response) => { response.setHeader('Content-Type', 'text/html'); response.end('<!doctype html><title>RepoViva curated repair evaluation</title>') })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  let browser
  try {
    browser = await chromium.launch({ headless: true, ...(process.env.EVAL_CHROME_PATH ? { executablePath: process.env.EVAL_CHROME_PATH } : {}) })
    const page = await browser.newPage()
    await page.goto(`http://127.0.0.1:${server.address().port}`)
    const js = stripTypeScriptTypes(runner, { mode: 'strip' }).replace(/^export /gm, '')
    await page.addScriptTag({ content: js + '\nglobalThis.evalRepair = runInSandbox;' })
    const results = [], references = {}
    const execute = async (code, family) => page.evaluate(async ({ code, tests, fn }) => window.evalRepair(code, tests, undefined, fn), { code, tests: family.tests, fn: family.function_name })
    for (const [name, family] of Object.entries(dataset.repair_families)) {
      const rows = await execute(family.reference_code, family)
      references[name] = { results: rows, passed: rows.every(row => row.passed) }
      if (!references[name].passed) throw new Error('Invalid reviewed reference tests: ' + name)
    }
    for (const item of dataset.repairs) {
      const family = dataset.repair_families[item.family]
      const observations = await execute(family[item.variant], family)
      const verdict = observations.every(row => row.passed) ? 'correct' : 'incorrect'
      results.push({ id: item.id, verdict, agrees_with_draft_label: verdict === item.expected, observations })
    }
    const output = { dataset_sha256: sha(fs.readFileSync(file)), runner_sha256: sha(runner), boundary: 'Actual browser sandbox; synthetic JavaScript fixtures only. Four finite test suites are not proof for every possible input.', references, results }
    fs.writeFileSync(path.join(__dirname, 'browser-tests.json'), JSON.stringify(output, null, 2) + '\n')
    console.log(`Reference suites: ${Object.keys(references).length}/${Object.keys(references).length}; repair cases against draft labels: ${results.filter(row => row.agrees_with_draft_label).length}/${results.length}`)
  } finally { await browser?.close(); await new Promise(resolve => server.close(resolve)) }
})().catch(error => { console.error(error); process.exitCode = 1 })

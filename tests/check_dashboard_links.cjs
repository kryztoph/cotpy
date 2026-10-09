// Optional browser regression: npm install --prefix /tmp/cotpy-browser playwright
// NODE_PATH=/tmp/cotpy-browser/node_modules node tests/check_dashboard_links.cjs
// Generate --dashboard first. CHROMIUM_PATH may select an existing browser.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

(async function () {
    const charts = path.resolve(process.argv[2] || 'output/charts');
    const url = pathToFileURL(path.join(charts, 'dashboard.html')).href;
    const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH});
    try {
        const page = await browser.newPage({viewport: {width: 1600, height: 1000}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        async function openDashboard() {
            await page.goto(url);
            await page.waitForSelector('.table a[href]');
        }
        async function clickChart(link) {
            const href = await link.getAttribute('href');
            let box = await link.boundingBox();
            // Scroll the page, not SVG table groups (scrollIntoView can move those).
            if (box.y > 900) {
                await page.evaluate(y => window.scrollTo(0, y - 300), box.y);
                box = await link.boundingBox();
            }
            await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
            await page.waitForURL('**/' + href);
            await page.waitForSelector('.scatterlayer');
        }
        await openDashboard();
        await page.evaluate(() => {
            const graph = document.querySelector('.js-plotly-plot');
            if (graph.data.filter(trace => trace.type === 'table').length !== 1 ||
                    graph.layout.annotations.some(annotation => annotation.text === 'Key Markets')) {
                throw new Error('Dashboard should have one full market table and no duplicate Key Markets section');
            }
            const full = graph.data.find(trace => trace.type === 'table' && trace.header.values.includes('Category'));
            if (!full || full.domain.y[0] < .6 || graph.layout.height !== 3000) {
                throw new Error('Full market table must remain at the top of the original dashboard layout');
            }
            if (full.cells.values[0].length !== graph.data.find(trace => trace.type === 'scatter').text.length) {
                throw new Error('The top table must include every analyzed market');
            }
        });
        assert(await page.locator('.csfox-header').isVisible());
        assert(await page.locator('.dashboard-sort-controls').isVisible());
        console.log('PASS all markets remain at the top with branding and sorting controls');
        const links = await page.locator('.table a').evaluateAll(elements =>
            elements.map(a => a.getAttribute('href')));
        assert(links.length > 0);
        for (const href of links) {
            assert(href);
            assert(fs.existsSync(path.join(charts, decodeURIComponent(href))));
        }
        await clickChart(page.locator('.table a[href]').first());
        console.log('PASS local link navigation and existing chart destinations');

        await openDashboard();
        await page.locator('[data-sort-key="market"]').click();
        await page.waitForFunction(() => document.querySelector('[data-sort-key="market"]').textContent.includes('▲'));
        await clickChart(page.locator('.table').last().locator('a[href]').first());
        console.log('PASS sorted table navigation');

        await openDashboard();
        // Reproduce today's hosted failure: wrapped markup inside a table value.
        await page.evaluate(async () => {
            const graph = document.querySelector('.js-plotly-plot');
            const index = graph.data.findLastIndex(trace => trace.type === 'table');
            const values = graph.data[index].cells.values.map(column => [...column]);
            values[1] = values[1].map(value => value.replace('">', '"<br>target="_self">'));
            await Plotly.restyle(graph, {'cells.values': [values]}, [index]);
        });
        const repaired = page.locator('.table').last().locator('a[href]').first();
        await page.waitForFunction(() => {
            const a = [...document.querySelectorAll('.table')].at(-1).querySelector('a[href]');
            return a && !a.textContent.includes('target=');
        });
        await clickChart(repaired);
        console.log('PASS wrapped anchor markup repaired after redraw');
        await openDashboard();
        const scrollLink = page.locator('.table').last().locator('a[href]').nth(20);
        await clickChart(scrollLink);
        console.log('PASS page scrolling preserves clickable market links');
        assert.deepEqual(errors, []);
        console.log('PASS no JavaScript errors');
    } finally {
        await browser.close();
    }
})().catch(error => {console.error(error); process.exitCode = 1;});

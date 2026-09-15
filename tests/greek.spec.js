const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const instance = require('../docs/instance.json');
const chunks = require('../docs/data/chunks.json');
const tokens2 = require('../docs/data/tokens2.json');

async function ready(page, url = '/') {
  await page.goto(url);
  await page.waitForFunction(() => window.__contabulateReady === true);
  await expect(page.locator('#results tbody tr').first()).toBeVisible();
}

test('sample links restore Greek search and commentary in a fresh page', async ({ page, context }) => {
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  for (const sample of instance.sample_queries) {
    const url = new URL(sample.url);
    await ready(page, url.pathname + url.search);
    if (url.searchParams.has('cm')) {
      await expect(page.locator('.commentary-detail-overlay.open')).toBeVisible();
      await expect(page.locator('.commentary-detail-table tbody tr').first()).toContainText('Augustine');
    } else {
      await expect(page.locator('#gran')).toHaveValue('line');
      await expect(page.locator('#results tbody tr').first()).toContainText('04.John.001.001');
      await expect(page.locator('#results tbody .hit').first()).toHaveText('λόγος');
      const copied = await context.newPage();
      await ready(copied, page.url());
      await expect(copied.locator('#results tbody tr').first()).toContainText('04.John.001.001');
      await copied.close();
    }
  }
  expect(errors).toEqual([]);
});

test('decomposed Greek phrase, punctuation highlights, and phrase percentages agree with indexes', async ({ page }) => {
  await ready(page, '/?q=' + encodeURIComponent('ἐν ἀρχῇ'.normalize('NFD')) + '&gran=line');
  await expect(page.locator('#results tbody tr').filter({ hasText: '04.John.001.001' })).toHaveCount(1);
  await expect(page.locator('#results tbody .hit').first()).toBeVisible();
  const helper = await page.evaluate(() => ({
    highlighted: highlightHTML('ὁ λόγος, καὶ θεός.', buildHighlightRegexFromNgrams(['λόγος καὶ'])),
    inside: highlightHTML('λογοσλόγος', buildHighlightRegexFromNgrams(['λόγος'])),
    elision: tokenizeLineText('διʼ αὐτοῦ'),
  }));
  expect(helper.highlighted).toContain('<span class="hit">λόγος, καὶ</span>');
  expect(helper.inside).not.toContain('class="hit"');
  expect(helper.elision).toEqual(['δι', 'αὐτοῦ']);
  await ready(page, '/');
  await page.selectOption('#newTermDisplay', 'pct');
  await page.fill('#q', 'ἐν ἀρχῇ');
  await page.click('#addColumnBtn');
  const ids = new Set(chunks.filter(c => c.play_id === 4).map(c => c.scene_id));
  const hits = tokens2['ἐν ἀρχῇ'].filter(([id]) => ids.has(id)).reduce((s, [, n]) => s + n, 0);
  const denominator = chunks.filter(c => c.play_id === 4).reduce((s, c) => s + Math.max(0, c.total_words - 1), 0);
  const john = page.locator('#results tbody tr').filter({ hasText: '04.John' });
  const cell = john.locator('td[data-key="t0_pct"]');
  expect(Number((await cell.textContent()).replace('%', ''))).toBeCloseTo(hits / denominator * 100, 3);
});

test('filter, sort, page, reorder, and full CSV preserve the result', async ({ page }, testInfo) => {
  await ready(page, '/?gran=act&s_ft_location=%5E01%5C.Matt%5C.&sk=location&sd=asc');
  await page.selectOption('#segmentsPageSize', '25');
  await expect(page.locator('#segmentsTotalInfo')).toContainText('28 total rows');
  await page.locator('th[data-key="location"]').click();
  await expect(page.locator('#results tbody tr').first()).toContainText('01.Matt.028');
  await page.click('#segmentsNextPage');
  await expect(page.locator('#results tbody tr')).toHaveCount(3);
  await page.locator('th[data-key="play_title"]').dragTo(page.locator('th[data-key="location"]'));
  await expect(page.locator('#results thead th').first()).toHaveAttribute('data-key', 'play_title');
  await page.locator('#segmentsTab details summary').click();
  const downloadPromise = page.waitForEvent('download');
  await page.click('#downloadSegmentsCsv');
  const download = await downloadPromise;
  const destination = testInfo.outputPath('chapters.csv');
  await download.saveAs(destination);
  const csv = fs.readFileSync(destination, 'utf8').trim().split('\n');
  expect(csv).toHaveLength(29);
  expect(csv[0]).toMatch(/^Book,Location/);
  expect(csv[1]).toContain('01.Matt.028');
  expect(csv[28]).toContain('01.Matt.001');
  await page.reload();
  await page.waitForFunction(() => window.__contabulateReady === true);
  await expect(page.locator('#results thead th').first()).toHaveAttribute('data-key', 'play_title');
  await expect(page.locator('#segmentsActiveFilters')).toContainText('01.Matt.');
});

test('unsupported names, empty results, invalid regex, and unavailable source recover visibly', async ({ page }) => {
  await ready(page, '/?gran=word&xn=1');
  await expect(page.locator('#vocabNamesUnavailable')).toBeVisible();
  await expect(page.locator('#vocabNamesToggle')).toBeHidden();
  await expect(page.locator('.ngram-exclude-btn, .name-dimmed')).toHaveCount(0);
  await ready(page, '/?q=zzzznonexistent&gran=line');
  await expect(page.locator('#results tbody')).toContainText(/No /i);
  await expect(page.locator('#loadingIndicator')).toBeHidden();
  await ready(page, '/');
  await page.selectOption('#matchMode', 'regex');
  await page.fill('#q', '[');
  await page.click('#addColumnBtn');
  await expect(page.locator('#results tbody')).toContainText('Invalid regex');
  await page.route('**/data/chunks.json', route => route.fulfill({ status: 503, body: 'Unavailable' }));
  await page.goto('/');
  await expect(page.locator('[role="alert"]')).toContainText('Unable to load data');
  await expect(page.locator('#loadingIndicator')).toBeHidden();
});

test('crosswalk commentary opens under Greek numbering', async ({ page }) => {
  await ready(page, '/?cm=2Cor.13.13');
  await expect(page.locator('#commentaryDetailTitle')).toContainText('13:13');
  const row = page.locator('.commentary-detail-table tbody tr').first();
  await expect(row).toBeVisible();
  await expect(page.locator('.commentary-detail-overlay')).toContainText('HCF numbering');
  await expect(page.locator('.commentary-detail-table thead')).toContainText('HCF passage');
});

test('desktop and mobile layouts keep the table usable', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await ready(page);
  await expect(page.locator('#results tbody tr')).toHaveCount(27);
  await page.screenshot({ path: 'test-results/gnt-desktop.png', fullPage: true });
  await ready(page, '/?q=' + encodeURIComponent('λόγος') + '&gran=line&s_ft_location=%5E04%5C.John%5C.&sk=location&sd=asc');
  await page.screenshot({ path: 'test-results/gnt-john.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('#addColumnsMobile')).toBeVisible();
  const bounds = await page.evaluate(() => ({ page: document.documentElement.scrollWidth, viewport: innerWidth,
    table: document.querySelector('#results').scrollWidth, tableWidth: document.querySelector('#results').clientWidth }));
  expect(bounds.page).toBeLessThanOrEqual(bounds.viewport + 1);
  expect(bounds.table).toBeGreaterThan(bounds.tableWidth);
  await page.screenshot({ path: 'test-results/gnt-mobile.png', fullPage: false });
  const mobileButton = await page.locator('#addColumnsMobile').boundingBox();
  const input = await page.locator('#q').boundingBox();
  expect(mobileButton.y).toBeGreaterThan(input.y + input.height);
  expect(mobileButton.height).toBeLessThan(75);
  await page.click('#addColumnsMobile');
  await expect(page.locator('.add-column-popover')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('.add-column-popover')).toBeHidden();
  await page.goto('/sources.html');
  await expect(page.locator('h1')).toHaveText('Edition and sources');
});

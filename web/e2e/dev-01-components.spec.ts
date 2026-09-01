/**
 * Feature: DEV-01 shared component visual baseline.
 * Responsibilities: verify deterministic primitive rendering across approved mobile widths.
 * Does not own: business navigation, API data, or feature page flows.
 * Plan task: DEV-01.
 */

import { expect, type Page, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

async function renderSurface(page: Page) {
  const tokens = await readFile(new URL("../src/styles/tokens.css", import.meta.url), "utf8");
  const primitives = await readFile(new URL("../src/shared/components/primitives.css", import.meta.url), "utf8");
  const css = `${tokens}\n${primitives.replace('@import "../../styles/tokens.css";', "")}`;
  await page.setContent(`
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
        <style>${css}</style>
      </head>
      <body style="margin:0;background:var(--stb-color-page-bg);font-family:var(--stb-font-family);">
        <main class="stb-mobile-surface" data-testid="surface" style="padding:18px 16px 92px;">
          <header class="stb-top-bar" style="padding-left:0;padding-right:0;">
            <div class="stb-top-bar__title">
              <h1 class="stb-text-page-title">组件基线长标题验证</h1>
              <p class="stb-text-secondary">稳定、无业务数据、移动端安全区域</p>
            </div>
            <button class="stb-button stb-button--secondary stb-button--icon" aria-label="更多">…</button>
          </header>
          <section class="stb-card">
            <h2 class="stb-card__title">基础卡片</h2>
            <div class="stb-card__body">
              <span class="stb-badge stb-badge--info">很长的中性视觉标签用于换行验证</span>
              <p class="stb-text-body">这是一段确定性展示文本，不包含员工、任务或接口数据。</p>
              <div class="stb-progress" role="progressbar" aria-label="完成度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="68">
                <div class="stb-progress__head"><span>完成度</span><span>68%</span></div>
                <div class="stb-progress__track"><span class="stb-progress__bar" style="width:68%"></span></div>
              </div>
            </div>
          </section>
          <label class="stb-field">
            <span class="stb-field__label">输入框</span>
            <input class="stb-field__control" placeholder="请输入中性内容" />
            <span class="stb-field__helper">辅助说明文本</span>
          </label>
          <section class="stb-state">
            <div class="stb-state__title">暂无内容</div>
            <div class="stb-state__detail">后续业务页面可复用该状态。</div>
          </section>
          <section class="stb-state stb-state--error" role="alert">
            <div class="stb-state__title">内容暂时无法加载</div>
            <div class="stb-state__detail">错误展示不解析业务异常。</div>
          </section>
          <div class="stb-overlay" style="position:relative;inset:auto;margin:16px 0 0;min-height:180px;">
            <section class="stb-sheet" role="dialog" aria-modal="true" aria-label="组件抽屉">
              <div class="stb-sheet__head">
                <h2 class="stb-sheet__title">组件抽屉</h2>
                <button class="stb-button stb-button--ghost stb-button--icon" aria-label="关闭抽屉">×</button>
              </div>
              <p class="stb-text-secondary">固定内容用于截图基线。</p>
            </section>
          </div>
          <nav class="stb-bottom-nav" aria-label="底部导航" style="position:absolute;">
            <button class="stb-bottom-nav__item stb-bottom-nav__item--active" aria-current="page"><span aria-hidden="true">⌂</span><span>首页</span></button>
            <button class="stb-bottom-nav__item"><span aria-hidden="true">□</span><span>概览</span></button>
            <button class="stb-bottom-nav__item"><span aria-hidden="true">＋</span><span>创建</span></button>
            <button class="stb-bottom-nav__item"><span aria-hidden="true">○</span><span>我的</span></button>
          </nav>
        </main>
      </body>
    </html>
  `);
}

test.describe("DEV-01 deterministic shared primitives", () => {
  test("has no horizontal overflow and matches screenshot baseline", async ({ page }, testInfo) => {
    await renderSurface(page);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await expect(page.getByTestId("surface")).toHaveScreenshot(`dev-01-components-${testInfo.project.name}.png`);
  });
});

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const designs = [
  { name: 'Enterprise Light', port: 3001, description: 'Professional B2B aesthetic' },
  { name: 'Cyberpunk Dark', port: 3002, description: 'Neon on black, developer-focused' },
  { name: 'Glassmorphism', port: 3003, description: 'Frosted glass effects, premium' },
  { name: 'Nordic Minimal', port: 3004, description: 'Ultra-clean, spacious' },
  { name: 'Vibrant Modern', port: 3005, description: 'Purple-blue gradients, energetic' },
];

async function evaluateDesigns() {
  const browser = await chromium.launch({ headless: true });
  const screenshotDir = './design-screenshots';

  if (!fs.existsSync(screenshotDir)) {
    fs.mkdirSync(screenshotDir, { recursive: true });
  }

  const results: any[] = [];

  for (const design of designs) {
    console.log(`\n=== Evaluating: ${design.name} (Port ${design.port}) ===`);

    const context = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
    });
    const page = await context.newPage();

    const designResult: any = {
      name: design.name,
      port: design.port,
      description: design.description,
      screenshots: [],
      metrics: {},
      observations: [],
    };

    try {
      // Navigate to home page
      const url = `http://localhost:${design.port}`;
      await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });

      // Wait for content to load
      await page.waitForTimeout(3000);

      // Take screenshot
      const screenshotPath = path.join(screenshotDir, `${design.port}-${design.name.toLowerCase().replace(/\s+/g, '-')}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: false });
      designResult.screenshots.push(screenshotPath);
      console.log(`  ✓ Screenshot: ${screenshotPath}`);

      // Analyze page structure
      const bodyBg = await page.evaluate(() => {
        return window.getComputedStyle(document.body).backgroundColor;
      });

      const textColor = await page.evaluate(() => {
        return window.getComputedStyle(document.body).color;
      });

      const headings = await page.$$('h1, h2, h3');
      const buttons = await page.$$('button');
      const links = await page.$$('a');

      designResult.metrics = {
        backgroundColor: bodyBg,
        textColor: textColor,
        headingCount: headings.length,
        buttonCount: buttons.length,
        linkCount: links.length,
      };

      console.log(`  Background: ${bodyBg}`);
      console.log(`  Text: ${textColor}`);
      console.log(`  Headings: ${headings.length}, Buttons: ${buttons.length}`);

      // Analyze first button if exists
      if (buttons.length > 0) {
        const buttonStyle = await buttons[0].evaluate((el) => {
          const styles = window.getComputedStyle(el);
          return {
            bg: styles.backgroundColor,
            color: styles.color,
            borderRadius: styles.borderRadius,
            padding: styles.padding,
            fontSize: styles.fontSize,
            fontWeight: styles.fontWeight,
          };
        });
        designResult.observations.push(`Button: ${JSON.stringify(buttonStyle)}`);
        console.log(`  Button style: ${JSON.stringify(buttonStyle, null, 2)}`);
      }

      // Check font family
      const fontFamily = await page.evaluate(() => {
        return window.getComputedStyle(document.body).fontFamily;
      });
      designResult.observations.push(`Font: ${fontFamily}`);
      console.log(`  Font: ${fontFamily}`);

      // Check for common design elements
      const hasGradients = await page.evaluate(() => {
        const allElements = document.querySelectorAll('*');
        for (const el of allElements) {
          const style = window.getComputedStyle(el);
          if (style.backgroundImage.includes('gradient')) {
            return true;
          }
        }
        return false;
      });
      designResult.observations.push(`Has gradients: ${hasGradients}`);

      const hasShadows = await page.evaluate(() => {
        const allElements = document.querySelectorAll('*');
        for (const el of allElements) {
          const style = window.getComputedStyle(el);
          if (style.boxShadow !== 'none') {
            return true;
          }
        }
        return false;
      });
      designResult.observations.push(`Has shadows: ${hasShadows}`);

      const hasBlur = await page.evaluate(() => {
        const allElements = document.querySelectorAll('*');
        for (const el of allElements) {
          const style = window.getComputedStyle(el);
          if (style.backdropFilter !== 'none' || style.filter.includes('blur')) {
            return true;
          }
        }
        return false;
      });
      designResult.observations.push(`Has blur effects: ${hasBlur}`);

    } catch (error: any) {
      console.log(`  ✗ Error: ${error.message}`);
      designResult.error = error.message;
    }

    await context.close();
    results.push(designResult);
  }

  await browser.close();

  // Write results to JSON
  const resultsPath = path.join(screenshotDir, 'evaluation-results.json');
  fs.writeFileSync(resultsPath, JSON.stringify(results, null, 2));
  console.log(`\n✓ Full results saved to: ${resultsPath}`);

  return results;
}

evaluateDesigns().catch(console.error);

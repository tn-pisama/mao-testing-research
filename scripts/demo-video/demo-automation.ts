/**
 * PISAMA Demo Video Automation Script
 * Uses Playwright to automate browser interactions for demo recording
 *
 * Run with: npx ts-node demo-automation.ts
 * Or: npx playwright test demo-automation.ts
 */

import { chromium, Browser, Page } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';

const BASE_URL = process.env.DEMO_URL || 'http://localhost:3000';
const TRACE_FILE = path.join(__dirname, '../../docs/demo-traces/semantic-loop.json');

interface DemoStep {
  name: string;
  action: () => Promise<void>;
  duration: number; // milliseconds to wait after action
}

async function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runDemo() {
  console.log('Starting PISAMA Demo Automation...\n');

  const browser: Browser = await chromium.launch({
    headless: false,
    slowMo: 100, // Slow down actions for visibility
    args: ['--start-maximized']
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: {
      dir: path.join(__dirname, 'recordings'),
      size: { width: 1920, height: 1080 }
    }
  });

  const page: Page = await context.newPage();

  const steps: DemoStep[] = [
    // Section 1: Hook - Show dashboard
    {
      name: '1. Navigate to Dashboard',
      action: async () => {
        await page.goto(`${BASE_URL}/dashboard`);
        await page.waitForLoadState('networkidle');
      },
      duration: 3000
    },

    // Section 2: Navigate to Demo
    {
      name: '2. Navigate to Demo Page',
      action: async () => {
        await page.goto(`${BASE_URL}/demo`);
        await page.waitForLoadState('networkidle');
      },
      duration: 2000
    },

    // Select Infinite Loop scenario
    {
      name: '3. Select Infinite Loop Scenario',
      action: async () => {
        // Click on scenario selector
        const scenarioSelector = page.locator('.scenario-selector, [data-testid="scenario-selector"]').first();
        if (await scenarioSelector.isVisible()) {
          await scenarioSelector.click();
          await sleep(500);

          // Select Infinite Loop option
          const infiniteLoopOption = page.locator('text=Infinite Loop').first();
          if (await infiniteLoopOption.isVisible()) {
            await infiniteLoopOption.click();
          }
        }
      },
      duration: 2000
    },

    // Click Start Demo
    {
      name: '4. Start Demo Simulation',
      action: async () => {
        const startButton = page.locator('.demo-start-button, button:has-text("Start"), [data-testid="start-demo"]').first();
        if (await startButton.isVisible()) {
          await startButton.click();
        }
      },
      duration: 1000
    },

    // Wait for agents to execute
    {
      name: '5. Watch Agents Execute',
      action: async () => {
        // Wait for metrics panel to update
        await page.waitForSelector('.metrics-panel, [data-testid="metrics"]', { timeout: 10000 }).catch(() => {});
        console.log('   Watching agent execution...');
      },
      duration: 15000
    },

    // Wait for detection
    {
      name: '6. Wait for Detection Alert',
      action: async () => {
        // Wait for detection feed to show alert
        await page.waitForSelector('.detection-feed, [data-testid="detection"], .alert', { timeout: 20000 }).catch(() => {});
        console.log('   Detection triggered!');
      },
      duration: 5000
    },

    // Show fix suggestion
    {
      name: '7. Highlight Fix Suggestion',
      action: async () => {
        const fixButton = page.locator('button:has-text("Fix"), button:has-text("Apply"), .fix-suggestion').first();
        if (await fixButton.isVisible()) {
          await fixButton.hover();
        }
      },
      duration: 3000
    },

    // Section 3: Try Your Own Trace
    {
      name: '8. Scroll to Trace Upload',
      action: async () => {
        const uploadSection = page.locator('.trace-upload, [data-testid="trace-upload"], text=Try Your Own').first();
        if (await uploadSection.isVisible()) {
          await uploadSection.scrollIntoViewIfNeeded();
        } else {
          await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        }
      },
      duration: 2000
    },

    // Upload trace file
    {
      name: '9. Upload Sample Trace',
      action: async () => {
        // Check if trace file exists
        if (fs.existsSync(TRACE_FILE)) {
          const fileInput = page.locator('input[type="file"]').first();
          if (await fileInput.count() > 0) {
            await fileInput.setInputFiles(TRACE_FILE);
            console.log('   Uploaded trace file');
          }
        } else {
          console.log('   Trace file not found, simulating upload');
          // Try drag-drop area click
          const dropZone = page.locator('.drop-zone, [data-testid="drop-zone"], .trace-upload').first();
          if (await dropZone.isVisible()) {
            await dropZone.click();
          }
        }
      },
      duration: 3000
    },

    // Show analysis result
    {
      name: '10. View Analysis Results',
      action: async () => {
        await page.waitForSelector('.detection, .analysis-result, [data-testid="result"]', { timeout: 10000 }).catch(() => {});
      },
      duration: 5000
    },

    // Section 4: CLI - Would need terminal recording (skip for browser automation)
    {
      name: '11. Pause for CLI Demo (manual)',
      action: async () => {
        console.log('   [CLI section - record terminal separately]');
      },
      duration: 1000
    },

    // Section 5: Features - Navigate to features/benchmarks
    {
      name: '12. Navigate to Benchmarks',
      action: async () => {
        await page.goto(`${BASE_URL}/benchmarks`);
        await page.waitForLoadState('networkidle');
      },
      duration: 3000
    },

    // Section 6: CTA - Navigate to docs
    {
      name: '13. Navigate to Case Studies',
      action: async () => {
        await page.goto(`${BASE_URL}/case-studies`);
        await page.waitForLoadState('networkidle');
      },
      duration: 3000
    },

    // End card
    {
      name: '14. Show End Card',
      action: async () => {
        // Navigate to landing page or show logo
        await page.goto(`${BASE_URL}`);
        await page.waitForLoadState('networkidle');
      },
      duration: 5000
    }
  ];

  // Execute all steps
  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    console.log(`[${i + 1}/${steps.length}] ${step.name}`);

    try {
      await step.action();
      await sleep(step.duration);
    } catch (error) {
      console.log(`   Warning: ${error}`);
    }
  }

  console.log('\nDemo automation complete!');

  // Close browser
  await context.close();
  await browser.close();

  console.log('\nRecordings saved to: scripts/demo-video/recordings/');
}

// Run if executed directly
runDemo().catch(console.error);

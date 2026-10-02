// Copyright 2026 The Kubeflow Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import { test, expect, Locator, Page } from '@playwright/test';

/** Opens JupyterLab and clicks the Kale sidebar tab. */
async function openKaleTab(page: Page): Promise<void> {
  await page.goto('http://localhost:8889/lab', { waitUntil: 'load' });

  await page.waitForTimeout(3000);

  // Dismiss the Git dialog if it appears
  const dismissButton = page.locator('button', { hasText: 'Dismiss' });
  if (await dismissButton.isVisible({ timeout: 2000 }).catch(() => false)) {
    await dismissButton.click();
    await page.waitForTimeout(500);
  }

  // Click the Kale sidebar tab (Kubeflow Pipelines Deployment Panel)
  const kaleTab = page.locator('[title="Kubeflow Pipelines Deployment Panel"]');
  await kaleTab.click();

  await page.waitForTimeout(1000);
}

/** Opens the Kale tab, creates a fresh notebook, and enables Kale on it. */
async function openKaleEnabledNotebook(page: Page): Promise<void> {
  await openKaleTab(page);

  // Create a new notebook
  const pythonNotebook = page
    .locator(
      '.jp-LauncherCard:has(.jp-LauncherCard-label[title="Python 3 (ipykernel)"])',
    )
    .first();
  await pythonNotebook.click();

  const notebookPanel = page.locator('.jp-NotebookPanel');
  await expect(notebookPanel).toBeVisible({ timeout: 5000 });

  // Enable Kale
  const enableSwitch = page.locator('input[name="enableKale"]');
  await enableSwitch.click();
  await expect(enableSwitch).toBeChecked();
}

/** Kale rewrites metadata on every change - accept unsaved changes. */
async function acceptUnsavedChangesPrompt(page: Page): Promise<void> {
  const prompt = page
    .locator('.jp-Dialog')
    .filter({ hasText: 'Unsaved Changes' });
  await page.addLocatorHandler(prompt, async dialog => {
    await dialog.getByRole('button', { name: 'YES' }).click();
  });
}

/** Dismiss Kale's error dialog to unblock other actions. */
async function dismissKaleErrorDialogs(page: Page): Promise<void> {
  const errorDialog = page.locator('.jp-Dialog').filter({ hasText: 'Error' });
  await page.addLocatorHandler(errorDialog, async dialog => {
    await dialog.getByRole('button', { name: 'Close' }).click();
  });
}

function getDeployButtonGroup(page: Page): Locator {
  return page.locator('[aria-label="split button"]');
}

function getAddVolumeDialog(page: Page): Locator {
  return page.getByRole('dialog', { name: 'Add Volume' });
}

/** Opens the "Add Volume" dialog via the "+ Add Volume" panel button. */
async function openAddVolumeDialog(page: Page): Promise<Locator> {
  await page.locator('.kale-add-volume-btn').click();
  const dialog = getAddVolumeDialog(page);
  await expect(dialog).toBeVisible({ timeout: 5000 });
  return dialog;
}

/** Fills and submits the Add Volume dialog, then waits for it to close. */
async function fillAndSubmitVolume(
  dialog: Locator,
  { name, mountPoint }: { name: string; mountPoint: string },
): Promise<void> {
  await dialog.getByLabel('PVC name').fill(name);
  await dialog.getByLabel('Mount path').fill(mountPoint);
  await dialog.getByRole('button', { name: 'Add volume', exact: true }).click();
  await expect(dialog).not.toBeVisible({ timeout: 5000 });
}

test.describe('Kale Empty State', () => {
  test('should open the Kale panel and verify the empty-state components', async ({
    page,
  }) => {
    await page.goto('http://localhost:8889/lab', { waitUntil: 'load' });

    await page.waitForTimeout(3000);

    // Dismiss the Git dialog if it appears
    const dismissButton = page.locator('button', { hasText: 'Dismiss' });
    if (await dismissButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await dismissButton.click();
      await page.waitForTimeout(500);
    }

    // Click the Kale sidebar tab (Kubeflow Pipelines Deployment Panel)
    const kaleTab = page.locator(
      '[title="Kubeflow Pipelines Deployment Panel"]',
    );
    await kaleTab.click();

    await page.waitForTimeout(1000);

    // Verify Enable Switch
    const toolbarContainer = page.locator('.toolbar.input-container');
    await expect(toolbarContainer).toBeVisible();

    const enableLabel = page.locator('.switch-label', { hasText: 'Enable' });
    await expect(enableLabel).toBeVisible({ timeout: 5000 });

    const enableSwitch = page.locator('input[name="enableKale"]');
    await expect(enableSwitch).toBeVisible({ timeout: 5000 });
    await expect(enableSwitch).not.toBeChecked();

    // Verify Empty State
    const emptyState = page.locator('.kale-empty-state-container');
    await expect(emptyState).toBeVisible({ timeout: 5000 });

    const title = page.locator('.kale-empty-state-title');
    await expect(title).toContainText(
      'Transform your Notebooks into Pipelines',
    );

    const featureItems = page.locator('.kale-empty-state-list-item');
    await expect(featureItems).toHaveCount(3);

    const githubLink = page.locator(
      'a[href="https://github.com/kubeflow/kale"]',
    );
    await expect(githubLink).toBeVisible();
  });
});

test.describe('Open a Notebook and Enable Kale', () => {
  test('should open a JupyterNotebook, enable Kale with the toggle, and verify UI components', async ({
    page,
  }) => {
    await page.goto('http://localhost:8889/lab', { waitUntil: 'load' });

    await page.waitForTimeout(3000);

    // Dismiss the Git dialog if it appears
    const dismissButton = page.locator('button', { hasText: 'Dismiss' });
    if (await dismissButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await dismissButton.click();
      await page.waitForTimeout(500);
    }

    // Click the Kale sidebar tab (Kubeflow Pipelines Deployment Panel)
    const kaleTab = page.locator(
      '[title="Kubeflow Pipelines Deployment Panel"]',
    );
    await kaleTab.click();

    await page.waitForTimeout(1000);

    // Create a new notebook
    const pythonNotebook = page
      .locator(
        '.jp-LauncherCard:has(.jp-LauncherCard-label[title="Python 3 (ipykernel)"])',
      )
      .first();
    await pythonNotebook.click();

    const notebookPanel = page.locator('.jp-NotebookPanel');
    await expect(notebookPanel).toBeVisible({ timeout: 5000 });

    // Enable Kale
    const enableSwitch = page.locator('input[name="enableKale"]');
    await enableSwitch.click();
    await expect(enableSwitch).toBeChecked();

    // Verify deploy button
    const compileButton = page.locator('button:has-text("Compile")');
    await expect(compileButton).toBeVisible();

    // Verify inline metadata
    const editButton = page.locator('.kale-editor-toggle');
    await expect(editButton).toBeVisible({ timeout: 5000 });
    await editButton.click();
    await page.waitForTimeout(500);
    const metadataEditor = page.locator('.kale-metadata-editor-wrapper');
    await expect(metadataEditor).toBeVisible({ timeout: 5000 });

    // Verify metadata editor fields
    await expect(page.locator('label:has-text("Cell type")')).toBeVisible();
    await expect(page.locator('label:has-text("Step name")')).toBeVisible();
    await expect(page.locator('label:has-text("Depends on")')).toBeVisible();
    await expect(page.locator('[aria-label="Configure step"]')).toBeVisible();
  });
});

test.describe('Trigger a Pipeline Compilation', () => {
  test(' should choose an option, deploy the action, and update the button', async ({
    page,
  }) => {
    await dismissKaleErrorDialogs(page);
    await acceptUnsavedChangesPrompt(page);
    await openKaleEnabledNotebook(page);

    // Wait for pipeline metadata to load so the deploy button is enabled
    const experimentName = page.getByLabel('Experiment Name');
    await expect(experimentName).toBeVisible({ timeout: 60000 });
    await experimentName.fill('test-experiment');
    await page.getByLabel('Pipeline Name').fill('test-pipeline');

    // The deploy button defaults to "Compile and Run"
    const deployButtonGroup = getDeployButtonGroup(page);
    const mainDeployButton = deployButtonGroup.locator('button').first();
    await expect(mainDeployButton).toBeEnabled({ timeout: 10000 });
    await expect(mainDeployButton).toHaveText('Compile and Run');

    // Open the three-dots menu
    await deployButtonGroup.locator('button').last().click();
    const menu = page.getByRole('menu');
    await expect(menu).toBeVisible({ timeout: 5000 });

    // Pick a new 'Compile' action
    await menu.getByRole('menuitem', { name: 'Compile and Save' }).click();

    // The deploy must start without a second click on the main button
    const deployProgress = page.locator('.deploy-progress');
    await expect(deployProgress).toBeVisible({ timeout: 10000 });
    await expect(
      deployProgress.locator('.deploy-progress-label', {
        hasText: 'Validating notebook...',
      }),
    ).toBeVisible();

    // The button must keep the newly chosen action as its new name
    await expect(mainDeployButton).toBeEnabled({ timeout: 60000 });
    await expect(mainDeployButton).toHaveText('Compile and Save');
  });
});

test.describe('Volumes panel — add a volume', () => {
  test('should add a volume and show it in the volumes list', async ({
    page,
  }) => {
    await openKaleEnabledNotebook(page);

    const dialog = await openAddVolumeDialog(page);
    await fillAndSubmitVolume(dialog, {
      name: 'raw-data',
      mountPoint: '/data',
    });

    await expect(
      page.locator('.kale-volume-name', { hasText: 'raw-data' }),
    ).toBeVisible();
    await expect(
      page.locator('.kale-volume-mount', { hasText: '/data' }),
    ).toBeVisible();
  });
});

test.describe('Volumes panel — validation', () => {
  test('should block a duplicate volume name', async ({ page }) => {
    await openKaleEnabledNotebook(page);

    const firstDialog = await openAddVolumeDialog(page);
    await fillAndSubmitVolume(firstDialog, {
      name: 'raw-data',
      mountPoint: '/data',
    });

    const dialog = await openAddVolumeDialog(page);
    await dialog.getByLabel('PVC name').fill('raw-data');
    await dialog.getByLabel('Mount path').fill('/other');

    await expect(
      dialog.getByText('This volume name is already used by another volume'),
    ).toBeVisible();
    await expect(
      dialog.getByRole('button', { name: 'Add volume', exact: true }),
    ).toBeDisabled();
  });

  test('should block a duplicate mount path', async ({ page }) => {
    await openKaleEnabledNotebook(page);

    const firstDialog = await openAddVolumeDialog(page);
    await fillAndSubmitVolume(firstDialog, {
      name: 'raw-data',
      mountPoint: '/data',
    });

    const dialog = await openAddVolumeDialog(page);
    await dialog.getByLabel('PVC name').fill('other-data');
    await dialog.getByLabel('Mount path').fill('/data');

    await expect(
      dialog.getByText('Mount path already used by another volume'),
    ).toBeVisible();
    await expect(
      dialog.getByRole('button', { name: 'Add volume', exact: true }),
    ).toBeDisabled();
  });

  test('should reject a mount path that is not absolute', async ({ page }) => {
    await openKaleEnabledNotebook(page);

    const dialog = await openAddVolumeDialog(page);
    await dialog.getByLabel('PVC name').fill('raw-data');
    await dialog.getByLabel('Mount path').fill('relative/path');

    await expect(
      dialog.getByText('Mount path must be an absolute path starting with "/"'),
    ).toBeVisible();
    await expect(
      dialog.getByRole('button', { name: 'Add volume', exact: true }),
    ).toBeDisabled();
  });

  test('should reject a mount path with path traversal segments', async ({
    page,
  }) => {
    await openKaleEnabledNotebook(page);

    const dialog = await openAddVolumeDialog(page);
    await dialog.getByLabel('PVC name').fill('raw-data');
    await dialog.getByLabel('Mount path').fill('/data/../secret');

    await expect(
      dialog.getByText('Mount path must not contain "." or ".." segments'),
    ).toBeVisible();
    await expect(
      dialog.getByRole('button', { name: 'Add volume', exact: true }),
    ).toBeDisabled();
  });

  test('should reject a mount path containing spaces', async ({ page }) => {
    await openKaleEnabledNotebook(page);

    const dialog = await openAddVolumeDialog(page);
    await dialog.getByLabel('PVC name').fill('raw-data');
    await dialog.getByLabel('Mount path').fill('/my data');

    await expect(
      dialog.getByText(
        'Mount path may only contain letters, numbers, ".", "_" and "-" in each segment',
      ),
    ).toBeVisible();
    await expect(
      dialog.getByRole('button', { name: 'Add volume', exact: true }),
    ).toBeDisabled();
  });
});

test.describe('Volumes panel — layout', () => {
  test('should always render the advanced settings notice below the Volumes section', async ({
    page,
  }) => {
    await openKaleEnabledNotebook(page);

    const volumesHeader = page.locator('.kale-header', { hasText: 'Volumes' });
    const settingsNotice = page.locator('.kale-settings-notice');
    await expect(volumesHeader).toBeVisible();
    await expect(settingsNotice).toBeVisible();

    const volumesBox = await volumesHeader.boundingBox();
    const noticeBox = await settingsNotice.boundingBox();
    expect(volumesBox).not.toBeNull();
    expect(noticeBox).not.toBeNull();
    expect(noticeBox!.y).toBeGreaterThan(volumesBox!.y);
  });

  test('should not stretch the "Select from notebook" button to the dialog width', async ({
    page,
  }) => {
    await openKaleEnabledNotebook(page);

    const dialog = await openAddVolumeDialog(page);
    const selectFromNotebookBtn = dialog.getByRole('button', {
      name: 'Select from notebook',
    });
    await expect(selectFromNotebookBtn).toBeVisible();

    const dialogBox = await dialog.boundingBox();
    const btnBox = await selectFromNotebookBtn.boundingBox();
    expect(dialogBox).not.toBeNull();
    expect(btnBox).not.toBeNull();
    expect(btnBox!.width).toBeLessThan(dialogBox!.width * 0.6);
  });
});

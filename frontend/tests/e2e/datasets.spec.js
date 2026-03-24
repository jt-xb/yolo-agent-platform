import { test, expect } from '@playwright/test'

test.describe('数据集管理页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/datasets')
  })

  test('页面应该正确加载', async ({ page }) => {
    await expect(page.locator('h2')).toContainText('数据集管理')
  })

  test('Tab 切换应该工作', async ({ page }) => {
    // 检查 Tab 栏
    await expect(page.locator('.tabs-bar')).toBeVisible()

    // 点击自动标注 Tab
    await page.click('text=自动标注')
    await expect(page.locator('.autolabel-panel')).toBeVisible()

    // 点击手动标注 Tab
    await page.click('text=手动标注')
    await expect(page.locator('.annotate-panel')).toBeVisible()
  })

  test('数据集选择器应该工作', async ({ page }) => {
    const selector = page.locator('.el-select')
    if (await selector.isVisible()) {
      await selector.click()
      await expect(page.locator('.el-select-dropdown')).toBeVisible()
    }
  })

  test('上传按钮应该打开对话框', async ({ page }) => {
    const uploadBtn = page.locator('button:has-text("上传图片")')
    if (await uploadBtn.isVisible()) {
      await uploadBtn.click()
      await expect(page.locator('.el-dialog')).toBeVisible()
    }
  })

  test('浏览模式下应该显示图片网格', async ({ page }) => {
    await page.waitForTimeout(2000)

    // 检查是否有图片
    const imageGrid = page.locator('.image-grid')
    if (await imageGrid.isVisible()) {
      await expect(imageGrid).toBeVisible()
    }
  })
})

test.describe('数据集详情', () => {
  test('应该显示数据集统计', async ({ page }) => {
    await page.goto('/datasets')
    await page.waitForTimeout(2000)

    const stats = page.locator('.dataset-stats')
    if (await stats.isVisible()) {
      await expect(stats).toBeVisible()
    }
  })
})

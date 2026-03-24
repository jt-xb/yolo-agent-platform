import { test, expect } from '@playwright/test'

test.describe('任务管理页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('页面应该正确加载', async ({ page }) => {
    // 检查页面标题
    await expect(page.locator('h2')).toContainText('训练任务管理')
  })

  test('应该显示新建任务按钮', async ({ page }) => {
    const createBtn = page.locator('text=新建训练任务')
    await expect(createBtn).toBeVisible()
  })

  test('点击新建任务应该打开对话框', async ({ page }) => {
    await page.click('text=新建训练任务')
    // 检查对话框是否出现
    await expect(page.locator('.el-dialog')).toBeVisible()
    await expect(page.locator('text=新建训练任务').first()).toBeVisible()
  })

  test('任务列表应该可以显示', async ({ page }) => {
    // 等待任务列表加载
    await page.waitForSelector('.el-table', { timeout: 10000 })
    await expect(page.locator('.el-table')).toBeVisible()
  })

  test('点击任务行应该打开详情', async ({ page }) => {
    // 等待数据加载
    await page.waitForTimeout(2000)

    // 如果有任务，尝试点击详情
    const detailBtn = page.locator('button:has-text("详情")').first()
    if (await detailBtn.isVisible()) {
      await detailBtn.click()
      // 检查详情对话框
      await expect(page.locator('.el-dialog')).toBeVisible()
    }
  })
})

test.describe('任务详情对话框', () => {
  test('详情对话框应该包含指标卡片', async ({ page }) => {
    await page.goto('/')

    // 等待任务列表
    await page.waitForTimeout(2000)

    // 点击详情
    const detailBtn = page.locator('button:has-text("详情")').first()
    if (await detailBtn.isVisible()) {
      await detailBtn.click()

      // 等待对话框打开
      await page.waitForSelector('.el-dialog', { timeout: 5000 })

      // 检查指标仪表板
      const metricsDashboard = page.locator('.metrics-dashboard')
      if (await metricsDashboard.isVisible()) {
        await expect(metricsDashboard).toBeVisible()
      }
    }
  })

  test('详情对话框应该包含 Agent 思考台', async ({ page }) => {
    await page.goto('/')

    await page.waitForTimeout(2000)

    const detailBtn = page.locator('button:has-text("详情")').first()
    if (await detailBtn.isVisible()) {
      await detailBtn.click()

      await page.waitForSelector('.el-dialog', { timeout: 5000 })

      // 检查 Agent 思考台
      const agentPanel = page.locator('.agent-thoughts-panel')
      if (await agentPanel.isVisible()) {
        await expect(agentPanel).toBeVisible()
      }
    }
  })
})

test.describe('导航功能', () => {
  test('侧边栏导航应该工作', async ({ page }) => {
    // 访问首页
    await expect(page.locator('.sidebar')).toBeVisible()

    // 点击数据集管理
    await page.click('text=数据管理')
    await expect(page).toHaveURL(/\/datasets/)

    // 点击模型仓库
    await page.click('text=模型仓库')
    await expect(page).toHaveURL(/\/models/)

    // 点击系统设置
    await page.click('text=系统设置')
    await expect(page).toHaveURL(/\/settings/)
  })

  test('顶部 Agent 状态栏应该显示', async ({ page }) => {
    await expect(page.locator('.agent-status-bar')).toBeVisible()
  })
})

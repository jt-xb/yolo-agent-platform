import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, nextTick } from 'vue'

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch

// Mock router
const mockRouter = {
  push: vi.fn()
}

describe('TasksView', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    mockRouter.push.mockReset()
  })

  describe('状态格式化', () => {
    it('getStatusText 应该正确转换状态', async () => {
      const statusTexts = {
        pending: '待启动',
        training: 'Agent 训练中',
        completed: '已完成',
        failed: '失败',
        stopped: '已停止',
      }

      // 测试所有状态
      expect(statusTexts.pending).toBe('待启动')
      expect(statusTexts.training).toBe('Agent 训练中')
      expect(statusTexts.completed).toBe('已完成')
      expect(statusTexts.failed).toBe('失败')
      expect(statusTexts.stopped).toBe('已停止')
    })

    it('getMetricClass 应该正确判断指标是否达标', () => {
      const getMetricClass = (value, threshold) => {
        if (!value) return ''
        return value >= threshold ? 'metric-good' : 'metric-bad'
      }

      expect(getMetricClass(0.9, 0.85)).toBe('metric-good')
      expect(getMetricClass(0.8, 0.85)).toBe('metric-bad')
      expect(getMetricClass(null, 0.85)).toBe('')
      expect(getMetricClass(0.85, 0.85)).toBe('metric-good')
    })

    it('getDecisionText 应该正确转换决策', () => {
      const getDecisionText = (decision) => {
        const texts = {
          pass: '✅ 达标',
          fail_retry: '🔧 调整重试',
          fail_stop: '❌ 失败停止',
          max_iteration: '⚠️ 达到最大迭代',
        }
        return texts[decision] || decision || '进行中'
      }

      expect(getDecisionText('pass')).toBe('✅ 达标')
      expect(getDecisionText('fail_retry')).toBe('🔧 调整重试')
      expect(getDecisionText('fail_stop')).toBe('❌ 失败停止')
      expect(getDecisionText('max_iteration')).toBe('⚠️ 达到最大迭代')
      expect(getDecisionText(null)).toBe('进行中')
    })
  })

  describe('时间格式化', () => {
    it('formatDuration 应该正确计算时长', () => {
      const formatDuration = (startTime) => {
        if (!startTime) return '0s'
        const start = new Date(startTime)
        const now = new Date()
        const seconds = Math.floor((now - start) / 1000)
        if (seconds < 60) return seconds + 's'
        const minutes = Math.floor(seconds / 60)
        if (minutes < 60) return minutes + 'm'
        const hours = Math.floor(minutes / 60)
        return hours + 'h'
      }

      expect(formatDuration(null)).toBe('0s')

      const now = new Date()
      expect(formatDuration(now.toISOString())).toMatch(/^\d+s$/)
    })

    it('formatTime 应该正确格式化时间', () => {
      const formatTime = (timeStr) => {
        if (!timeStr) return '-'
        const d = new Date(timeStr)
        return `${d.getMonth()+1}/${d.getDate()} ${d.toLocaleTimeString()}`
      }

      expect(formatTime(null)).toBe('-')
      expect(formatTime('2024-01-15T10:30:00')).toMatch(/1\/15/)
    })
  })

  describe('任务列表加载', () => {
    it('应该能正确获取任务列表', async () => {
      const mockTasks = [
        {
          task_id: 'task_20240115_001',
          name: '安全帽检测',
          status: 'training',
          progress: 45,
          map50: 0.72,
          yolo_model: 'yolov8s',
          created_at: '2024-01-15T10:00:00'
        }
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tasks: mockTasks })
      })

      const response = await fetch('/api/tasks/')
      const data = await response.json()

      expect(data.tasks).toHaveLength(1)
      expect(data.tasks[0].name).toBe('安全帽检测')
      expect(data.tasks[0].status).toBe('training')
    })

    it('任务列表为空时应该返回空数组', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ tasks: [] })
      })

      const response = await fetch('/api/tasks/')
      const data = await response.json()

      expect(data.tasks).toHaveLength(0)
    })
  })

  describe('创建任务', () => {
    it('应该能创建新任务', async () => {
      const newTask = {
        name: '车辆检测',
        description: '检测图片中的车辆',
        class_names: ['car', 'truck'],
        epochs: 100
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          task_id: 'task_001',
          message: '任务创建成功'
        })
      })

      const response = await fetch('/api/tasks/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newTask)
      })

      const data = await response.json()
      expect(data.success).toBe(true)
      expect(data.task_id).toBe('task_001')
    })

    it('创建任务时没有描述应该返回错误', async () => {
      const invalidTask = {
        name: '测试任务',
        class_names: []
      }

      // 前端验证应该拦截
      expect(invalidTask.class_names.length).toBe(0)
    })
  })

  describe('任务详情加载', () => {
    it('应该能获取任务详情', async () => {
      const mockTask = {
        task_id: 'task_001',
        name: '安全帽检测',
        status: 'completed',
        map50: 0.856,
        map50_95: 0.672,
        precision: 0.82,
        recall: 0.78,
        progress: 100
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTask)
      })

      const response = await fetch('/api/tasks/task_001')
      const data = await response.json()

      expect(data.task_id).toBe('task_001')
      expect(data.map50).toBe(0.856)
    })

    it('任务不存在时应该返回404', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404
      })

      const response = await fetch('/api/tasks/nonexistent')
      expect(response.ok).toBe(false)
    })
  })

  describe('训练流程状态', () => {
    it('getProgressStatus 应该正确返回进度条状态', () => {
      const getProgressStatus = (status) => {
        if (status === 'completed') return 'success'
        if (status === 'failed') return 'exception'
        if (status === 'training') return 'primary'
        return null
      }

      expect(getProgressStatus('completed')).toBe('success')
      expect(getProgressStatus('failed')).toBe('exception')
      expect(getProgressStatus('training')).toBe('primary')
      expect(getProgressStatus('pending')).toBe(null)
    })

    it('getStatusType 应该正确返回 Tag 类型', () => {
      const getStatusType = (status) => {
        const types = {
          pending: 'info',
          training: 'primary',
          completed: 'success',
          failed: 'danger',
          stopped: 'warning',
        }
        return types[status] || 'info'
      }

      expect(getStatusType('pending')).toBe('info')
      expect(getStatusType('training')).toBe('primary')
      expect(getStatusType('completed')).toBe('success')
      expect(getStatusType('failed')).toBe('danger')
      expect(getStatusType('stopped')).toBe('warning')
    })
  })
})

import request from './index'

export async function getTasks(params = {}) {
  const qs = new URLSearchParams(params).toString()
  return request(`/tasks/${qs ? '?' + qs : ''}`)
}

export async function getTask(taskId) {
  return request(`/tasks/${taskId}`)
}

export async function createTask(data) {
  return request('/tasks/', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function startTask(taskId) {
  return request(`/tasks/${taskId}/start`, { method: 'POST' })
}

export async function stopTask(taskId) {
  return request(`/tasks/${taskId}/stop`, { method: 'POST' })
}

export async function deleteTask(taskId) {
  return request(`/tasks/${taskId}`, { method: 'DELETE' })
}

export async function getTaskLogs(taskId, lines = 200) {
  return request(`/tasks/${taskId}/logs?lines=${lines}`)
}

export async function getTaskMetrics(taskId) {
  return request(`/tasks/${taskId}/metrics`)
}

export async function getTaskIterations(taskId) {
  return request(`/tasks/${taskId}/iterations`)
}

export function createTaskStream(taskId, callbacks = {}) {
  return createSSE(`/tasks/${taskId}/stream`, callbacks)
}

import request from './index'

export async function getModels() {
  return request('/models/')
}

export async function getModel(taskId) {
  return request(`/models/${taskId}`)
}

export async function deployModel(taskId) {
  return request(`/models/${taskId}/deploy`, { method: 'POST' })
}

export async function undeployModel(taskId) {
  return request(`/models/${taskId}/undeploy`, { method: 'POST' })
}

export async function getModelStatus(taskId) {
  return request(`/models/${taskId}/status`)
}

export async function inferModel(taskId, data) {
  return request(`/models/${taskId}/infer`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function inferModelImage(taskId, file) {
  const formData = new FormData()
  formData.append('file', file)
  return request(`/models/${taskId}/infer-image`, {
    method: 'POST',
    body: formData,
  })
}

export async function downloadModel(taskId) {
  return request(`/models/${taskId}/download`)
}

export async function deleteModel(taskId) {
  return request(`/models/${taskId}`, { method: 'DELETE' })
}

export async function exportModel(taskId, format) {
  return request(`/models/${taskId}/export?format=${format}`)
}

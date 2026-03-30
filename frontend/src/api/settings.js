import request from './index'

export async function getLlmConfig() {
  return request('/api/settings/llm')
}

export async function saveLlmConfig(data) {
  return request('/api/settings/llm', {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function testLlmConnection(data) {
  return request('/api/settings/llm/test', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

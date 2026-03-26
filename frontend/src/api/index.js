const BASE_URL = '/api'

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  }

  // Don't set Content-Type for FormData
  if (options.body instanceof FormData) {
    delete config.headers['Content-Type']
  }

  try {
    const res = await fetch(url, config)
    const data = await res.json()

    if (!res.ok) {
      throw new Error(data.message || data.detail || `HTTP ${res.status}`)
    }

    return data
  } catch (err) {
    if (err.message === 'Failed to fetch') {
      throw new Error('网络连接失败，请检查后端服务')
    }
    throw err
  }
}

export function createSSE(path, callbacks = {}) {
  const url = `${BASE_URL}${path}`
  const es = new EventSource(url)

  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      callbacks.onMessage?.(data)
    } catch {}
  }

  es.onerror = (e) => {
    callbacks.onError?.(e)
    es.close()
  }

  return {
    close: () => es.close(),
  }
}

export default request

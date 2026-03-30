const BASE_URL = import.meta.env.VITE_API_BASE || '/api'

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    method: options.method || 'GET',
  }

  // Don't set Content-Type for FormData and DELETE requests
  if (options.body instanceof FormData) {
    delete config.headers['Content-Type']
  }

  // Only add body for non-DELETE requests
  if (options.method !== 'DELETE' && options.body) {
    config.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body)
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
  let url
  try {
    url = `${BASE_URL}${path}`
  } catch (err) {
    callbacks.onError?.(err)
    return { close: () => {} }
  }

  let es
  try {
    es = new EventSource(url)
  } catch (err) {
    callbacks.onError?.(err)
    return { close: () => {} }
  }

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

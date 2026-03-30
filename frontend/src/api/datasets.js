import request, { createSSE } from './index'

export async function getDatasets() {
  return request('/datasets/all')
}

export async function getDataset(datasetId) {
  return request(`/datasets/${datasetId}`)
}

export async function getDatasetImages(datasetId, params = {}) {
  const qs = new URLSearchParams(params).toString()
  return request(`/datasets/${datasetId}/images${qs ? '?' + qs : ''}`)
}

export async function getDemoDataset() {
  return request('/datasets/demo')
}

export async function createDataset(name) {
  return request('/datasets/create', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export async function deleteDataset(datasetId) {
  return request(`/datasets/${datasetId}`, { method: 'DELETE' })
}

export async function uploadImages(datasetId, files) {
  const formData = new FormData()
  files.forEach(f => formData.append('files', f))
  return request(`/datasets/upload-images?dataset_id=${datasetId}`, {
    method: 'POST',
    body: formData,
  })
}

export async function deleteImage(imageId) {
  return request(`/datasets/image/${imageId}`, { method: 'DELETE' })
}

export async function saveImageAnnotations(imageId, boxes) {
  return request(`/datasets/image/${imageId}/annotations`, {
    method: 'POST',
    body: JSON.stringify(boxes),
  })
}

export async function autoLabelDinoSam(data) {
  return request('/datasets/dino-sam-auto-label', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getAutoLabelInfo() {
  return request('/datasets/auto-label-info')
}

export async function importDataset(data) {
  return request('/datasets/import', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function extractVideoFrames(datasetId, file, frameInterval = 5, maxFrames = 200, split = 'train') {
  const formData = new FormData()
  formData.append('dataset_id', datasetId)
  formData.append('file', file)
  formData.append('frame_interval', frameInterval)
  formData.append('max_frames', maxFrames)
  formData.append('split', split)
  return request('/datasets/video-extract', {
    method: 'POST',
    body: formData,
  })
}

export async function getDatasetMeta(datasetId) {
  return request(`/datasets/${datasetId}/meta`)
}

export async function updateDatasetMeta(datasetId, meta) {
  return request(`/datasets/${datasetId}/meta`, {
    method: 'PUT',
    body: JSON.stringify(meta),
  })
}

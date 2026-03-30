import request from './index'

export async function lsConnect(url, apiKey) {
  return request('/label-studio/connect', {
    method: 'POST',
    body: JSON.stringify({ url, api_key: apiKey }),
  })
}

export async function lsStatus() {
  return request('/label-studio/status')
}

export async function lsListProjects() {
  return request('/label-studio/projects')
}

export async function lsCreateProject(data) {
  return request('/label-studio/projects', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function lsGetProject(projectId) {
  return request(`/label-studio/projects/${projectId}`)
}

export async function lsSyncDataset(data) {
  return request('/label-studio/sync-dataset', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function lsExportAnnotations(projectId, data) {
  return request(`/label-studio/projects/${projectId}/export`, {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, ...data }),
  })
}

export async function lsOpenProject(projectId) {
  return request(`/label-studio/open/${projectId}`)
}

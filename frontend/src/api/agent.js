import request from './index'

/**
 * AI Agent 相关 API
 * 用于 Agent 参数推荐和训练参数智能建议
 */

/**
 * 获取 Agent 状态
 */
export async function getAgentStatus() {
  return request('/agent/status')
}

/**
 * Agent 聊天 - 获取参数推荐
 * @param {string} message - 用户描述
 * @param {string} context - 上下文（如数据集信息）
 */
export async function agentChat(message, context = {}) {
  return request('/agent/chat', {
    method: 'POST',
    body: JSON.stringify({ message, context }),
  })
}

/**
 * 根据任务描述推荐训练参数
 * @param {Object} params
 * @param {string} params.description - 任务描述（如：检测安全帽）
 * @param {string} params.datasetId - 数据集 ID
 * @param {number} params.imageCount - 图片数量
 * @param {string[]} params.classNames - 类别列表
 */
export async function recommendTrainingParams(params) {
  return request('/agent/recommend', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/**
 * 获取训练建议
 * @param {string} taskId - 任务 ID
 */
export async function getTrainingAdvice(taskId) {
  return request(`/agent/advice/${taskId}`)
}

/**
 * 评估模型质量
 * @param {string} modelPath - 模型路径
 * @param {Object} metrics - 评估指标
 */
export async function evaluateModelQuality(modelPath, metrics) {
  return request('/agent/evaluate', {
    method: 'POST',
    body: JSON.stringify({ model_path: modelPath, metrics }),
  })
}

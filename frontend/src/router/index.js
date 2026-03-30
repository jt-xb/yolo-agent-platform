import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/tasks',
    },
    {
      path: '/tasks',
      name: 'Tasks',
      component: () => import('../views/TasksView.vue'),
    },
    {
      path: '/datasets',
      name: 'Datasets',
      component: () => import('../views/DatasetsView.vue'),
    },
    {
      path: '/models',
      name: 'Models',
      component: () => import('../views/ModelsView.vue'),
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('../views/SettingsView.vue'),
    },
  ],
})

export default router

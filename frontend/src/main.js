import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import {
  ElContainer, ElHeader, ElAside, ElMain,
  ElButton, ElMenu, ElMenuItem, ElMenuItemGroup,
  ElTable, ElTableColumn, ElDialog, ElForm, ElFormItem,
  ElInput, ElInputNumber, ElSelect, ElOption, ElTag,
  ElProgress, ElMessage, ElMessageBox, ElAlert, ElCard,
  ElRow, ElCol, ElDescriptions, ElDescriptionsItem,
  ElCollapse, ElCollapseItem, ElRadioGroup, ElRadioButton,
  ElSlider, ElSwitch, ElUpload, ElIcon, ElDivider, ElEmpty,
  ElBadge, ElTabs, ElTabPane, ElLoading, ElImage, ElScrollbar,
  ElDropdown, ElDropdownMenu, ElDropdownItem, ElTooltip,
} from 'element-plus'
import router from './router'
import App from './App.vue'

import './styles/variables.css'
import './styles/reset.css'
import './styles/transitions.css'

const app = createApp(App)

app.use(ElementPlus)
app.use(router)

app.mount('#app')

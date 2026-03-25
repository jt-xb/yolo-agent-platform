import { createApp } from 'vue'
import {
  ElContainer,
  ElHeader,
  ElAside,
  ElMain,
  ElButton,
  ElMenu,
  ElMenuItem,
  ElTable,
  ElTableColumn,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElSelect,
  ElOption,
  ElTag,
  ElProgress,
  ElMessage,
  ElMessageBox,
  ElAlert,
  ElCard,
  ElRow,
  ElCol,
  ElDescriptions,
  ElDescriptionsItem,
  ElCollapse,
  ElCollapseItem,
  ElRadioGroup,
  ElRadioButton,
  ElSlider,
  ElSwitch,
  ElUpload,
  ElIcon,
  ElDivider,
  ElEmpty,
  ElBadge,
  ElTabs,
  ElTabPane,
  ElLoading,
} from 'element-plus'
import router from './router'
import App from './App.vue'

const app = createApp(App)

app.use(ElContainer)
app.use(ElHeader)
app.use(ElAside)
app.use(ElMain)
app.use(ElButton)
app.use(ElMenu)
app.use(ElMenuItem)
app.use(ElTable)
app.use(ElTableColumn)
app.use(ElDialog)
app.use(ElForm)
app.use(ElFormItem)
app.use(ElInput)
app.use(ElInputNumber)
app.use(ElSelect)
app.use(ElOption)
app.use(ElTag)
app.use(ElProgress)
app.use(ElMessage)
app.use(ElMessageBox)
app.use(ElAlert)
app.use(ElCard)
app.use(ElRow)
app.use(ElCol)
app.use(ElDescriptions)
app.use(ElDescriptionsItem)
app.use(ElCollapse)
app.use(ElCollapseItem)
app.use(ElRadioGroup)
app.use(ElRadioButton)
app.use(ElSlider)
app.use(ElSwitch)
app.use(ElUpload)
app.use(ElIcon)
app.use(ElDivider)
app.use(ElEmpty)
app.use(ElBadge)
app.use(ElTabs)
app.use(ElTabPane)
app.use(ElLoading)

app.use(router)

app.mount('#app')

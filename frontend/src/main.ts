import {createApp} from 'vue'
import {createPinia} from 'pinia'
import {createRouter,createWebHistory} from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'
import Workspace from './views/Workspace.vue'
const router=createRouter({history:createWebHistory(),routes:[{path:'/:page?',component:Workspace},{path:'/products/:id',component:Workspace}]})
createApp(App).use(createPinia()).use(router).use(ElementPlus).mount('#app')

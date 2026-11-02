import {createApp} from 'vue'
import {createPinia} from 'pinia'
import {createRouter,createWebHistory} from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import './briefing.css'
import App from './App.vue'
import Workspace from './views/Workspace.vue'
import CompanyIntelligence from './views/CompanyIntelligence.vue'
import Coverage from './views/Coverage.vue'
import Home from './views/Home.vue'
const router=createRouter({history:createWebHistory(),routes:[{path:'/',redirect:'/home'},{path:'/home',component:Home},{path:'/coverage',component:Coverage},...['/companies','/feed','/tracker','/industry','/companies/:id'].map(path=>({path,component:CompanyIntelligence})),{path:'/:page?',component:Workspace},{path:'/products/:id',component:Workspace}]})
createApp(App).use(createPinia()).use(router).use(ElementPlus).mount('#app')

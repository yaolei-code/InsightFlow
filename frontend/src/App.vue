<script setup lang="ts">
import {useRoute} from 'vue-router'
import {DataAnalysis,Box,Grid,Clock,Document,Setting,Connection} from '@element-plus/icons-vue'
const route=useRoute()
const links=[['companies','企业情报',Box],['feed','行业动态',Clock],['tracker','进展追踪',DataAnalysis],['industry','行业技术地图',Grid],['dashboard','研究总览',DataAnalysis],['products','产品与数据源',Box],['comparison','产品能力对比',Grid],['timeline','产品变化',Clock],['reports','研究报告',Document],['tasks','任务与设置',Setting]]
</script>
<template>
 <div class="shell"><aside><router-link to="/dashboard" class="brand"><span class="brand-icon">iF</span>InsightFlow<span class="version">BETA</span></router-link><div class="workspace-label">RESEARCH WORKSPACE</div><nav><router-link v-for="[path,label,icon] in links" :key="String(path)" :to="'/'+path" :class="{selected:route.path.includes(String(path))||(path==='dashboard'&&route.path==='/')}"><el-icon><component :is="icon"/></el-icon>{{label}}</router-link></nav><div class="sidebar-bottom"><el-icon><Connection/></el-icon><strong>Evidence first.</strong><p>让每一个产品判断<br>都有据可循。</p><span class="tiny">INSIGHTFLOW / 01</span></div></aside><section class="main-shell"><header><span>工作空间 <b>/</b> 具身智能研究</span><span class="header-right"><i class="green-dot"/> 本地研究环境 <span class="avatar">IF</span></span></header><main><router-view/></main><footer>InsightFlow · AI-Powered Competitive Intelligence <span>公开来源 · 可追溯证据 · 审慎推断</span></footer></section></div>
</template>

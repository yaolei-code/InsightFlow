<script setup lang="ts">
import {onMounted,onUnmounted,ref,watch} from 'vue'
import {get} from '../api'
import ReportPreview from './ReportPreview.vue'
const props=defineProps<{id:number|null}>(),run=ref<any>(null),report=ref<any>(null)
async function load(){if(!props.id)return;run.value=await get('/workspace/research/'+props.id);if(run.value.report_id)report.value=await get('/reports/'+run.value.report_id)}
let timer:ReturnType<typeof setInterval>
onMounted(()=>{load();timer=setInterval(()=>{if(run.value&&['queued','running'].includes(run.value.status))load()},3000)})
watch(()=>props.id,()=>{report.value=null;load()});onUnmounted(()=>clearInterval(timer))
</script>
<template><section v-if="run" class="panel"><h2>研究 #{{run.id}} · {{run.status}}</h2><p>{{run.user_query}}</p><p v-for="(step,i) in run.trace" :key="i">{{step.at}} · {{step.tool}}：{{step.summary}}</p><p>{{run.summary}} {{run.stop_reason}}</p><p>请求 {{run.usage.requests||0}} 次 · {{run.usage.total_tokens||0}} tokens</p><el-collapse v-if="report"><el-collapse-item title="研究报告与证据引用" name="report"><ReportPreview :report="report"/></el-collapse-item></el-collapse></section></template>

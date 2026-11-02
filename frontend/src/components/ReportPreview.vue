<script setup lang="ts">
import {computed} from 'vue'
import {marked} from 'marked'
import DOMPurify from 'dompurify'
import {ElMessage} from 'element-plus'
const props=defineProps<{report:any}>()
const html=computed(()=>DOMPurify.sanitize(marked.parse(props.report?.markdown||'') as string))
function download(){const url=URL.createObjectURL(new Blob([props.report.markdown],{type:'text/markdown;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='InsightFlow-report.md';a.click();URL.revokeObjectURL(url)}
async function copy(){try{await navigator.clipboard.writeText(props.report.markdown);ElMessage.success('已复制')}catch{ElMessage.error('无法访问剪贴板，请下载 Markdown')}}
</script>
<template><div class="report-preview"><div class="toolbar"><el-button @click="download">下载 Markdown</el-button><el-button @click="copy">复制报告</el-button></div><article v-html="html"/></div></template>

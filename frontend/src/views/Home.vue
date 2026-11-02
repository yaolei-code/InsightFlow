<script setup lang="ts">
import {computed,onMounted,ref} from 'vue'
import {get} from '../api'
import {questions,questionMatches,withinWindow} from '../intelligence'
const events=ref<any[]>([]),companies=ref<any[]>([]),loading=ref(false),failed=ref(false)
const days=ref(30),active=ref('releases'),independent=ref(false),companyQuery=ref(''),page=ref(1),evidence=ref<any>(null),drawer=ref(false)
const names=(id:number)=>companies.value.find(c=>c.id===id)?.name||'企业 '+id
const stageLabels:Record<string,string>={research:'研究',prototype:'原型',demonstration:'演示',pilot:'客户试点',commercial_deployment:'商业部署',scaled_production:'规模生产',unknown:'阶段未知'}
const levels:Record<string,string>={company_claim:'企业自述',technical_artifact:'技术产物',independent_verification:'独立验证',customer_confirmation:'客户确认'}
const scoped=computed(()=>events.value.filter(e=>withinWindow(e,days.value)&&(!independent.value||['independent_verification','customer_confirmation'].includes(e.evidence_level))))
const unknownDates=computed(()=>events.value.filter(e=>!e.occurred_at&&!e.published_at).length)
const selected=computed(()=>scoped.value.filter(e=>questionMatches(e,active.value)&&names(e.company_id).toLowerCase().includes(companyQuery.value.toLowerCase())).sort((a,b)=>(b.occurred_at||b.published_at||'').localeCompare(a.occurred_at||a.published_at||'')))
const visible=computed(()=>selected.value.slice((page.value-1)*10,page.value*10))
const companyCount=(id:string)=>new Set(scoped.value.filter(e=>questionMatches(e,id)).map(e=>e.company_id)).size
async function load(){loading.value=true;failed.value=false;try{companies.value=await get('/companies?limit=200');const all:any[]=[];for(let offset=0;;offset+=200){const rows=await get('/progress-events?limit=200&offset='+offset);all.push(...rows);if(rows.length<200)break}events.value=[...new Map(all.map(e=>[e.id,e])).values()]}catch{failed.value=true}finally{loading.value=false}}
async function showEvidence(e:any){evidence.value=await get('/event-evidence/'+e.evidence_ids[0]);drawer.value=true}
onMounted(load)
</script>
<template><div v-loading="loading"><div class="page-heading"><div><div class="eyebrow">INSIGHTFLOW / INDUSTRY BRIEFING</div><h1>今天，你想了解什么？</h1><p>从行业问题出发，找到公司进展与原始证据。</p></div><el-button @click="load">刷新情报</el-button></div><el-alert v-if="failed" title="情报加载失败，请检查服务后刷新" type="error"/>
<div class="briefing-controls"><el-radio-group v-model="days" @change="page=1"><el-radio-button :value="7">最近7天</el-radio-button><el-radio-button :value="30">最近30天</el-radio-button><el-radio-button :value="0">全部资料</el-radio-button></el-radio-group><el-switch v-model="independent" active-text="只看独立验证 / 客户确认" @change="page=1"/></div><p class="muted">按事件日期优先、文章日期其次筛选；日期未知的 {{unknownDates}} 条仅在“全部资料”展示。数量是来源记录数，可能包含重复报道。</p>
<div class="question-grid"><button v-for="(q,index) in questions" :key="q.id" class="question-card" :class="{active:active===q.id}" @click="active=q.id;page=1"><span class="eyebrow">0{{index+1}} / KEY QUESTION</span><h2>{{q.title}}</h2><p>{{q.description}}</p><div><strong>{{companyCount(q.id)}}</strong> 家企业 <span>{{scoped.filter(e=>questionMatches(e,q.id)).length}} 条记录 ↗</span></div></button></div>
<section class="panel"><div class="section-heading"><div><h2>{{questions.find(q=>q.id===active)?.title}}</h2><p style="margin:8px 0 0">依据已保存的公开资料整理；企业披露不等于独立证实。</p></div><el-input v-model="companyQuery" placeholder="在结果中搜索企业" clearable style="max-width:240px" @input="page=1"/></div><div class="briefing-event" v-for="e in visible" :key="e.id"><div><router-link :to="'/companies/'+e.company_id">{{names(e.company_id)}}</router-link><span class="muted">{{e.occurred_at||e.published_at||'日期未知'}}</span></div><h3>{{e.title}}</h3><p>{{e.description}}</p><div class="briefing-event-footer"><span class="pill">{{stageLabels[e.progress_stage]||e.progress_stage}}</span><span class="pill">{{levels[e.evidence_level]||e.evidence_level}}</span><el-button link @click="showEvidence(e)">查看原始证据 ↗</el-button></div></div><el-empty v-if="!selected.length" description="当前资料没有匹配记录，不代表行业没有进展。"><el-button v-if="days!==0" @click="days=0;page=1">查看全部时间资料</el-button></el-empty><el-pagination v-model:current-page="page" :page-size="10" :total="selected.length" layout="prev,pager,next,total"/></section>
<div class="briefing-shortcuts"><router-link to="/industry"><strong>想比较具体公司？ →</strong><p>在精简地图中搜索企业、选择方向，最多对比4家。</p></router-link><router-link to="/coverage"><strong>想追踪更多公开资料？ →</strong><p>发现与自动处理新文章，持续补充信息覆盖。</p></router-link></div>
<el-drawer v-model="drawer" title="这条信息的依据" size="min(700px,95vw)"><template v-if="evidence"><span class="pill">{{levels[evidence.evidence_level]||evidence.evidence_level}}</span><blockquote>{{evidence.evidence_text}}</blockquote><a :href="evidence.source_url" target="_blank" rel="noopener noreferrer">打开原始来源 ↗</a><p>Snapshot #{{evidence.snapshot_id}} · {{evidence.created_at}}</p><p>原文匹配表示引用存在，不等于对企业声明的独立验证。</p></template></el-drawer>
</div></template>

export const questions=[
 {id:'releases',title:'最近发布了哪些模型或产品？',description:'查看模型、产品与开源发布记录',types:['model_release','product_release','open_source_release']},
 {id:'demos',title:'哪些公司展示了真机能力？',description:'演示记录与实际部署分开查看',types:['robot_demo'],stage:'demonstration'},
 {id:'pilots',title:'谁披露了客户试点？',description:'关注试点对象、任务与原始来源',types:['pilot_deployment'],stage:'pilot'},
 {id:'commercial',title:'谁披露了商业部署或量产？',description:'核对商业部署与规模生产证据',types:['commercial_deployment','mass_production'],stages:['commercial_deployment','scaled_production']},
 {id:'research',title:'有哪些值得关注的技术成果？',description:'技术、模型与评测结果',types:['technology_breakthrough','benchmark_result','model_release']},
 {id:'business',title:'有哪些融资和合作动态？',description:'合作公告不等于完成交付',types:['funding','customer_cooperation']}
] as const

export function questionMatches(event:any,id:string):boolean{
 const question:any=questions.find(q=>q.id===id)
 if(!question)return false
 if(id==='pilots')return event.progress_stage==='pilot'
 if(id==='commercial')return ['commercial_deployment','scaled_production'].includes(event.progress_stage)
 if(id==='demos')return event.event_type==='robot_demo'||event.progress_stage==='demonstration'
 return question.types.includes(event.event_type)
}

export function withinWindow(event:any,days:number,now=new Date()):boolean{
 if(!days)return true
 const value=event.occurred_at||event.published_at
 if(!value)return false
 const date=Date.parse(value.slice(0,10)+'T00:00:00Z')
 const today=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate())
 return Number.isFinite(date)&&date<=today&&date>=today-(days-1)*86400000
}

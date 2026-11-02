// Browsing categories group source tags; they are not capability ratings.
const groups:[string,RegExp][]=[
 ['VLA 与机器人模型',/\bvla\b|vision.language.action|机器人.*模型|robot.*model|基础模型|foundation model|helix|π0|pi0/i],
 ['世界模型',/世界模型|world model/i],['数据与遥操作',/数据|dataset|data collection|teleop|遥操作/i],
 ['仿真与训练',/仿真|simulation|训练|training|learning|强化学习/i],['感知与操作',/感知|perception|操作|manipulation|灵巧|dexter|抓取|grasp/i],
 ['机器人本体',/人形|humanoid|四足|quadruped|本体|机器人硬件/i],['部署与交付',/部署|deployment|交付|commercial|试点|pilot|工厂|factory|production|量产/i],
 ['评测与评估',/评测|评估|benchmark|evaluation/i],['开源与开发工具',/开源|open.source|框架|framework|sdk|开发平台|developer/i],
 ['融资与合作',/融资|funding|合作|cooperation|partnership/i]]
export function directions(event:any):string[]{
 const text=(event.capability_tags||[]).join(' ')
 const result=groups.filter(([,pattern])=>pattern.test(text)).map(([name])=>name)
 return result.length?result:['其他公开进展']
}

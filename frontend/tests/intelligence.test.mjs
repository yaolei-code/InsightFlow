import test from 'node:test'
import assert from 'node:assert/strict'
import {withinWindow,questionMatches} from '../src/intelligence.ts'
const now=new Date('2026-11-02T10:00:00Z')
test('recent window excludes unknown and future dates',()=>{
 assert.equal(withinWindow({published_at:null},7,now),false)
 assert.equal(withinWindow({published_at:'2026-11-03'},7,now),false)
 assert.equal(withinWindow({published_at:'2026-10-27'},7,now),true)
 assert.equal(withinWindow({published_at:'2026-10-26'},7,now),false)
})
test('all time shows unknown dates without calling them recent',()=>assert.equal(withinWindow({},0,now),true))
test('actual event date takes priority over article date',()=>assert.equal(withinWindow({occurred_at:'2025-01-01',published_at:'2026-11-02'},30,now),false))
test('demo is not pilot or commercial deployment',()=>{
 const event={event_type:'robot_demo',progress_stage:'demonstration'}
 assert.equal(questionMatches(event,'demos'),true)
 assert.equal(questionMatches(event,'pilots'),false)
 assert.equal(questionMatches(event,'commercial'),false)
})
test('planned deployment with unknown stage is not a completed deployment',()=>assert.equal(questionMatches({event_type:'commercial_deployment',progress_stage:'unknown'},'commercial'),false))
test('commercial and production stay in deployment question',()=>assert.equal(questionMatches({event_type:'other',progress_stage:'scaled_production'},'commercial'),true))

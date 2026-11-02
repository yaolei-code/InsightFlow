import {defineStore} from 'pinia'
import {ref} from 'vue'
import {get} from './api'
export const useWorkspace=defineStore('workspace',()=>{
  const health=ref<any>({}), products=ref<any[]>([]), sources=ref<any[]>([])
  async function refresh(){[health.value,products.value,sources.value]=await Promise.all([get('/health'),get('/products?limit=200'),get('/sources?limit=200')])}
  return {health,products,sources,refresh}
})

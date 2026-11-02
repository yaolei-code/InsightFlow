import axios from 'axios'
import {ElMessage} from 'element-plus'
export const api=axios.create({baseURL:'/api',timeout:30000})
api.interceptors.response.use(r=>r,e=>{ElMessage.error(e.response?.data?.error?.message||'无法连接服务器');return Promise.reject(e)})
export const get=async(path:string)=>(await api.get(path)).data
export const post=async(path:string,data:unknown={})=>(await api.post(path,data)).data

import type * as T from './types';
const taskKeys:(keyof T.TaskFields)[]=['title','topic','context','need','users','data_materials','constraints','expected_result','success_criteria','contact','consultation'];
const taskPayload=(fields:Partial<T.TaskFields>)=>Object.fromEntries(taskKeys.filter(key=>typeof fields[key]==='string').map(key=>[key,fields[key]]));
export const API_BASE_URL=(import.meta.env.VITE_API_BASE_URL??'').replace(/\/+$/,'');
export class ApiError extends Error {
  readonly status:number;readonly code:string;readonly fieldErrors:T.FieldErrors;
  constructor(status:number,payload:T.ErrorResponse){super(payload.message);this.name='ApiError';this.status=status;this.code=payload.code;this.fieldErrors=payload.field_errors??{};}
}
export function createApiClient({getCsrf=()=>'',onUnauthorized=()=>{}}:{getCsrf?:()=>string;onUnauthorized?:()=>void}={}){
  async function request<R>(path:string,method='GET',body?:unknown,ai=false):Promise<R>{
    const headers:Record<string,string>={Accept:'application/json'};
    if(body!==undefined)headers['Content-Type']='application/json';
    if(method!=='GET'&&getCsrf())headers['X-CSRF-Token']=getCsrf();
    let response:Response;
    try{response=await fetch(API_BASE_URL+path,{method,headers,credentials:'include',body:body===undefined?undefined:JSON.stringify(body)});}
    catch{throw new ApiError(0,{code:'network_error',message:'Нет связи с сервером. Проверьте подключение и повторите.'});}
    let data:unknown;
    try{data=response.status===204?undefined:await response.json();}catch{throw new ApiError(response.status,{code:'invalid_response',message:'Сервер вернул непонятный ответ. Повторите позже.'});}
    if(!response.ok){
      if(response.status===401&&!['/api/auth/login','/api/auth/register','/api/auth/password'].includes(path))onUnauthorized();
      throw new ApiError(response.status,data as T.ErrorResponse);
    }
    const source=response.headers.get('X-AI-Source');
    return(ai?{data,source:source==='openai'||source==='fallback'?source:null}:data)as R;
  }
  const id=encodeURIComponent;
  return {
    session:()=>request<T.Session>('/api/auth/session'),
    register:(body:T.Registration)=>request<T.Session>('/api/auth/register','POST',body),
    login:(body:{email:string;password:string})=>request<T.Session>('/api/auth/login','POST',body),
    logout:()=>request<void>('/api/auth/logout','POST'),
    changePassword:(body:{current_password:string;new_password:string})=>request<void>('/api/auth/password','POST',body),
    updateUser:(name:string)=>request<T.Account>('/api/users/me','PATCH',{name}),
    profile:(profileId:string)=>request<T.Profile>('/api/profiles/'+id(profileId)),
    updateProfile:(fields:T.ProfilePatch)=>request<T.Profile>('/api/profiles/me','PATCH',fields),
    createTask:(fields:Partial<T.TaskFields>)=>request<T.TaskResponse>('/api/tasks','POST',taskPayload(fields)),
    task:(taskId:string)=>request<T.TaskResponse>('/api/tasks/'+id(taskId)),
    updateTask:(taskId:string,fields:Partial<T.TaskFields>)=>request<T.TaskResponse>('/api/tasks/'+id(taskId),'PATCH',taskPayload(fields)),
    questions:(taskId:string)=>request<T.AiResult<T.QuestionResponse>>('/api/tasks/'+id(taskId)+'/questions','POST',undefined,true),
    composeTask:(taskId:string,answers:T.Answer[])=>request<T.AiResult<T.TaskResponse>>('/api/tasks/'+id(taskId)+'/compose','POST',{answers},true),
    confirmTask:(taskId:string)=>request<T.TaskResponse>('/api/tasks/'+id(taskId)+'/confirm','POST'),
    publishTask:(taskId:string)=>request<T.TaskResponse>('/api/tasks/'+id(taskId)+'/publish','POST'),
    catalog:(query:{topic?:string;level?:T.RatingLevel}={})=>request<T.CatalogResponse>('/api/tasks?'+new URLSearchParams(query)),
    businessTasks:()=>request<T.CatalogResponse>('/api/business/tasks'),
    createProposal:(taskId:string,body:T.ProposalCreate)=>request<T.ProposalResponse>('/api/tasks/'+id(taskId)+'/proposals','POST',body),
    proposals:(taskId:string)=>request<T.ProposalListResponse>('/api/tasks/'+id(taskId)+'/proposals'),
    decideProposal:(proposalId:string,decision:T.ProposalDecision)=>request<T.ProposalResponse>('/api/proposals/'+id(proposalId)+'/decision','POST',{decision}),
    teamProposals:()=>request<T.TeamProposalList>('/api/team/proposals'),
    createMilestone:(proposalId:string,body:T.MilestoneCreate)=>request<T.MilestoneResponse>('/api/proposals/'+id(proposalId)+'/milestone','POST',body),
    reviewMilestone:(milestoneId:string,decision:T.MilestoneDecision,comment:string)=>request<T.MilestoneResponse>('/api/milestones/'+id(milestoneId)+'/review','POST',{decision,comment}),
  };
}
export type ApiClient=ReturnType<typeof createApiClient>;

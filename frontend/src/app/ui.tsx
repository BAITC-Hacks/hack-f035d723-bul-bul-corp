import {useEffect,useRef,useState,type ReactNode} from 'react';
import {Link} from 'react-router-dom';
import {ApiError} from '../api/client';
import type {Profile,Rating,TaskFields} from '../api/types';
import {useDemoSession} from './DemoSession';
export const fields:{key:keyof TaskFields;label:string;hint:string}[]=[
 {key:'title',label:'Название',hint:'Маршрутизация обращений клиентов'},
 {key:'topic',label:'Тема',hint:'Например, поддержка клиентов'},
 {key:'context',label:'Контекст',hint:'Как устроен процесс сейчас?'},
 {key:'need',label:'Потребность',hint:'Что нужно изменить?'},
 {key:'users',label:'Пользователи',hint:'Кто будет работать с решением?'},
 {key:'data_materials',label:'Данные и материалы',hint:'Какие данные доступны и в каком формате?'},
 {key:'constraints',label:'Ограничения',hint:'Сроки, доступы, бюджет, технологии'},
 {key:'expected_result',label:'Ожидаемый результат',hint:'Что команда должна передать?'},
 {key:'success_criteria',label:'Критерии успеха',hint:'Например, точность классификации не менее 90%'},
 {key:'contact',label:'Контакт',hint:'Email, телефон или @имя'},
 {key:'consultation',label:'Формат взаимодействия',hint:'Например, еженедельный созвон и обратная связь по почте'}
];
export const emptyFields=Object.fromEntries(fields.map(f=>[f.key,'']))as unknown as TaskFields;
export const statusLabels={pending:'На рассмотрении',selected:'Выбрано',rejected:'Отклонено',submitted:'На проверке',confirmed:'Подтверждено',changes_requested:'Нужна доработка'};
export function message(e:unknown){return e instanceof Error?e.message:'Не удалось выполнить действие. Повторите.';}
export function ErrorNote({text}:{text:string|null}){return text?<div className="notice error" role="alert">{text}</div>:null;}
export function Loading(){return <div className="loading" role="status">Загружаем данные…</div>;}
export function useAction(){const [busy,setBusy]=useState(false);const [error,setError]=useState<string|null>(null);const lock=useRef(false);
 async function run(action:()=>Promise<void>){if(lock.current)return;lock.current=true;setBusy(true);setError(null);try{await action();}catch(e){setError(message(e));if(e instanceof ApiError){const field=Object.keys(e.fieldErrors)[0];if(field)document.getElementsByName(field)[0]?.focus();}}finally{lock.current=false;setBusy(false);}}
 return{busy,error,run,setError};}
export function PageTitle({title,description,action}:{title:string;description?:string;action?:ReactNode}){return <header className="page-title"><div><h1>{title}</h1>{description&&<p>{description}</p>}</div>{action}</header>;}
export function Field({label,name,value,onChange,multiline=false,required=false,type='text',hint,autoComplete,minLength}:{label:string;name:string;value:string;onChange:(v:string)=>void;multiline?:boolean;required?:boolean;type?:string;hint?:string;autoComplete?:string;minLength?:number}){
 return <label className="form-field"><span>{label}{required&&<span className="required"> *</span>}</span>{multiline?<textarea name={name} value={value} onChange={e=>onChange(e.target.value)} rows={3} required={required} placeholder={hint}/>:<input name={name} value={value} onChange={e=>onChange(e.target.value)} type={type} required={required} placeholder={hint} autoComplete={autoComplete} minLength={minLength}/>}</label>;
}
export function RatingPanel({rating,confirmed}:{rating:Rating;confirmed:boolean}){return <aside className="rating-panel"><div className="rating-head"><h2>Готовность задачи</h2><strong>{rating.total}<small>/100</small></strong></div><p className="muted">{confirmed?'Баллы за подтверждённые сведения.':'Подтвердите сведения, чтобы получить оценку.'}</p><div className="rating-bars">{rating.categories.map(c=><details key={c.key}><summary><span>{c.label}</span><b>{c.points}/{c.max_points}</b></summary><progress value={c.points} max={c.max_points}/><ul>{c.basis.map(b=><li key={b}>{b}</li>)}</ul></details>)}</div>{rating.missing.length>0&&<div className="missing"><h3>Что повысит рейтинг</h3><ul>{rating.missing.map(v=><li key={v}>{v}</li>)}</ul></div>}</aside>;}
export function ProfileLink({id}:{id:string}){const {api}=useDemoSession();const [profile,setProfile]=useState<Profile|null>(null);useEffect(()=>{let active=true;void api.profile(id).then(v=>{if(active)setProfile(v);}).catch(()=>{});return()=>{active=false;};},[api,id]);return <Link to={'/profiles/'+id}>{profile?.name??'Профиль автора'}</Link>;}
export function SafeLink({url,label}:{url:string;label:string}){let valid=false;try{valid=['http:','https:'].includes(new URL(url).protocol);}catch{}return valid?<a href={url} target="_blank" rel="noreferrer">{label}</a>:null;}

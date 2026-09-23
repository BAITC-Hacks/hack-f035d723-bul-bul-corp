import {useEffect,useState,type FormEvent} from 'react';
import {Link} from 'react-router-dom';
import type {ProposalCreate,ProposalResponse} from '../../api/types';
import {useDemoSession} from '../../app/DemoSession';
import {ErrorNote,Field,statusLabels,useAction} from '../../app/ui';
import {readDraft,removeDraft,saveDraft} from '../../app/storage';
const initial:ProposalCreate={idea:'',plan:'',duration:'',prototype_url:''};
export function ProposalPanel({taskId}:{taskId:string}){
 const {api,selectedIdentity}=useDemoSession();const key=selectedIdentity!.id+':proposal:'+taskId;
 const [items,setItems]=useState<ProposalResponse[]>([]);const [values,setValues]=useState(()=>readDraft(key,initial));const [notice,setNotice]=useState('');const a=useAction();
 async function load(){await a.run(async()=>setItems((await api.teamProposals()).items.filter(p=>p.task_id===taskId)));}
 useEffect(()=>{if(selectedIdentity?.role==='team')void load();},[api,taskId,selectedIdentity?.id]);
 if(selectedIdentity?.role!=='team')return null;
 function edit<K extends keyof ProposalCreate>(field:K,value:string){const next={...values,[field]:value};setValues(next);saveDraft(key,next);}
 async function submit(e:FormEvent){e.preventDefault();if(values.prototype_url&&!/^https?:\/\//i.test(values.prototype_url)){a.setError('Ссылка на прототип должна начинаться с http:// или https://');document.getElementsByName('prototype_url')[0]?.focus();return;}
 await a.run(async()=>{const p=await api.createProposal(taskId,values);setItems(old=>[...old,p]);setValues(initial);removeDraft(key);setNotice('Предложение отправлено. Статус можно отслеживать в разделе «Моя работа».');});}
 return <section className="proposal-panel panel" id="proposal"><div className="section-top"><div><h2>Предложить решение</h2><p className="muted">Расскажите о подходе команды. Решение принимает бизнес.</p></div><Link to="/team">Моя работа</Link></div><ErrorNote text={a.error}/>{notice&&<div className="notice" role="status">{notice}</div>}
 {items.length>0&&<div className="own-proposals"><div className="section-top"><h3>Ваши предложения: {items.length}</h3><button disabled={a.busy} onClick={()=>void load()}>Обновить статусы</button></div>{items.map(p=><div className="own-proposal" key={p.id}><span>{p.idea}</span><span className={'badge '+p.status}>{statusLabels[p.status]}</span></div>)}</div>}
 <form onSubmit={submit}><fieldset disabled={a.busy}><Field label="Идея решения" name="idea" value={values.idea} onChange={v=>edit('idea',v)} multiline required/><Field label="План работы" name="plan" value={values.plan} onChange={v=>edit('plan',v)} multiline required/><div className="form-grid"><Field label="Срок" name="duration" value={values.duration} onChange={v=>edit('duration',v)} required hint="Например, две недели"/><Field label="Ссылка на прототип, необязательно" name="prototype_url" value={values.prototype_url} onChange={v=>edit('prototype_url',v)} type="url" hint="https://"/></div><div className="actions"><button className="primary">{a.busy?'Отправляем…':'Отправить предложение'}</button><span className="muted">Черновик сохраняется на этом устройстве.</span></div></fieldset></form></section>;
}

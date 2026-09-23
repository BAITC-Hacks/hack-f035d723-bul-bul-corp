import {createContext,useCallback,useContext,useEffect,useMemo,useRef,useState,type PropsWithChildren} from 'react';
import {ApiError,createApiClient,type ApiClient} from '../api/client';
import type {Account,Profile,Session} from '../api/types';
import {clearDrafts} from './storage';
interface SessionValue{api:ApiClient;user:Account|null;selectedIdentity:Profile|null;state:'loading'|'ready'|'guest'|'error';error:string|null;accept:(session:Session)=>void;reload:()=>Promise<void>;logout:()=>Promise<void>;}
const Context=createContext<SessionValue|null>(null);
export function DemoSessionProvider({children}:PropsWithChildren){
 const [user,setUser]=useState<Account|null>(null);
 const [state,setState]=useState<SessionValue['state']>('loading');
 const [error,setError]=useState<string|null>(null);const csrf=useRef('');
 const api=useMemo(()=>createApiClient({getCsrf:()=>csrf.current,onUnauthorized:()=>{csrf.current='';setUser(null);setState('guest');}}),[]);
 const accept=useCallback((session:Session)=>{csrf.current=session.csrf_token;setUser(session.user);setState('ready');setError(null);},[]);
 const reload=useCallback(async()=>{try{accept(await api.session());}catch(e){if(e instanceof ApiError&&e.status===401){setUser(null);setState('guest');}else{setError(e instanceof Error?e.message:'Не удалось проверить вход');setState('error');}}},[api,accept]);
 useEffect(()=>{void reload();},[reload]);
 async function logout(){try{await api.logout();}catch(e){if(!(e instanceof ApiError&&e.status===401))throw e;}if(user)clearDrafts(user.profile.id);csrf.current='';setUser(null);setState('guest');}
 return <Context.Provider value={{api,user,selectedIdentity:user?.profile??null,state,error,accept,reload,logout}}>{children}</Context.Provider>;
}
export function useDemoSession(){const value=useContext(Context);if(!value)throw new Error('Session provider missing');return value;}

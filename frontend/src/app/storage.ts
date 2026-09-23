const memory=new Map<string,string>();const prefix='sana.draft.';
export function readDraft<T>(key:string,fallback:T):T{try{const value=localStorage.getItem(prefix+key)??memory.get(key);return value?JSON.parse(value):fallback;}catch{try{return JSON.parse(memory.get(key)??'')as T;}catch{return fallback;}}}
export function saveDraft(key:string,value:unknown){const text=JSON.stringify(value);memory.set(key,text);try{localStorage.setItem(prefix+key,text);}catch{/* Storage is optional. */}}
export function removeDraft(key:string){memory.delete(key);try{localStorage.removeItem(prefix+key);}catch{/* Storage is optional. */}}
export function clearDrafts(profileId:string){for(const key of memory.keys())if(key.startsWith(profileId+':'))memory.delete(key);try{for(const key of Object.keys(localStorage))if(key.startsWith(prefix+profileId+':'))localStorage.removeItem(key);}catch{/* Storage is optional. */}}

import {useEffect,type ReactNode} from 'react';
import {Link,Navigate,NavLink,Route,Routes,useLocation} from 'react-router-dom';
import {CatalogPage} from '../features/catalog/CatalogPage';
import {TaskDetailsPage} from '../features/catalog/TaskDetailsPage';
import {AuthPage} from '../features/AuthPage';
import {ConstructorPage} from '../features/ConstructorPage';
import {BusinessPage,TeamPage} from '../features/Dashboards';
import {ProfilePage} from '../features/ProfilePage';
import {useDemoSession} from './DemoSession';
import {ErrorNote,Loading,useAction} from './ui';
function Icon({kind}:{kind:string}){return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">{kind==='catalog'?<><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>:kind==='profile'?<><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></>:kind==='new'?<path d="M12 4v16M4 12h16"/>:<><rect x="3" y="6" width="18" height="15" rx="2"/><path d="M8 6V3h8v3M3 12h18M10 12v3h4v-3"/></>}</svg>;}
function Guard({children,role}:{children:ReactNode;role?:'business'|'team'}){const {state,selectedIdentity,error,reload}=useDemoSession();if(state==='loading')return <Loading/>;if(state==='error')return <div className="empty"><h1>Не удалось подключиться</h1><ErrorNote text={error}/><button onClick={()=>void reload()}>Повторить</button></div>;if(!selectedIdentity)return <Navigate to="/login" replace/>;if(role&&selectedIdentity.role!==role)return <div className="empty"><h1>Этот раздел доступен {role==='business'?'бизнесу':'команде'}</h1><Link to="/catalog">Вернуться в каталог</Link></div>;return children;}
export function App(){const s=useDemoSession();const a=useAction();const location=useLocation();const authPage=['/login','/register'].includes(location.pathname);
 useEffect(()=>{window.scrollTo(0,0);document.getElementById('main-content')?.focus();},[location.pathname]);
 return <div className={authPage?'app auth-shell':'app'}><a className="skip-link" href="#main-content">Перейти к содержимому</a>
 <aside className="sidebar"><Link className="brand" to="/catalog"><span className="brand-mark">q.</span><span>Qadam</span></Link><nav aria-label="Основная навигация">
 <NavLink to="/catalog"><Icon kind="catalog"/>Каталог задач</NavLink>
 {s.selectedIdentity?.role==='business'&&<><NavLink to="/business"><Icon kind="work"/>Мои задачи</NavLink><NavLink to="/constructor"><Icon kind="new"/>Создать задачу</NavLink></>}
 {s.selectedIdentity?.role==='team'&&<NavLink to="/team"><Icon kind="work"/>Моя работа</NavLink>}
 {s.user&&<NavLink to="/profile"><Icon kind="profile"/>Мой профиль</NavLink>}
 </nav><div className="sidebar-bottom"><p>От задачи<br/>к результату.</p><span>Кейс AI Sana · HackAlem</span></div></aside>
 <div className="workspace"><header className="topbar"><span>{s.selectedIdentity?(s.selectedIdentity.role==='business'?'Пространство бизнеса':'Пространство команды'):'Практические проекты'}</span><div className="account-menu">{s.user?<><Link to="/profile"><span className="avatar">{s.user.name.slice(0,1)}</span><span>{s.user.profile.name}</span></Link><button className="text-button" disabled={a.busy} onClick={()=>void a.run(s.logout)}>Выйти</button></>:<Link to={location.pathname==='/login'?'/register':'/login'}>{location.pathname==='/login'?'Создать аккаунт':'Войти'}</Link>}</div></header>
 <main id="main-content" tabIndex={-1} className="main-content"><ErrorNote text={a.error}/><Routes>
 <Route path="/" element={<Navigate to="/catalog" replace/>}/><Route path="/login" element={<AuthPage key="login"/>}/><Route path="/register" element={<AuthPage register key="register"/>}/>
 <Route path="/catalog" element={<Guard><CatalogPage/></Guard>}/><Route path="/catalog/:taskId" element={<Guard><TaskDetailsPage/></Guard>}/>
 <Route path="/constructor" element={<Guard role="business"><ConstructorPage key={location.search+s.user?.id}/></Guard>}/>
 <Route path="/business" element={<Guard role="business"><BusinessPage/></Guard>}/><Route path="/team" element={<Guard role="team"><TeamPage/></Guard>}/>
 <Route path="/profile" element={<Guard><ProfilePage key={s.user?.id}/></Guard>}/><Route path="/profiles/:profileId" element={<Guard><ProfilePage key={location.pathname}/></Guard>}/>
 <Route path="*" element={<div className="empty"><h1>Страница не найдена</h1><Link to="/catalog">Открыть каталог</Link></div>}/>
 </Routes></main><footer className="footer"><span>Qadam</span><span>Решения выбирают люди.</span></footer></div></div>;
}

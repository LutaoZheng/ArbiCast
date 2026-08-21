export async function browserApi<T>(path:string, init?:RequestInit):Promise<T>{
  const response=await fetch(`/backend/api${path}`,{...init,cache:'no-store'});
  if(!response.ok){const text=await response.text();throw new Error(text||`API ${response.status}`)}
  return response.json();
}

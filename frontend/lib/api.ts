const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export async function api<T>(path:string):Promise<T>{
  try { const response=await fetch(`${API}/api${path}`,{next:{revalidate:2}}); if(!response.ok) throw new Error(`API ${response.status}`); return response.json(); }
  catch(error){ console.error(`ArbiCast API error for ${path}`,error); throw error; }
}


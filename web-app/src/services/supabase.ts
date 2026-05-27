import { createClient, SupabaseClient } from '@supabase/supabase-js';

let supabaseInstance: SupabaseClient | null = null;

export async function getSupabase(): Promise<SupabaseClient> {
  if (supabaseInstance) return supabaseInstance;
  const res = await fetch('/api/config');
  const config = await res.json();
  supabaseInstance = createClient(config.supabase_url, config.supabase_key, {
    auth: { persistSession: true },
  });
  return supabaseInstance;
}

export async function getAuthToken(): Promise<string | null> {
  const sb = await getSupabase();
  const session = await sb.auth.getSession();
  return session.data.session?.access_token ?? null;
}

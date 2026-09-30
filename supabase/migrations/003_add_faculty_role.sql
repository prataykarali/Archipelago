-- Add faculty role to the Archipelago role enum
ALTER TYPE public.archipelago_role ADD VALUE IF NOT EXISTS 'faculty';

-- Role page permissions table
CREATE TABLE IF NOT EXISTS public.role_page_permissions (
  id SERIAL PRIMARY KEY,
  role TEXT NOT NULL,
  page TEXT NOT NULL,
  allowed BOOLEAN NOT NULL DEFAULT true,
  UNIQUE(role, page)
);

-- Seed permission matrix
INSERT INTO public.role_page_permissions (role, page, allowed) VALUES
  ('student', 'chat', true),
  ('student', 'library', true),
  ('student', 'graph_explorer', false),
  ('student', 'admin', false),
  ('faculty', 'chat', true),
  ('faculty', 'library', true),
  ('faculty', 'graph_explorer', false),
  ('faculty', 'admin', false),
  ('librarian', 'chat', true),
  ('librarian', 'library', true),
  ('librarian', 'graph_explorer', true),
  ('librarian', 'admin', false),
  ('administrator', 'chat', true),
  ('administrator', 'library', true),
  ('administrator', 'graph_explorer', true),
  ('administrator', 'admin', true)
ON CONFLICT (role, page) DO NOTHING;

-- Enable RLS
ALTER TABLE public.role_page_permissions ENABLE ROW LEVEL SECURITY;
